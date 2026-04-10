"""Tiny synthetic event generator for tests + local experiments.

Not the 1000/100 dataset generator the blueprint mentions for phase 3 —
that one lives under ml/ and uses this as a building block.
"""

from __future__ import annotations

import random
from typing import Literal


def generate_normal_session(
    session_id: str = "sess-normal",
    user_id: str = "user-1",
    duration_ms: int = 60_000,
    seed: int = 0,
) -> list[dict]:
    """A plausible, non-fraud session: mousemoves with natural variance,
    some clicks, some typing, occasional small scrolls."""
    rng = random.Random(seed)
    events: list[dict] = []
    t = 0
    x, y = 500, 400

    while t < duration_ms:
        # Mouse movement in small-ish deltas, at ~100ms cadence.
        x += rng.randint(-40, 40)
        y += rng.randint(-30, 30)
        events.append({"type": "mousemove", "x": x, "y": y, "ts_ms": t})
        t += rng.randint(80, 160)

        # Occasional click
        if rng.random() < 0.05:
            events.append({"type": "click", "x": x, "y": y, "ts_ms": t})
            t += rng.randint(50, 200)

        # Typing burst
        if rng.random() < 0.08:
            for _ in range(rng.randint(3, 10)):
                events.append(
                    {
                        "type": "keydown",
                        "key_code": rng.randint(65, 90),
                        "dwell_ms": rng.randint(60, 140),
                        "ts_ms": t,
                    }
                )
                t += rng.randint(90, 180)  # normal typing rhythm

        # A scroll every once in a while
        if rng.random() < 0.04:
            events.append(
                {"type": "scroll", "depth": min(1.0, t / duration_ms), "ts_ms": t}
            )
            t += rng.randint(100, 300)

    return events


def generate_coached_session(
    session_id: str = "sess-coached",
    user_id: str = "user-1",
    duration_ms: int = 120_000,
    seed: int = 1,
) -> list[dict]:
    """Approximation of a coached / scammed session.

    Key signals we want the features to pick up on:
      - long pauses between mouse movements ("hold on, what do I click next")
      - very low velocity variance (careful, deliberate movement)
      - pasted values rather than typed (bursts of keydowns <50ms apart)
      - near-zero backspace rate (people don't correct dictated values)
    """
    rng = random.Random(seed)
    events: list[dict] = []
    t = 0
    x, y = 600, 500

    while t < duration_ms:
        # Deliberate, small, slow mousemoves
        x += rng.randint(-10, 10)
        y += rng.randint(-8, 8)
        events.append({"type": "mousemove", "x": x, "y": y, "ts_ms": t})
        t += rng.randint(200, 280)  # slower cadence

        # A long pause every now and then ("waiting on the scammer")
        if rng.random() < 0.10:
            t += rng.randint(3000, 8000)  # 3-8 second pause

        # Paste bursts — 5+ keydowns within a few ms
        if rng.random() < 0.05:
            burst_t = t
            for _ in range(rng.randint(5, 12)):
                events.append(
                    {
                        "type": "keydown",
                        "key_code": rng.randint(48, 57),  # digits — account numbers
                        "dwell_ms": rng.randint(10, 30),
                        "ts_ms": burst_t,
                    }
                )
                burst_t += rng.randint(1, 5)  # <50ms spans = paste
            t = burst_t + rng.randint(500, 2000)

    return events


def make_session_batch(
    kind: Literal["normal", "coached"] = "normal",
    session_id: str = "sess-1",
    user_id: str = "user-1",
) -> dict:
    """Wrap events in the SessionEventBatch shape the API expects."""
    events = (
        generate_normal_session(session_id=session_id, user_id=user_id)
        if kind == "normal"
        else generate_coached_session(session_id=session_id, user_id=user_id)
    )
    return {"session_id": session_id, "user_id": user_id, "events": events}
