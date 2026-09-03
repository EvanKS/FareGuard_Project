"""Formatting + defensive client access shared by every v2 page."""
from __future__ import annotations

from typing import Any, Callable, Optional

RUPEE = "\u20b9"
DASH = "\u2014"


def safe(client: Any, method: str, default: Any = None, *args, **kwargs) -> Any:
    """Call client.<method>() and never let a page crash on a missing route."""
    fn: Optional[Callable] = getattr(client, method, None)
    if fn is None:
        return default
    try:
        result = fn(*args, **kwargs)
    except Exception:
        return default
    return default if result is None else result


def inr(value: Any, decimals: int = 0) -> str:
    try:
        return RUPEE + format(float(value), "," + "." + str(decimals) + "f")
    except (TypeError, ValueError):
        return DASH


def num(value: Any) -> str:
    try:
        return format(int(float(value)), ",")
    except (TypeError, ValueError):
        return DASH


def ms(value: Any) -> str:
    try:
        return format(float(value), ",.0f") + " ms"
    except (TypeError, ValueError):
        return DASH


def pct(value: Any, decimals: int = 1) -> str:
    try:
        return format(float(value) * 100, "." + str(decimals) + "f") + "%"
    except (TypeError, ValueError):
        return DASH
