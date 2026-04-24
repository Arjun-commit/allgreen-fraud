"""Redis-backed session feature store + friction cache.

Graceful fallback: if Redis is down, scoring recomputes from Postgres.
Tests inject a FakeRedis or None.
"""

from __future__ import annotations

from typing import Any, Protocol

import orjson
import structlog

log = structlog.get_logger()

SESSION_FEATURES_TTL = 4 * 3600  # 4 hours
FRICTION_TTL = 3600  # 1 hour


class RedisLike(Protocol):
    """Minimal interface we use from redis.Redis."""

    def get(self, name: str) -> bytes | None: ...
    def setex(self, name: str, time: int, value: str | bytes) -> bool: ...
    def delete(self, *names: str) -> int: ...


_client: RedisLike | None = None


def set_redis(client: RedisLike | None) -> None:
    global _client
    _client = client


def get_redis() -> RedisLike | None:
    global _client
    if _client is None:
        try:
            import redis as redis_lib

            from backend.config import get_settings

            settings = get_settings()
            _client = redis_lib.Redis.from_url(settings.redis_url, decode_responses=False)
            # Quick ping to verify
            _client.ping()  # type: ignore[union-attr]
        except Exception:
            log.warning("redis.connect_failed", msg="falling back to no-cache mode")
            return None
    return _client



def _features_key(session_id: str) -> str:
    return f"session:{session_id}:features"


def cache_session_features(session_id: str, features: dict[str, float]) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(_features_key(session_id), SESSION_FEATURES_TTL, orjson.dumps(features))
    except Exception:
        log.warning("redis.cache_features_failed", session_id=session_id)


def get_cached_features(session_id: str) -> dict[str, float] | None:
    r = get_redis()
    if r is None:
        return None
    try:
        data = r.get(_features_key(session_id))
        if data is None:
            return None
        return orjson.loads(data)
    except Exception:
        return None



def _friction_key(session_id: str) -> str:
    return f"session:{session_id}:friction"


def cache_friction(session_id: str, friction: dict[str, Any]) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(_friction_key(session_id), FRICTION_TTL, orjson.dumps(friction))
    except Exception:
        log.warning("redis.cache_friction_failed", session_id=session_id)


def get_cached_friction(session_id: str) -> dict[str, Any] | None:
    r = get_redis()
    if r is None:
        return None
    try:
        data = r.get(_friction_key(session_id))
        if data is None:
            return None
        return orjson.loads(data)
    except Exception:
        return None
