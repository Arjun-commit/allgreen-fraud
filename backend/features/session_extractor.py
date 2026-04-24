"""Compute behavioral features from raw session events.

Event shape (as produced by the browser SDK):
    {"type": "mousemove"|"click"|"keydown"|"scroll"|"focus"|"blur",
     "ts_ms": int,
     "x": int?, "y": int?,
     "key_code": int?, "dwell_ms": int?,
     "depth": float?}

A few features can't be derived from events alone (device identity, VPN,
time-of-day in the user's timezone, page-level context). Those come in via
the `context` dict and default to sensible no-ops when missing. The caller
(the consumer or the /score path) is responsible for filling context from
the user profile and request headers.

Keys returned here must exactly match BEHAVIORAL_FEATURE_NAMES — downstream
code builds input tensors by iterating that tuple in order.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

BEHAVIORAL_FEATURE_NAMES: tuple[str, ...] = (
    "mouse_avg_velocity",
    "mouse_velocity_std",
    "mouse_pause_count",
    "mouse_longest_pause_ms",
    "click_dwell_avg_ms",
    "click_dwell_std",
    "keystroke_interval_avg_ms",
    "keystroke_interval_std",
    "backspace_ratio",
    "copy_paste_detected",
    "confirmation_page_dwell_ms",
    "review_scroll_depth",
    "form_revisit_count",
    "session_duration_ms",
    "time_of_day_hour",
    "day_of_week",
    "is_new_device",
    "vpn_detected",
)

MOUSE_PAUSE_THRESHOLD_MS = 2000  # >2s between mousemoves = a pause
BACKSPACE_KEY_CODE = 8


@dataclass
class _MouseStats:
    avg_velocity: float
    velocity_std: float
    pause_count: int
    longest_pause_ms: int


def _mean(xs: Iterable[float]) -> float:
    xs_list = list(xs)
    return sum(xs_list) / len(xs_list) if xs_list else 0.0


def _stddev(xs: Iterable[float]) -> float:
    xs_list = list(xs)
    if len(xs_list) < 2:
        return 0.0
    m = _mean(xs_list)
    var = sum((x - m) ** 2 for x in xs_list) / (len(xs_list) - 1)
    return math.sqrt(var)


def _mouse_stats(mousemoves: list[dict]) -> _MouseStats:
    """Velocity in px/s, plus pause detection. Returns zeros on insufficient data."""
    if len(mousemoves) < 2:
        return _MouseStats(0.0, 0.0, 0, 0)

    velocities: list[float] = []
    pause_count = 0
    longest_pause = 0

    for prev, cur in zip(mousemoves, mousemoves[1:], strict=False):
        dt_ms = cur["ts_ms"] - prev["ts_ms"]
        if dt_ms <= 0:
            continue
        dx = (cur.get("x") or 0) - (prev.get("x") or 0)
        dy = (cur.get("y") or 0) - (prev.get("y") or 0)
        dist = math.sqrt(dx * dx + dy * dy)
        velocities.append(dist / (dt_ms / 1000.0))

        if dt_ms > MOUSE_PAUSE_THRESHOLD_MS:
            pause_count += 1
            if dt_ms > longest_pause:
                longest_pause = dt_ms

    return _MouseStats(
        avg_velocity=_mean(velocities),
        velocity_std=_stddev(velocities),
        pause_count=pause_count,
        longest_pause_ms=longest_pause,
    )


def _click_dwell_stats(clicks: list[dict]) -> tuple[float, float]:
    """Click dwell (mousedown->mouseup duration) if the SDK captured it.

    The SDK doesn't emit click dwell yet -- returns zeros until we add
    mousedown/mouseup pair tracking.
    """
    dwells = [c["dwell_ms"] for c in clicks if c.get("dwell_ms") is not None]
    return _mean(dwells), _stddev(dwells)


def _keystroke_stats(keydowns: list[dict]) -> tuple[float, float]:
    """Mean + stddev of inter-keystroke intervals."""
    if len(keydowns) < 2:
        return 0.0, 0.0
    intervals = [
        b["ts_ms"] - a["ts_ms"]
        for a, b in zip(keydowns, keydowns[1:], strict=False)
        if b["ts_ms"] >= a["ts_ms"]
    ]
    return _mean(intervals), _stddev(intervals)


def _backspace_ratio(keydowns: list[dict]) -> float:
    if not keydowns:
        return 0.0
    backs = sum(1 for k in keydowns if k.get("key_code") == BACKSPACE_KEY_CODE)
    return backs / len(keydowns)


def _copy_paste_detected(keydowns: list[dict]) -> bool:
    """Heuristic: >=3 keystrokes in <50ms total is almost certainly a paste.

    TODO: add explicit paste detection via the `paste` event once the SDK
    supports clipboard events.
    """
    if len(keydowns) < 3:
        return False
    fast_bursts = 0
    for a, _b, c in zip(keydowns, keydowns[1:], keydowns[2:], strict=False):
        span = c["ts_ms"] - a["ts_ms"]
        if 0 <= span < 50:
            fast_bursts += 1
    return fast_bursts > 0


def _session_duration(events: list[dict]) -> int:
    if not events:
        return 0
    ts = [e["ts_ms"] for e in events]
    return max(ts) - min(ts)


def _max_scroll_depth(scrolls: list[dict]) -> float:
    depths = [s["depth"] for s in scrolls if s.get("depth") is not None]
    return max(depths) if depths else 0.0


def extract_session_features(
    events: list[dict], context: dict[str, Any] | None = None
) -> dict[str, float]:
    """Return a dict keyed exactly on BEHAVIORAL_FEATURE_NAMES.

    `context` may include:
      - time_of_day_hour (int, 0-23 in user's timezone)
      - day_of_week (int, 0=Mon)
      - is_new_device (bool)
      - vpn_detected (bool)
      - confirmation_page_dwell_ms (int)
      - form_revisit_count (int)

    Anything missing defaults to 0 / False.
    """
    ctx = context or {}
    by_type: dict[str, list[dict]] = {}
    for e in events:
        by_type.setdefault(e["type"], []).append(e)
    # Sort each bucket by ts_ms once so downstream helpers can assume order.
    for bucket in by_type.values():
        bucket.sort(key=lambda e: e["ts_ms"])

    mousemoves = by_type.get("mousemove", [])
    clicks = by_type.get("click", [])
    keydowns = by_type.get("keydown", [])
    scrolls = by_type.get("scroll", [])

    ms = _mouse_stats(mousemoves)
    click_avg, click_std = _click_dwell_stats(clicks)
    ks_avg, ks_std = _keystroke_stats(keydowns)

    return {
        "mouse_avg_velocity": ms.avg_velocity,
        "mouse_velocity_std": ms.velocity_std,
        "mouse_pause_count": float(ms.pause_count),
        "mouse_longest_pause_ms": float(ms.longest_pause_ms),
        "click_dwell_avg_ms": click_avg,
        "click_dwell_std": click_std,
        "keystroke_interval_avg_ms": ks_avg,
        "keystroke_interval_std": ks_std,
        "backspace_ratio": _backspace_ratio(keydowns),
        "copy_paste_detected": float(_copy_paste_detected(keydowns)),
        "confirmation_page_dwell_ms": float(ctx.get("confirmation_page_dwell_ms", 0)),
        "review_scroll_depth": _max_scroll_depth(scrolls),
        "form_revisit_count": float(ctx.get("form_revisit_count", 0)),
        "session_duration_ms": float(_session_duration(events)),
        "time_of_day_hour": float(ctx.get("time_of_day_hour", 0)),
        "day_of_week": float(ctx.get("day_of_week", 0)),
        "is_new_device": float(bool(ctx.get("is_new_device", False))),
        "vpn_detected": float(bool(ctx.get("vpn_detected", False))),
    }
