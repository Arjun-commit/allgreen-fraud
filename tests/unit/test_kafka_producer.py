"""Verifies producer.publish() lands on the injected FakeProducer."""

from __future__ import annotations

import orjson

from backend.kafka import topics
from backend.kafka.producer import publish


def test_publish_records_payload(fake_kafka) -> None:
    publish(topics.SESSION_EVENTS_RAW, {"hello": "world"}, key="sess-1")

    assert len(fake_kafka.published) == 1
    entry = fake_kafka.published[0]
    assert entry["topic"] == topics.SESSION_EVENTS_RAW
    assert entry["key"] == b"sess-1"
    assert orjson.loads(entry["value"]) == {"hello": "world"}


def test_events_route_publishes_to_kafka(fake_kafka) -> None:
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    r = client.post(
        "/v1/events/session",
        json={
            "session_id": "sess-42",
            "user_id": "user-42",
            "events": [{"type": "mousemove", "ts_ms": 1, "x": 1, "y": 1}],
        },
    )
    assert r.status_code == 202

    # Exactly one publish landed on our fake, with the right topic + key.
    assert len(fake_kafka.published) == 1
    entry = fake_kafka.published[0]
    assert entry["topic"] == topics.SESSION_EVENTS_RAW
    assert entry["key"] == b"sess-42"
    decoded = orjson.loads(entry["value"])
    assert decoded["session_id"] == "sess-42"
    assert len(decoded["events"]) == 1
