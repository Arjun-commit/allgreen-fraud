"""GET /friction/{session_id} — polled by the bank frontend.

The bank's web app polls this every few seconds after a transfer is
initiated to check if friction was applied (and if so, which kind).
This reads from the Redis cache that the scoring pipeline writes to.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter

from backend.store.redis_store import get_cached_friction

log = structlog.get_logger()
router = APIRouter()


@router.get("/friction/{session_id}")
async def get_friction(session_id: str) -> dict[str, Any]:
    cached = get_cached_friction(session_id)

    if cached is None:
        return {
            "session_id": session_id,
            "friction": None,
            "risk_score": None,
            "risk_level": None,
        }

    return {
        "session_id": session_id,
        "friction": {
            "type": cached.get("friction_type", "none"),
            "payload": cached.get("payload"),
        },
        "risk_score": cached.get("risk_score"),
        "risk_level": cached.get("risk_level"),
        "transaction_id": cached.get("transaction_id"),
    }
