"""Unit tests for backend.features.session_extractor.

Approach: a mix of hand-crafted fixtures (so we can pin exact values) and
the synthetic generator (so we exercise the full feature dict end to end).
"""

from __future__ import annotations

import pytest

from backend.features.session_extractor import (
    BEHAVIORAL_FEATURE_NAMES,
    extract_session_features,
)
from tests.data_generator import generate_coached_session, generate_normal_session

# ---------- shape / coverage ----------

def test_output_has_every_declared_feature() -> None:
    feats = extract_session_features([])
    assert set(feats.keys()) == set(BEHAVIORAL_FEATURE_NAMES)


def test_empty_session_returns_zeros() -> None:
    feats = extract_session_features([])
    assert all(v == 0.0 for v in feats.values())


# ---------- hand-crafted fixtures ----------

def _mousemove(ts: int, x: int, y: int) -> dict:
    return {"type": "mousemove", "ts_ms": ts, "x": x, "y": y}


def test_mouse_velocity_two_point() -> None:
    # Two points 1000 ms apart, 100px of distance → 100 px/s
    events = [_mousemove(0, 0, 0), _mousemove(1000, 60, 80)]
    feats = extract_session_features(events)
    assert feats["mouse_avg_velocity"] == pytest.approx(100.0)
    # One sample → stddev falls back to 0
    assert feats["mouse_velocity_std"] == 0.0


def test_long_pause_is_counted() -> None:
    events = [
        _mousemove(0, 0, 0),
        _mousemove(500, 10, 10),
        _mousemove(5000, 20, 20),  # 4.5s gap → pause
    ]
    feats = extract_session_features(events)
    assert feats["mouse_pause_count"] == 1.0
    assert feats["mouse_longest_pause_ms"] == 4500.0


def test_backspace_ratio() -> None:
    events = [
        {"type": "keydown", "key_code": 65, "ts_ms": 0},
        {"type": "keydown", "key_code": 8, "ts_ms": 100},   # backspace
        {"type": "keydown", "key_code": 66, "ts_ms": 200},
        {"type": "keydown", "key_code": 8, "ts_ms": 300},   # backspace
    ]
    feats = extract_session_features(events)
    assert feats["backspace_ratio"] == 0.5


def test_copy_paste_detected_on_fast_burst() -> None:
    events = [
        {"type": "keydown", "key_code": 49, "ts_ms": 1000},
        {"type": "keydown", "key_code": 50, "ts_ms": 1005},
        {"type": "keydown", "key_code": 51, "ts_ms": 1010},
        {"type": "keydown", "key_code": 52, "ts_ms": 1015},
    ]
    feats = extract_session_features(events)
    assert feats["copy_paste_detected"] == 1.0


def test_copy_paste_not_triggered_by_normal_typing() -> None:
    events = [
        {"type": "keydown", "key_code": 65, "ts_ms": 0},
        {"type": "keydown", "key_code": 66, "ts_ms": 120},
        {"type": "keydown", "key_code": 67, "ts_ms": 240},
    ]
    feats = extract_session_features(events)
    assert feats["copy_paste_detected"] == 0.0


def test_scroll_depth_takes_max() -> None:
    events = [
        {"type": "scroll", "ts_ms": 100, "depth": 0.2},
        {"type": "scroll", "ts_ms": 500, "depth": 0.8},
        {"type": "scroll", "ts_ms": 900, "depth": 0.5},
    ]
    feats = extract_session_features(events)
    assert feats["review_scroll_depth"] == 0.8


def test_session_duration() -> None:
    events = [_mousemove(100, 0, 0), _mousemove(5100, 10, 10)]
    feats = extract_session_features(events)
    assert feats["session_duration_ms"] == 5000.0


# ---------- context pass-through ----------

def test_context_values_flow_through() -> None:
    ctx = {
        "time_of_day_hour": 23,
        "day_of_week": 5,
        "is_new_device": True,
        "vpn_detected": True,
        "confirmation_page_dwell_ms": 12000,
        "form_revisit_count": 3,
    }
    feats = extract_session_features([], context=ctx)
    assert feats["time_of_day_hour"] == 23.0
    assert feats["day_of_week"] == 5.0
    assert feats["is_new_device"] == 1.0
    assert feats["vpn_detected"] == 1.0
    assert feats["confirmation_page_dwell_ms"] == 12000.0
    assert feats["form_revisit_count"] == 3.0


# ---------- end-to-end sanity via synthetic generator ----------

def test_coached_vs_normal_shows_distinct_signals() -> None:
    """Not a model test — just verifies the extractor separates the
    two synthetic patterns on the signals we care about. If this ever
    flakes it probably means the extractor or the generator drifted.
    """
    normal = extract_session_features(generate_normal_session(seed=42))
    coached = extract_session_features(generate_coached_session(seed=42))

    # Coached sessions should have more/longer pauses.
    assert coached["mouse_pause_count"] >= normal["mouse_pause_count"]
    assert coached["mouse_longest_pause_ms"] >= normal["mouse_longest_pause_ms"]

    # Coached sessions should trigger the paste heuristic.
    assert coached["copy_paste_detected"] == 1.0
