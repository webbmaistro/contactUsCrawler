"""
Track daily Geoapify credit usage and enforce cap so we stay within free tier.
Usage file: lead_gen_usage.json (date + geoapify_credits). Resets at midnight (local date).
"""

import json
from datetime import date
from pathlib import Path

from lead_gen import config


def _usage_path() -> Path:
    """Path to usage file (project root when run from repo)."""
    p = Path(config.USAGE_FILE)
    if not p.is_absolute():
        # Default: same dir as lead_gen package's parent (project root)
        p = Path(__file__).resolve().parent.parent / config.USAGE_FILE
    return p


def _load() -> tuple[str, int]:
    """Return (today_str, credits_used). Resets if date is not today."""
    path = _usage_path()
    today_str = date.today().isoformat()
    if not path.exists():
        return today_str, 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("date") != today_str:
            return today_str, 0
        return today_str, int(data.get("geoapify_credits", 0))
    except (json.JSONDecodeError, OSError):
        return today_str, 0


def _save(today_str: str, credits: int):
    path = _usage_path()
    try:
        path.write_text(
            json.dumps({"date": today_str, "geoapify_credits": credits}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass  # Don't fail the run if we can't write usage


def get_geoapify_credits_used_today() -> int:
    """Credits used today (so far)."""
    _, credits = _load()
    return credits


def can_use_geoapify_credits(amount: int = 1) -> bool:
    """True if we can use `amount` more credits today without exceeding the cap."""
    cap = getattr(config, "GEOAPIFY_DAILY_CREDIT_CAP", 0)
    if cap <= 0:
        return True
    today_str, used = _load()
    return (used + amount) <= cap


def record_geoapify_credits(amount: int = 1):
    """Record that we used `amount` Geoapify credits today."""
    today_str, used = _load()
    used += amount
    _save(today_str, used)
