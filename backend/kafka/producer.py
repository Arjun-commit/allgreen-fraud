"""Thin producer wrapper.

Design notes:
- Single global producer (confluent-kafka is thread-safe and recommends this).
- Lazy init so tests that don't touch Kafka don't need librdkafka installed.
- Dependency-injectable via `set_producer` for unit tests (see tests/unit/test_kafka_producer.py).
- orjson for serialization — we send a lot of these, and the stdlib json is the
  single biggest hot-path cost the last time I measured this kind of ingest.
"""

from __future__ import annotations

from typing import Any, Protocol

import orjson
import structlog

from backend.config import get_settings

log = structlog.get_logger()


class ProducerLike(Protocol):
    """Minimal interface we use from confluent_kafka.Producer."""

    def produce(self, topic: str, value: bytes, key: bytes | None = None) -> None: ...
    def poll(self, timeout: float) -> int: ...
    def flush(self, timeout: float = -1) -> int: ...


_producer: ProducerLike | None = None


def _build_default_producer() -> ProducerLike:
    # Imported lazily so unit tests don't need librdkafka.
    from confluent_kafka import Producer  # type: ignore[import-not-found]

    settings = get_settings()
    return Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "linger.ms": 5,
            "compression.type": "lz4",
            "client.id": "allgreen-api",
        }
    )


def get_producer() -> ProducerLike:
    global _producer
    if _producer is None:
        _producer = _build_default_producer()
    return _producer


def set_producer(p: ProducerLike | None) -> None:
    """Inject a producer (tests) or reset with None."""
    global _producer
    _producer = p


def _delivery_callback(err: Any, msg: Any) -> None:
    if err is not None:
        log.warning("kafka.delivery.error", error=str(err))


def publish(topic: str, value: dict, key: str | None = None) -> None:
    """Fire-and-forget publish. Callers shouldn't await delivery on the hot path."""
    p = get_producer()
    payload = orjson.dumps(value)
    p.produce(
        topic=topic,
        value=payload,
        key=key.encode() if key else None,
    )
    # Serve delivery callbacks from the producer's internal queue without
    # blocking. Non-zero timeout = bad on the hot path.
    p.poll(0)


def flush(timeout: float = 5.0) -> None:
    """Drain the producer. Call on app shutdown."""
    get_producer().flush(timeout)
