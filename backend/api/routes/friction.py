"""GET /friction/{session_id} — polled by the bank frontend."""

import structlog
from fastapi import APIRouter

log = structlog.get_logger()
router = APIRouter()


@router.get("/friction/{session_id}")
async def get_friction(session_id: str) -> dict:
    # STUB. Real version (phase 4) reads latest friction decision from Redis
    # or the DB for this session.
    log.debug("friction.get", session_id=session_id)
    return {"session_id": session_id, "friction": None, "updated_at": None}
