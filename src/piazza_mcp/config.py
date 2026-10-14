"""Settings read from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_COOKIE_FILE = "~/.config/piazza-mcp/cookies.json"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{name} must be true or false, not {raw!r}")


def _float(name: str, default: float, low: float, high: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number, not {raw!r}") from None
    if not low <= value <= high:
        raise ValueError(f"{name} must be from {low} to {high}, not {value}")
    return value


@dataclass(frozen=True)
class Settings:
    email: str | None = None
    password: str | None = None
    cookie_file: Path = Path(DEFAULT_COOKIE_FILE).expanduser()
    anonymize_students: bool = False
    fence_content: bool = True
    keep_unread: bool = False  # mark posts unread again after the server reads them
    min_interval: float = 0.0  # seconds between Piazza requests
    cache_ttl: float = 0.0  # seconds to keep feeds and posts

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            email=os.environ.get("PIAZZA_EMAIL") or None,
            password=os.environ.get("PIAZZA_PASSWORD") or None,
            cookie_file=Path(os.environ.get("PIAZZA_COOKIE_FILE") or DEFAULT_COOKIE_FILE).expanduser(),
            anonymize_students=_bool("PIAZZA_ANONYMIZE_STUDENTS", False),
            fence_content=_bool("PIAZZA_FENCE_CONTENT", True),
            keep_unread=_bool("PIAZZA_KEEP_UNREAD", False),
            min_interval=_float("PIAZZA_MIN_INTERVAL", 0.5, 0, 10),
            cache_ttl=_float("PIAZZA_CACHE_TTL", 60, 0, 3600),
        )
