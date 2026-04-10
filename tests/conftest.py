"""Shared test fixtures.

Installs a fake Kafka producer by default so unit tests don't need
librdkafka / a running broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from backend.kafka import producer as kafka_producer


@dataclass
class FakeProducer:
    """Records every produce() call. Mirrors the ProducerLike Protocol."""

    published: list[dict[str, Any]] = field(default_factory=list)

    def produce(self, topic: str, value: bytes, key: bytes | None = None) -> None:
        self.published.append({"topic": topic, "value": value, "key": key})

    def poll(self, timeout: float) -> int:
        return 0

    def flush(self, timeout: float = -1) -> int:
        return 0


@pytest.fixture(autouse=True)
def fake_kafka():
    """Replace the global producer with a FakeProducer for every test."""
    fake = FakeProducer()
    kafka_producer.set_producer(fake)
    yield fake
    kafka_producer.set_producer(None)
