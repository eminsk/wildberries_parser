"""
Unified Free & Paid AI Engine for WB SDK Pro (`wb_parser.ai`).

Combines:
1. Free Zero-Key AI via `g4f` provider discovery, model listing, latency/error
   health-checks, and automatic multi-provider fallback (inspired by `testg4f`).
2. Local Key-Free OpenAI-compatible runtimes (`Ollama`, `LM Studio`, `vLLM`).
3. Paid & Hybrid OpenAI-compatible APIs (`OpenAI`, `DeepSeek`, `OpenRouter`,
   `ProxyAPI`, `Groq`, `Google Gemini`, or custom `base_url`).

Core discovery, health-check, and OpenAI-compatible calls require only standard
library + `httpx`/`requests` (Python 3.8-3.16, PyPy, No-GIL). Free `g4f` routing
is activated automatically whenever optional extra `wb-sdk-pro[ai]` (`g4f`) is
installed.
"""

from __future__ import annotations

import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar, Union

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

try:
    import requests as std_requests
except ImportError:  # pragma: no cover
    std_requests = None  # type: ignore[assignment]

from wb_parser._model import BaseModel, Field

FREE_G4F_CANDIDATES: Tuple[str, ...] = (
    "Yqcloud",
    "Airforce",
    "LLM7",
    "GLM",
    "DeepInfra",
    "Cloudflare",
    "BraveSearch",
    "G4FSpace",
    "Cerebras",
    "KiloCode",
    "Pollinations",
)

AI_PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "backend": "openai_compat",
        "tier": "paid",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "env_var": "OPENAI_API_KEY",
        "needs_auth": True,
        "url": "https://platform.openai.com",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o3-mini"],
        "notes": "Official OpenAI Chat Completions API",
    },
    "deepseek": {
        "name": "DeepSeek",
        "backend": "openai_compat",
        "tier": "paid",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_var": "DEEPSEEK_API_KEY",
        "needs_auth": True,
        "url": "https://platform.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "notes": "DeepSeek V3 / R1 API",
    },
    "openrouter": {
        "name": "OpenRouter (Free + Paid)",
        "backend": "openai_compat",
        "tier": "hybrid",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "deepseek/deepseek-chat-v3-0324:free",
        "env_var": "OPENROUTER_API_KEY",
        "needs_auth": True,
        "url": "https://openrouter.ai",
        "models": [
            "deepseek/deepseek-chat-v3-0324:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-3.8-flash",
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
        ],
        "notes": "Unified gateway hosting `:free` models and paid flagship models",
    },
    "proxyapi": {
        "name": "ProxyAPI (RU OpenAI/Claude Gateway)",
        "backend": "openai_compat",
        "tier": "paid",
        "base_url": "https://api.proxyapi.ru/openai/v1",
        "default_model": "gpt-4o-mini",
        "env_var": "PROXYAPI_API_KEY",
        "needs_auth": True,
        "url": "https://proxyapi.ru",
        "models": ["gpt-4o-mini", "gpt-4o", "deepseek-chat"],
        "notes": "Russian-accessible OpenAI-compatible gateway",
    },
    "groq": {
        "name": "Groq (Free Tier + Paid)",
        "backend": "openai_compat",
        "tier": "hybrid",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "openai/gpt-oss-20b",
        "env_var": "GROQ_API_KEY",
        "needs_auth": True,
        "url": "https://console.groq.com",
        "models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"],
        "notes": "Ultra-fast LPU inference with free developer quota",
    },
    "gemini": {
        "name": "Google Gemini (OpenAI Compat)",
        "backend": "openai_compat",
        "tier": "hybrid",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-3.8-flash",
        "env_var": "GEMINI_API_KEY",
        "needs_auth": True,
        "url": "https://aistudio.google.com",
        "models": ["gemini-3.8-flash", "gemini-flash-latest", "gemini-pro-latest"],
        "notes": "Google AI Studio free/paid tier via OpenAI-compatible endpoint",
    },
    "ollama": {
        "name": "Ollama (Local Free)",
        "backend": "openai_compat",
        "tier": "local",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "env_var": "OLLAMA_BASE_URL",
        "needs_auth": False,
        "url": "https://ollama.com",
        "models": ["llama3.2", "qwen2.5", "mistral", "gemma2"],
        "notes": "100% free local LLM runtime (no API key required)",
    },
    "lmstudio": {
        "name": "LM Studio (Local Free)",
        "backend": "openai_compat",
        "tier": "local",
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
        "env_var": "LMSTUDIO_BASE_URL",
        "needs_auth": False,
        "url": "https://lmstudio.ai",
        "models": ["local-model"],
        "notes": "Local OpenAI-compatible server on port 1234",
    },
}

_PAID_KEY_ENV_ORDER: Tuple[Tuple[str, str], ...] = (
    ("custom", "WB_AI_KEY"),
    ("openai", "OPENAI_API_KEY"),
    ("deepseek", "DEEPSEEK_API_KEY"),
    ("openrouter", "OPENROUTER_API_KEY"),
    ("proxyapi", "PROXYAPI_API_KEY"),
    ("groq", "GROQ_API_KEY"),
    ("gemini", "GEMINI_API_KEY"),
)

_PROVIDER_ALIASES: Dict[str, str] = {
    "local": "ollama",
    "ollama": "ollama",
    "lm-studio": "lmstudio",
    "lmstudio": "lmstudio",
    "openrouter": "openrouter",
    "proxyapi": "proxyapi",
    "deepseek": "deepseek",
    "openai": "openai",
    "groq": "groq",
    "gemini": "gemini",
    "google": "gemini",
}


class AIProviderInfo(BaseModel):
    """Normalized metadata describing either a free (`g4f`/local) or paid AI provider."""

    index: int = 0
    id: str
    name: str
    backend: str = "openai_compat"
    tier: str = "free"
    working: bool = True
    needs_auth: bool = False
    supports_stream: bool = True
    default_model: str = ""
    base_url: str = ""
    env_var: str = ""
    url: str = ""
    models: List[str] = Field(default_factory=list)
    notes: str = ""
    configured: bool = False


class AIProviderResult(BaseModel):
    """Health-check / prompt execution benchmark result for an AI provider."""

    provider: str
    backend: str = "openai_compat"
    tier: str = "free"
    model: str = ""
    success: bool = False
    response_text: str = ""
    latency_seconds: float = 0.0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    hint: Optional[str] = None


class AIChatResult(BaseModel):
    """Result returned by `generate_completion` across free, local, and paid backends."""

    ok: bool = False
    content: str = ""
    provider: str = ""
    model: str = ""
    backend: str = ""
    tier: str = ""
    latency_seconds: float = 0.0
    error: Optional[str] = None
    attempts: List[str] = Field(default_factory=list)


def _load_g4f_modules() -> Optional[Tuple[Any, Any]]:
    """Lazily import `(g4f.Provider, g4f.client.Client)` if optional `g4f` package is installed."""
    try:
        import g4f.Provider as g4f_providers  # type: ignore[import-not-found]
        from g4f.client import Client as G4FClient  # type: ignore[import-not-found]
        return g4f_providers, G4FClient
    except ImportError:
        return None


def is_g4f_available() -> bool:
    """Return True when the optional `g4f` free-AI backend is installed."""
    return _load_g4f_modules() is not None


def extract_static_models(provider_cls: Any) -> List[str]:
    """Extract static models + `default_model` from a `g4f` provider class without network calls."""
    models: List[Any] = []
    raw_models = getattr(provider_cls, "models", None)
    if raw_models:
        if isinstance(raw_models, dict):
            models.extend(list(raw_models.keys()))
        elif isinstance(raw_models, (list, tuple, set)):
            models.extend(list(raw_models))

    def_m = getattr(provider_cls, "default_model", None)
    if def_m and def_m not in models:
        models.insert(0, def_m)

    clean: List[str] = []
    for item in models:
        val = getattr(item, "name", item) if not isinstance(item, str) else item
        if isinstance(val, str):
            stripped = val.strip()
            if stripped and stripped not in clean:
                clean.append(stripped)
    return clean


def _diagnose_ai_error(err_type: str, err_msg: str) -> Optional[str]:
    """Return a concise actionable hint for common Free/Paid AI failures."""
    joined = f"{err_type} {err_msg}"
    if "MissingAuth" in err_type or "401" in err_msg or "Missing Authorization" in err_msg or "API key" in err_msg:
        return "Provider requires an API key/token (set key or switch to mode='free' / local Ollama)."
    if "PaymentRequired" in err_type or "402" in err_msg or "insufficient_quota" in err_msg:
        return "Provider quota/credits exhausted (402). Try free g4f mode or another provider."
    if "403" in err_msg or "ResponseStatusError" in err_type or "Cloudflare" in joined:
        return "Blocked by Cloudflare/WAF or regional restriction (403). Try another provider or proxy."
    if "Timeout" in err_type:
        return "Provider timed out; increase timeout or use automatic free fallback."
    if "MissingRequirements" in err_type or "No module named 'g4f'" in err_msg:
        return 'Install optional extra dependencies: uv add "wb-sdk-pro[ai]"'
    if "ConnectionError" in err_type or "ConnectError" in err_type:
        return "Could not connect to endpoint (check base_url or start local Ollama server)."
    return None


def _is_local_url(url: str) -> bool:
    lowered = url.lower()
    return "localhost" in lowered or "127.0.0.1" in lowered or "0.0.0.0" in lowered


def _strip_g4f_prefix(name: str) -> Tuple[str, bool]:
    """Strip explicit `g4f:` prefix; returns `(clean_name, forced_g4f)`."""
    trimmed = name.strip()
    if trimmed.lower().startswith("g4f:"):
        return trimmed[4:].strip(), True
    return trimmed, False


_T = TypeVar("_T")


def _run_with_daemon_timeout(fn: Callable[[], _T], timeout: float, timeout_label: str) -> _T:
    """
    Execute `fn()` on a daemon thread with wall-clock timeout without registering
    non-daemon `ThreadPoolExecutor` atexit joins (prevents process exit hangs).
    """
    result_box: Dict[str, Any] = {}

    def _runner() -> None:
        try:
            result_box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001
            result_box["error"] = exc

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout=max(0.05, float(timeout)))
    if t.is_alive():
        raise TimeoutError(f"{timeout_label} timed out after {timeout}s")
    if "error" in result_box:
        raise result_box["error"]
    return result_box["value"]


def _is_non_text_or_nag_response(content: str) -> bool:
    lowered = content.strip().lower()
    return (
        lowered.startswith("<audio ")
        or "https://image.pollinations.ai/" in lowered
        or "sign up and repeat your request" in lowered
    )


def _resolve_preset_key(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    clean, forced_g4f = _strip_g4f_prefix(name)
    if forced_g4f:
        return None
    norm = clean.lower()
    if norm in _PROVIDER_ALIASES:
        return _PROVIDER_ALIASES[norm]
    if norm in AI_PROVIDER_PRESETS:
        return norm
    return None


def _env_key_for_preset(preset_key: Optional[str]) -> str:
    if preset_key and preset_key in AI_PROVIDER_PRESETS:
        env_name = AI_PROVIDER_PRESETS[preset_key]["env_var"]
        if env_name and not AI_PROVIDER_PRESETS[preset_key]["needs_auth"]:
            return ""
        if env_name and os.environ.get(env_name):
            return os.environ[env_name].strip()
    return (os.environ.get("WB_AI_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()


def _detect_any_paid_env() -> Optional[Tuple[str, str]]:
    """Return `(preset_slug, api_key)` for the first configured paid AI env var."""
    for slug, env_var in _PAID_KEY_ENV_ORDER:
        val = (os.environ.get(env_var) or "").strip()
        if val:
            return ("openai" if slug == "custom" else slug), val
    return None


def list_g4f_providers(
    *,
    only_working: bool = False,
    only_free: bool = False,
    search_query: str = "",
) -> List[AIProviderInfo]:
    """
    Discover registered `g4f` providers cleanly without network requests.
    Returns `[]` if `g4f` (`wb-sdk-pro[ai]`) is not installed.
    """
    mods = _load_g4f_modules()
    if mods is None:
        return []
    g4f_providers, _ = mods
    raw_providers = getattr(g4f_providers, "__providers__", [])
    query = search_query.strip().lower()

    items: List[AIProviderInfo] = []
    idx = 1
    for cls in raw_providers:
        name = getattr(cls, "__name__", str(cls))
        working = bool(getattr(cls, "working", False))
        needs_auth = bool(getattr(cls, "needs_auth", False))
        supports_stream = bool(getattr(cls, "supports_stream", False))
        default_model = str(getattr(cls, "default_model", "") or "")
        url = str(getattr(cls, "url", "") or "")

        if only_working and not working:
            continue
        if only_free and needs_auth:
            continue
        if query and query not in name.lower() and query not in url.lower():
            continue

        items.append(
            AIProviderInfo(
                index=idx,
                id=name,
                name=name,
                backend="g4f",
                tier="paid" if needs_auth else "free",
                working=working,
                needs_auth=needs_auth,
                supports_stream=supports_stream,
                default_model=default_model,
                url=url,
                models=extract_static_models(cls),
                notes="Free no-key g4f provider" if not needs_auth else "Requires g4f auth / cookies / API key",
                configured=not needs_auth,
            )
        )
        idx += 1
    return items


def fetch_g4f_provider_models(provider_name: str, timeout: float = 3.0) -> List[str]:
    """Return static + lazy remote models for a `g4f` provider within `timeout` seconds."""
    mods = _load_g4f_modules()
    if mods is None:
        return []
    g4f_providers, _ = mods
    clean_name, _ = _strip_g4f_prefix(provider_name)
    target_cls = getattr(g4f_providers, clean_name, None)
    if target_cls is None:
        for cls in getattr(g4f_providers, "__providers__", []):
            if getattr(cls, "__name__", "").lower() == clean_name.lower():
                target_cls = cls
                break
    if target_cls is None:
        return []

    models = extract_static_models(target_cls)
    if len(models) > 1 or not hasattr(target_cls, "get_models"):
        return models

    try:
        res = _run_with_daemon_timeout(target_cls.get_models, timeout=timeout, timeout_label=clean_name)
        extra_raw: Sequence[Any] = ()
        if isinstance(res, dict):
            extra_raw = list(res.keys())
        elif isinstance(res, (list, tuple, set)):
            extra_raw = list(res)
        for m in extra_raw:
            val = getattr(m, "name", m) if not isinstance(m, str) else m
            if isinstance(val, str) and val.strip() and val.strip() not in models:
                models.append(val.strip())
    except Exception:
        pass
    return models


def list_ai_providers(
    *,
    tier: str = "all",
    only_working: bool = False,
    only_free: bool = False,
    include_g4f: bool = True,
    search_query: str = "",
) -> List[AIProviderInfo]:
    """
    Unified discovery listing Built-in Paid / Hybrid / Local presets AND Free `g4f` providers.

    Args:
        tier: Filter category: `"all"`, `"free"` (`g4f` free + local), `"paid"`, `"local"`, or `"g4f"`.
        only_working: Filter out inactive providers.
        only_free: Return strictly zero-key providers (`needs_auth=False`).
        include_g4f: Include discovered `g4f` providers when `g4f` is installed.
        search_query: Case-insensitive filter across id, name, notes, and URL.
    """
    tier_norm = (tier or "all").strip().lower()
    query = search_query.strip().lower()
    collected: List[AIProviderInfo] = []

    if tier_norm != "g4f":
        for slug, cfg in AI_PROVIDER_PRESETS.items():
            p_tier = cfg["tier"]
            needs_auth = bool(cfg["needs_auth"])
            if only_free and needs_auth:
                continue
            if tier_norm == "free" and p_tier not in ("local", "hybrid"):
                continue
            if tier_norm == "paid" and p_tier not in ("paid", "hybrid"):
                continue
            if tier_norm == "local" and p_tier != "local":
                continue

            env_name = str(cfg.get("env_var") or "")
            is_configured = (not needs_auth) or bool(env_name and os.environ.get(env_name))
            base_url = str(cfg["base_url"])
            if not needs_auth and env_name and os.environ.get(env_name):
                base_url = os.environ[env_name].strip() or base_url

            haystack = f"{slug} {cfg['name']} {cfg['notes']} {base_url} {cfg['url']}".lower()
            if query and query not in haystack:
                continue

            collected.append(
                AIProviderInfo(
                    id=slug,
                    name=str(cfg["name"]),
                    backend="openai_compat",
                    tier=p_tier,
                    working=True,
                    needs_auth=needs_auth,
                    supports_stream=True,
                    default_model=str(cfg["default_model"]),
                    base_url=base_url,
                    env_var=env_name,
                    url=str(cfg["url"]),
                    models=list(cfg["models"]),
                    notes=str(cfg["notes"]),
                    configured=is_configured,
                )
            )

    if include_g4f and tier_norm in ("all", "free", "g4f", "paid"):
        g4f_only_free = only_free or (tier_norm == "free")
        g4f_items = list_g4f_providers(
            only_working=only_working,
            only_free=g4f_only_free,
            search_query=search_query,
        )
        if tier_norm == "paid":
            g4f_items = [item for item in g4f_items if item.needs_auth]
        collected.extend(g4f_items)

    for idx, item in enumerate(collected, start=1):
        item.index = idx
    return collected


def find_ai_provider(
    identifier: Union[str, int],
    providers: Optional[Sequence[AIProviderInfo]] = None,
) -> Optional[AIProviderInfo]:
    """Find a free or paid AI provider by 1-based index, exact slug/name (`g4f:Name`), or substring."""
    pool = list(providers) if providers is not None else list_ai_providers()
    id_str = str(identifier).strip()
    if not id_str:
        return None

    if id_str.isdigit():
        idx = int(id_str)
        if 1 <= idx <= len(pool):
            return pool[idx - 1]

    clean_id, forced_g4f = _strip_g4f_prefix(id_str)
    if forced_g4f:
        pool = [p for p in pool if p.backend == "g4f"]
    id_lower = clean_id.lower() if forced_g4f else _PROVIDER_ALIASES.get(clean_id.lower(), clean_id.lower())
    for p in pool:
        if p.id.lower() == id_lower or p.name.lower() == id_lower:
            return p
    for p in pool:
        if id_lower in p.id.lower() or id_lower in p.name.lower():
            return p
    return None


def _post_openai_chat(
    prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    temperature: float = 0.2,
    timeout: float = 25.0,
) -> str:
    """Execute a standard `/chat/completions` HTTP call using `httpx` or `requests`."""
    endpoint = base_url.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }

    if httpx is not None:
        with httpx.Client(timeout=timeout) as http:
            resp = http.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            body = resp.json()
    elif std_requests is not None:
        resp = std_requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        body = resp.json()
    else:  # pragma: no cover
        raise RuntimeError("Install `httpx` or `requests` to call OpenAI-compatible endpoints")

    choices = body.get("choices") or []
    if not choices:
        return str(body)
    return str((choices[0].get("message") or {}).get("content") or "").strip()


def _resolve_g4f_class(provider_name: str) -> Tuple[Any, Any]:
    mods = _load_g4f_modules()
    if mods is None:
        raise RuntimeError('Optional `g4f` backend is not installed. Run: uv add "wb-sdk-pro[ai]"')
    g4f_providers, G4FClient = mods

    clean_name, _ = _strip_g4f_prefix(provider_name)
    direct = getattr(g4f_providers, clean_name, None)
    if direct is not None:
        return direct, G4FClient

    target_lower = clean_name.lower()
    for cls in getattr(g4f_providers, "__providers__", []):
        if getattr(cls, "__name__", "").lower() == target_lower:
            return cls, G4FClient
    raise ValueError(f"Unknown g4f provider: {provider_name!r}")


def _call_g4f_provider(
    provider_name: str,
    prompt: str,
    *,
    model: str = "",
    timeout: float = 15.0,
) -> Tuple[str, str, str]:
    """Call a single `g4f` provider with hard daemon-thread timeout; returns `(content, provider, model)`."""
    provider_cls, G4FClient = _resolve_g4f_class(provider_name)
    resolved_name = getattr(provider_cls, "__name__", str(provider_name))
    target_model = model or str(getattr(provider_cls, "default_model", "") or "")

    def _run() -> str:
        client = G4FClient(provider=provider_cls)
        resp = client.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        if hasattr(resp, "choices") and resp.choices:
            return str(resp.choices[0].message.content or "").strip()
        return str(resp).strip()

    content = _run_with_daemon_timeout(_run, timeout=timeout, timeout_label=resolved_name)
    if not content:
        raise RuntimeError(f"{resolved_name} returned empty response")
    if _is_non_text_or_nag_response(content):
        raise RuntimeError(f"{resolved_name} returned non-text or signup prompt: {content[:80]}")
    return content, resolved_name, target_model or "(default)"


def _g4f_fallback_order() -> List[str]:
    """Return ordered list of working key-free `g4f` providers prioritizing proven candidates."""
    free_working = list_g4f_providers(only_working=True, only_free=True)
    by_lower = {p.id.lower(): p.id for p in free_working}

    ordered: List[str] = []
    for candidate in FREE_G4F_CANDIDATES:
        matched = by_lower.pop(candidate.lower(), None)
        if matched:
            ordered.append(matched)
    for remaining in by_lower.values():
        ordered.append(remaining)
    return ordered


def _resolve_openai_params(
    *,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[str, str, str, str, str]:
    """
    Resolve `(preset_slug, resolved_tier, resolved_base_url, resolved_key, resolved_model)`
    for OpenAI-compatible (Paid / Hybrid / Local) backends.
    """
    preset_slug = _resolve_preset_key(provider)
    key = (api_key or "").strip()

    if not preset_slug and not key and not base_url:
        detected = _detect_any_paid_env()
        if detected:
            preset_slug, key = detected

    if not preset_slug and base_url:
        lower_url = base_url.lower()
        if "deepseek.com" in lower_url:
            preset_slug = "deepseek"
        elif "openrouter.ai" in lower_url:
            preset_slug = "openrouter"
        elif "proxyapi.ru" in lower_url:
            preset_slug = "proxyapi"
        elif "groq.com" in lower_url:
            preset_slug = "groq"
        elif "generativelanguage.googleapis.com" in lower_url:
            preset_slug = "gemini"
        elif _is_local_url(lower_url):
            preset_slug = "ollama"
        else:
            preset_slug = "openai"

    preset = AI_PROVIDER_PRESETS.get(preset_slug or "openai", AI_PROVIDER_PRESETS["openai"])
    resolved_slug = preset_slug or "openai"
    env_base_override = ""
    if not preset.get("needs_auth") and preset.get("env_var"):
        env_base_override = (os.environ.get(str(preset["env_var"])) or "").strip()
    resolved_url = (base_url or "").strip() or env_base_override or str(preset["base_url"])
    resolved_tier = "local" if _is_local_url(resolved_url) else str(preset["tier"])
    resolved_model = (model or "").strip() or str(preset["default_model"])

    if not key:
        if resolved_tier == "local":
            key = "ollama"
        else:
            key = _env_key_for_preset(resolved_slug)

    return resolved_slug, resolved_tier, resolved_url, key, resolved_model


def generate_completion(
    prompt: str,
    *,
    mode: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.2,
    timeout: float = 25.0,
    g4f_fallback_limit: int = 5,
) -> AIChatResult:
    """
    Execute a chat completion seamlessly across Free (`g4f` / local `Ollama`)
    and Paid (`OpenAI` / `DeepSeek` / `OpenRouter` / `ProxyAPI` / `Groq` / custom) models.
    """
    eff_mode = (mode or os.environ.get("WB_AI_MODE") or "auto").strip().lower()
    eff_provider = (provider or os.environ.get("WB_AI_PROVIDER") or "").strip()
    eff_model = (model or os.environ.get("WB_AI_MODEL") or "").strip()
    eff_url = (base_url or os.environ.get("WB_AI_BASE_URL") or "").strip() or None
    eff_key = (api_key or "").strip() or None

    if eff_mode == "offline":
        return AIChatResult(ok=False, provider="offline", backend="offline", tier="offline", error="Offline mode selected")

    preset_slug = _resolve_preset_key(eff_provider)
    explicit_g4f = bool(
        eff_provider
        and not preset_slug
        and eff_provider.lower() not in ("auto", "default")
    )
    g4f_auto_requested = eff_provider.lower() in ("g4f", "auto-free", "free", "auto free pool")

    def _run_openai_compat() -> AIChatResult:
        slug, tier, url, key, mdl = _resolve_openai_params(
            provider=eff_provider or None,
            api_key=eff_key,
            base_url=eff_url,
            model=eff_model or None,
        )
        if not key and tier != "local":
            env_hint = AI_PROVIDER_PRESETS.get(slug, {}).get("env_var", "OPENAI_API_KEY")
            return AIChatResult(
                ok=False,
                provider=slug,
                model=mdl,
                backend="openai_compat",
                tier=tier,
                error=f"Missing API key for {slug} (pass api_key or set {env_hint})",
                attempts=[f"{slug}:{mdl}"],
            )
        t0 = time.perf_counter()
        try:
            content = _post_openai_chat(
                prompt,
                base_url=url,
                api_key=key or "ollama",
                model=mdl,
                temperature=temperature,
                timeout=timeout,
            )
            return AIChatResult(
                ok=bool(content),
                content=content,
                provider=slug,
                model=mdl,
                backend="openai_compat",
                tier="local" if tier == "local" else ("free" if mdl.endswith(":free") else "paid"),
                latency_seconds=round(time.perf_counter() - t0, 2),
                attempts=[f"{slug}:{mdl}"],
                error=None if content else "Provider returned empty completion",
            )
        except Exception as exc:
            return AIChatResult(
                ok=False,
                provider=slug,
                model=mdl,
                backend="openai_compat",
                tier=tier,
                latency_seconds=round(time.perf_counter() - t0, 2),
                error=f"{type(exc).__name__}: {exc}",
                attempts=[f"{slug}:{mdl}"],
            )

    def _run_g4f() -> AIChatResult:
        if not is_g4f_available():
            return AIChatResult(
                ok=False,
                provider=eff_provider or "g4f",
                model=eff_model,
                backend="g4f",
                tier="free",
                error='Optional `g4f` backend is not installed. Run: uv add "wb-sdk-pro[ai]"',
            )
        targets = (
            [eff_provider]
            if (explicit_g4f and not g4f_auto_requested)
            else _g4f_fallback_order()[: max(1, g4f_fallback_limit)]
        )
        if not targets:
            return AIChatResult(
                ok=False,
                provider="g4f",
                backend="g4f",
                tier="free",
                error="No working free g4f providers available right now.",
            )

        attempts: List[str] = []
        last_err = ""
        t_start = time.perf_counter()
        per_timeout = min(timeout, 15.0)
        for p_name in targets:
            t0 = time.perf_counter()
            try:
                content, used_p, used_m = _call_g4f_provider(
                    p_name, prompt, model=eff_model, timeout=per_timeout
                )
                attempts.append(f"g4f:{used_p}/{used_m}")
                return AIChatResult(
                    ok=True,
                    content=content,
                    provider=used_p,
                    model=used_m,
                    backend="g4f",
                    tier="free",
                    latency_seconds=round(time.perf_counter() - t0, 2),
                    attempts=attempts,
                )
            except Exception as exc:
                attempts.append(f"g4f:{p_name} ({type(exc).__name__})")
                last_err = f"{type(exc).__name__}: {exc}"

        return AIChatResult(
            ok=False,
            provider=targets[0],
            model=eff_model,
            backend="g4f",
            tier="free",
            latency_seconds=round(time.perf_counter() - t_start, 2),
            error=last_err or "All candidate free g4f providers failed",
            attempts=attempts,
        )

    if eff_mode == "paid":
        return _run_openai_compat()

    if eff_mode == "local":
        eff_provider = eff_provider or "ollama"
        return _run_openai_compat()

    if eff_mode == "free":
        if preset_slug == "ollama" or preset_slug == "lmstudio" or (eff_url and _is_local_url(eff_url)):
            return _run_openai_compat()
        if (preset_slug in ("openrouter", "groq", "gemini") or eff_model.endswith(":free")) and (
            eff_key or _env_key_for_preset(preset_slug)
        ):
            return _run_openai_compat()
        return _run_g4f()

    # Auto mode: respect explicit provider first -> configured paid/local key -> free g4f pool
    if preset_slug:
        return _run_openai_compat()
    if explicit_g4f or g4f_auto_requested:
        return _run_g4f()
    if eff_key or (eff_url and _is_local_url(eff_url)) or _detect_any_paid_env():
        return _run_openai_compat()
    return _run_g4f()


def test_ai_provider(
    provider: Optional[str] = None,
    *,
    mode: str = "auto",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    prompt: str = "Ответь одним словом: Работает",
    timeout: float = 12.0,
) -> AIProviderResult:
    """
    Run a single health check / test prompt on a free (`g4f` / `ollama`) or paid
    (`openai`, `deepseek`, `openrouter`, `proxyapi`, `groq`, custom) AI provider.
    """
    res = generate_completion(
        prompt,
        mode=mode,
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        g4f_fallback_limit=1,
    )
    if res.ok:
        return AIProviderResult(
            provider=res.provider,
            backend=res.backend,
            tier=res.tier,
            model=res.model,
            success=True,
            response_text=res.content,
            latency_seconds=res.latency_seconds,
        )

    err_text = res.error or "Unknown error"
    err_type, _, err_msg = err_text.partition(": ")
    if not err_msg:
        err_msg = err_type
        err_type = "AIError"
    return AIProviderResult(
        provider=res.provider or (provider or "auto"),
        backend=res.backend or "auto",
        tier=res.tier or mode,
        model=res.model or (model or ""),
        success=False,
        latency_seconds=res.latency_seconds,
        error_type=err_type,
        error_message=err_msg,
        hint=_diagnose_ai_error(err_type, err_msg),
    )


def quick_scan_ai_providers(timeout: float = 6.0) -> List[AIProviderResult]:
    """
    Scan popular free `g4f` providers + configured local/paid OpenAI-compatible presets concurrently
    using daemon threads (matches `testg4f --quick-scan` without exit hangs).
    """
    tasks: List[Tuple[str, str, Optional[str]]] = []
    if is_g4f_available():
        existing = {p.id.lower(): p for p in list_g4f_providers()}
        for candidate in FREE_G4F_CANDIDATES:
            info = existing.get(candidate.lower())
            if info:
                tasks.append((f"g4f:{info.id}", "free", info.default_model or None))

    for p in list_ai_providers(include_g4f=False):
        if p.configured and p.tier in ("paid", "hybrid"):
            tasks.append((p.id, "paid", p.default_model))

    results: List[Optional[AIProviderResult]] = [None] * len(tasks)
    sem = threading.Semaphore(6)

    def _probe(idx: int, prov: str, mode_name: str, mdl: Optional[str]) -> None:
        with sem:
            results[idx] = test_ai_provider(
                prov,
                mode=mode_name,
                model=mdl,
                prompt="Ответь 1 словом: ОК",
                timeout=timeout,
            )

    threads: List[threading.Thread] = []
    for idx, (prov, mode_name, mdl) in enumerate(tasks):
        t = threading.Thread(target=_probe, args=(idx, prov, mode_name, mdl), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join(timeout=timeout + 2.0)

    return [r for r in results if r is not None]


def parse_json_payload(raw_content: str) -> Dict[str, Any]:
    """Extract JSON object safely from LLM markdown/fenced responses."""
    import json

    match = re.search(r"\{.*\}", raw_content, re.DOTALL)
    return json.loads(match.group(0) if match else raw_content)


class AIClient:
    """High-level reusable client supporting both Free (`g4f`/Ollama) and Paid LLM providers."""

    def __init__(
        self,
        *,
        mode: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 25.0,
    ) -> None:
        self.mode = mode or os.environ.get("WB_AI_MODE") or "auto"
        self.provider = provider or os.environ.get("WB_AI_PROVIDER") or None
        self.model = model or os.environ.get("WB_AI_MODEL") or None
        self.api_key = api_key
        self.base_url = base_url or os.environ.get("WB_AI_BASE_URL") or None
        self.timeout = timeout

    def chat(self, prompt: str, *, temperature: float = 0.2) -> AIChatResult:
        """Generate completion using configured Free/Local/Paid provider & fallback rules."""
        return generate_completion(
            prompt,
            mode=self.mode,
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=temperature,
            timeout=self.timeout,
        )

    def list_providers(
        self,
        *,
        tier: str = "all",
        only_working: bool = False,
        only_free: bool = False,
        search_query: str = "",
    ) -> List[AIProviderInfo]:
        """List available free and paid AI providers."""
        return list_ai_providers(
            tier=tier,
            only_working=only_working,
            only_free=only_free,
            search_query=search_query,
        )

    def test_provider(
        self,
        provider: Optional[str] = None,
        *,
        model: Optional[str] = None,
        timeout: float = 12.0,
    ) -> AIProviderResult:
        """Benchmark and health-check a provider."""
        return test_ai_provider(
            provider or self.provider,
            mode=self.mode,
            model=model or self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )
