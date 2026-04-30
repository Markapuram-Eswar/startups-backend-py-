"""Shared parsing helpers — mirrors startupController.js."""

from __future__ import annotations

from datetime import datetime


def to_bool(v) -> bool:
    return v is True or v == "true" or v == "on" or v == "Yes"


def to_num(v) -> float | int:
    if v == "" or v is None:
        return 0
    return float(v) if "." in str(v) else int(float(v))


def to_num_or_null(v):
    s = str(v if v is not None else "").strip().upper()
    if s == "" or s == "NA":
        return None
    try:
        n = float(v)
        return n if n == int(n) else n  # keep int-like as int for year
    except (TypeError, ValueError):
        return None


def safe_date(v, fallback=None):
    if not v:
        return fallback
    if isinstance(v, datetime):
        return v
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d.replace(tzinfo=None) if d.tzinfo else d
    except Exception:
        return fallback


def normalize_trl(trl):
    if isinstance(trl, (int, float)) and not isinstance(trl, bool):
        n = max(1, min(9, int(trl)))
        return f"TRL {n}"
    if isinstance(trl, str):
        digits = "".join(c for c in trl if c.isdigit())
        if digits:
            n = int(digits)
            if 1 <= n <= 9:
                return f"TRL {n}"
    return trl
