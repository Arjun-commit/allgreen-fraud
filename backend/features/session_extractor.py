"""Behavioral feature extraction from raw session events.

Phase 2. Left as a placeholder so the import graph is stable and the
feature-name constants can already be referenced elsewhere.
"""

# The full list lives in the blueprint §6.1. Kept here as the source of truth
# that downstream code (model input schema, feature store keys) pulls from.
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


def extract_session_features(events: list[dict]) -> dict[str, float]:
    """Return a dict keyed on BEHAVIORAL_FEATURE_NAMES.

    TODO(phase-2): real implementation. For now this returns zeros so the
    LSTM input pipeline has something to shape-check against.
    """
    return {name: 0.0 for name in BEHAVIORAL_FEATURE_NAMES}
