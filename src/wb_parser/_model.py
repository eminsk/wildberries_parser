"""
Lightweight, zero-dependency, Free-Threaded (No-GIL) safe model layer for `wb_parser`.

Implements the Pydantic-v2-compatible subset used across the SDK (`BaseModel`,
`Field`, `ConfigDict`, `model_validator`, `model_validate`, `model_dump`,
`model_dump_json`) in 100% pure Python so the core package installs and runs
natively on CPython 3.8-3.16, PyPy 3.8-3.12, No-GIL 3.13t-3.16t, and Debian APT.
"""

from __future__ import annotations

import functools
import json
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union

try:
    from typing import get_args, get_origin, get_type_hints
except ImportError:  # pragma: no cover
    from typing_extensions import get_args, get_origin, get_type_hints  # type: ignore

T = TypeVar("T", bound="BaseModel")

_NONE_TYPE = type(None)
_SPEC_LOCK = threading.RLock()


class _UnsetType:
    """Sentinel distinguishing omitted default values from explicit `None`."""


_UNSET = _UnsetType()


class _FieldInfo:
    __slots__ = ("default", "default_factory", "alias")

    def __init__(
        self,
        *,
        default: Any = _UNSET,
        default_factory: Optional[Callable[[], Any]] = None,
        alias: Optional[str] = None,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.alias = alias


def Field(
    default: Any = _UNSET,
    *,
    default_factory: Optional[Callable[[], Any]] = None,
    alias: Optional[str] = None,
    **_extra: Any,
) -> Any:
    """Declare field defaults, factories, or input aliases on a `BaseModel`."""
    return _FieldInfo(default=default, default_factory=default_factory, alias=alias)


def ConfigDict(**kwargs: Any) -> Dict[str, Any]:
    """Build model configuration dictionary (`extra`, `populate_by_name`, etc.)."""
    return dict(kwargs)


class _BeforeValidator:
    """Descriptor wrapping a `@model_validator(mode='before')` method."""

    def __init__(self, fn: Any) -> None:
        self._is_cm = isinstance(fn, classmethod)
        self.fn = fn.__func__ if self._is_cm else fn
        self._wb_before_validator = True

    def __get__(self, instance: Any, owner: Any = None) -> Any:
        cls = owner if owner is not None else type(instance)
        return functools.partial(self.fn, cls) if self._is_cm else self.fn


def model_validator(*, mode: str = "before") -> Callable[[Any], Any]:
    """Register a pre-validation normalization hook (`mode='before'`)."""

    def _decorator(fn: Any) -> Any:
        if mode == "before":
            return _BeforeValidator(fn)
        return fn

    return _decorator


class _FieldSpec:
    __slots__ = ("name", "annotation", "default", "default_factory", "alias")

    def __init__(
        self,
        *,
        name: str,
        annotation: Any,
        default: Any,
        default_factory: Optional[Callable[[], Any]],
        alias: Optional[str],
    ) -> None:
        self.name = name
        self.annotation = annotation
        self.default = default
        self.default_factory = default_factory
        self.alias = alias


class _ModelSpec:
    __slots__ = ("fields", "before_validators", "populate_by_name", "extra")

    def __init__(
        self,
        *,
        fields: List[_FieldSpec],
        before_validators: List[Callable[..., Any]],
        populate_by_name: bool,
        extra: str,
    ) -> None:
        self.fields = fields
        self.before_validators = before_validators
        self.populate_by_name = populate_by_name
        self.extra = extra


def _copy_default(value: Any) -> Any:
    if isinstance(value, (list, dict, set)):
        return value.copy()
    return value


def _dump_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_dump_value(item) for item in value]
    if isinstance(value, tuple):
        return [_dump_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _dump_value(v) for k, v in value.items()}
    return value


def _coerce_value(value: Any, annotation: Any) -> Any:
    if annotation is Any or annotation is object:
        return value

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Union:
        if value is None and _NONE_TYPE in args:
            return None
        non_none = [arg for arg in args if arg is not _NONE_TYPE]
        if len(non_none) == 1:
            return _coerce_value(value, non_none[0])
        for candidate in non_none:
            try:
                return _coerce_value(value, candidate)
            except Exception:
                continue
        return value

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        if isinstance(value, annotation):
            return value
        if isinstance(value, dict):
            return annotation.model_validate(value)
        return value

    if origin in (list, List):
        if value is None:
            return []
        seq = list(value)
        if args and args[0] is not Any:
            elem_type = args[0]
            return [_coerce_value(item, elem_type) for item in seq]
        return seq

    if origin in (dict, Dict):
        if value is None:
            return {}
        if not isinstance(value, dict):
            return dict(value)
        key_type = args[0] if len(args) >= 1 else Any
        val_type = args[1] if len(args) >= 2 else Any
        return {
            _coerce_value(k, key_type): _coerce_value(v, val_type)
            for k, v in value.items()
        }

    if annotation is bool:
        return bool(value)

    if annotation is int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(float(value))

    if annotation is float:
        return float(value)

    if annotation is str:
        return "" if value is None else str(value)

    return value


def _compile_model_spec(cls: Type["BaseModel"]) -> _ModelSpec:
    fields: List[_FieldSpec] = []
    before_validators: List[Callable[..., Any]] = []
    seen_fields: set[str] = set()
    field_order: List[str] = []
    hints: Dict[str, Any] = {}
    defaults: Dict[str, Any] = {}

    for base in reversed(cls.__mro__):
        if base in (BaseModel, object):
            continue

        raw_ann = base.__dict__.get("__annotations__", {})
        mod = sys.modules.get(base.__module__)
        base_globals = getattr(mod, "__dict__", {}) if mod is not None else {}
        try:
            resolved_hints = get_type_hints(base, globalns=base_globals)
        except Exception:
            resolved_hints = {}

        for fname in raw_ann:
            if fname == "model_config":
                continue
            if fname not in seen_fields:
                seen_fields.add(fname)
                field_order.append(fname)
            hints[fname] = resolved_hints.get(fname, Any)

        for attr_name, attr_val in base.__dict__.items():
            if attr_name in raw_ann and attr_name != "model_config":
                defaults[attr_name] = attr_val
            if isinstance(attr_val, _BeforeValidator):
                before_validators.append(attr_val.fn)

    for fname in field_order:
        raw_def = defaults.get(fname, _UNSET)
        if isinstance(raw_def, _FieldInfo):
            f_default = raw_def.default
            f_factory = raw_def.default_factory
            f_alias = raw_def.alias
        else:
            f_default = raw_def
            f_factory = None
            f_alias = None
        fields.append(
            _FieldSpec(
                name=fname,
                annotation=hints.get(fname, Any),
                default=f_default,
                default_factory=f_factory,
                alias=f_alias,
            )
        )

    cfg = getattr(cls, "model_config", None)
    if not isinstance(cfg, dict):
        cfg = {}

    return _ModelSpec(
        fields=fields,
        before_validators=before_validators,
        populate_by_name=bool(cfg.get("populate_by_name", False)),
        extra=str(cfg.get("extra", "ignore")),
    )


def _get_model_spec(cls: Type["BaseModel"]) -> _ModelSpec:
    existing = cls.__dict__.get("__wb_compiled_spec__")
    if isinstance(existing, _ModelSpec):
        return existing
    with _SPEC_LOCK:
        existing = cls.__dict__.get("__wb_compiled_spec__")
        if isinstance(existing, _ModelSpec):
            return existing
        spec = _compile_model_spec(cls)
        setattr(cls, "__wb_compiled_spec__", spec)
        return spec


class BaseModel:
    """Thread-safe pure-Python base model compatible with Pydantic v2 SDK calls."""

    model_config: Dict[str, Any] = ConfigDict(extra="ignore", populate_by_name=True)

    def __init__(self, **data: Any) -> None:
        self._populate_from_mapping(data)

    def _populate_from_mapping(self, raw: Any) -> None:
        cls = type(self)
        spec = _get_model_spec(cls)

        payload: Any = dict(raw) if isinstance(raw, dict) else raw
        for fn in spec.before_validators:
            payload = fn(cls, payload)

        if not isinstance(payload, dict):
            raise TypeError(f"{cls.__name__} expected dict input, got {type(payload).__name__}")

        for field in spec.fields:
            if spec.populate_by_name:
                if field.name in payload:
                    val = payload[field.name]
                elif field.alias and field.alias in payload:
                    val = payload[field.alias]
                elif field.default_factory is not None:
                    val = field.default_factory()
                elif field.default is not _UNSET:
                    val = _copy_default(field.default)
                else:
                    raise ValueError(f"Missing required field {field.name!r} for {cls.__name__}")
            else:
                if field.alias and field.alias in payload:
                    val = payload[field.alias]
                elif field.name in payload:
                    val = payload[field.name]
                elif field.default_factory is not None:
                    val = field.default_factory()
                elif field.default is not _UNSET:
                    val = _copy_default(field.default)
                else:
                    raise ValueError(f"Missing required field {field.name!r} for {cls.__name__}")

            setattr(self, field.name, _coerce_value(val, field.annotation))

    @classmethod
    def model_validate(cls: Type[T], obj: Any) -> T:
        """Create and validate a model instance from a dict or existing instance."""
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, BaseModel):
            obj = obj.model_dump()
        instance = cls.__new__(cls)
        instance._populate_from_mapping(obj)
        return instance

    def model_dump(self) -> Dict[str, Any]:
        """Serialize model fields recursively to a plain dictionary."""
        spec = _get_model_spec(type(self))
        return {
            field.name: _dump_value(getattr(self, field.name))
            for field in spec.fields
        }

    def model_dump_json(self, indent: Optional[int] = None) -> str:
        """Serialize model fields recursively to UTF-8 JSON string."""
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=indent)

    def __repr__(self) -> str:
        spec = _get_model_spec(type(self))
        parts = ", ".join(f"{f.name}={getattr(self, f.name)!r}" for f in spec.fields[:5])
        suffix = ", ..." if len(spec.fields) > 5 else ""
        return f"{type(self).__name__}({parts}{suffix})"

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return self.model_dump() == other.model_dump()
