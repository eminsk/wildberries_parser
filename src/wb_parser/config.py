"""
Configuration defaults, regional destination codes, and settings helpers for WB SDK.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

TELEGRAM_CHANNEL_URL = "https://t.me/avito_sdk_pro"
DOCS_URL = "https://eminsk.github.io/"
ISSUES_URL = "https://github.com/eminsk/wildberries_parser/issues"
REPO_URL = "https://github.com/eminsk/wildberries_parser"
UPSTREAMS_URL = "https://cdn.wbbasket.ru/api/v3/upstreams"

# Well-known Wildberries warehouse/delivery destination IDs (dest parameter)
DEST_CODES: Dict[str, int] = {
    "Москва": -1257786,
    "Санкт-Петербург": -1198055,
    "Казань": -2133464,
    "Екатеринбург": -5818883,
    "Новосибирск": -364763,
    "Краснодар": -1281648,
    "Минск": 123585857,
    "Алматы": 85,
}
DEFAULT_DEST = DEST_CODES["Москва"]


@dataclass
class WBConfig:
    """Configuration container for CLI, GUI, and programmatic WB scraping."""

    targets: List[str] = field(default_factory=list)
    dest: int = DEFAULT_DEST
    currency: str = "rub"
    lang: str = "ru"
    proxy: Optional[str] = None
    proxy_change_url: Optional[str] = None
    mobileproxy_key: Optional[str] = None
    cookies: Optional[str] = None
    wbaas_token: Optional[str] = None
    min_price: int = 0
    max_price: int = 999_999_999
    min_discount: int = 0
    min_rating: float = 0.0
    white_keywords: List[str] = field(default_factory=list)
    black_keywords: List[str] = field(default_factory=list)
    with_feedbacks: bool = True
    enrich_cdn: bool = True
    max_pages: int = 5
    limit: int = 200
    interval_sec: int = 60
    pause_sec: float = 1.5
    timeout: float = 12.0
    force_ipv4: bool = True
    tg_token: Optional[str] = None
    tg_chat_id: Optional[str] = None
    tg_proxy: Optional[str] = None
    tracker_db: str = "wb_prices.db"
    output_dir: Path = Path("result")

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "WBConfig":
        """Load configuration from JSON or TOML file."""
        cfg_path = Path(path)
        if not cfg_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {cfg_path}")

        suffix = cfg_path.suffix.lower()
        if suffix == ".json":
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        elif suffix == ".toml":
            try:
                import tomllib
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("tomllib requires Python 3.11+") from exc
            raw = tomllib.loads(cfg_path.read_bytes().decode("utf-8"))
            raw = raw.get("wildberries", raw) if isinstance(raw, dict) else {}
        else:
            raise ValueError(f"Unsupported config format: {suffix}")

        cfg = cls()
        for key, value in raw.items():
            if hasattr(cfg, key):
                if key == "output_dir":
                    value = Path(value)
                setattr(cfg, key, value)
        return cfg

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config into a JSON-safe dictionary."""
        data = dict(self.__dict__)
        data["output_dir"] = str(self.output_dir)
        return data
