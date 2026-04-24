"""Shared test fixtures — fake Kafka and Redis for all tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from backend.kafka import producer as kafka_producer
from backend.store import redis_store


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



class FakeRedis:
    """In-memory dict that quacks like redis.Redis. Good enough for tests."""

    def __init__(self):
        self._data: dict[str, bytes] = {}

    def get(self, name: str) -> bytes | None:
        return self._data.get(name)

    def setex(self, name: str, time: int, value: str | bytes) -> bool:
        if isinstance(value, str):
            value = value.encode()
        self._data[name] = value
        return True

    def delete(self, *names: str) -> int:
        count = 0
        for n in names:
            if n in self._data:
                del self._data[n]
                count += 1
        return count

    def ping(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def fake_redis():
    """Replace the global Redis client with a FakeRedis for every test."""
    fake = FakeRedis()
    redis_store.set_redis(fake)
    yield fake
    redis_store.set_redis(None)
