"""POST /events/session and POST /events/transaction.

Phase 1: accepts the payload, validates the shape, and returns 'received'.
In phase 2 this will publish to Kafka (`session.events.raw` /
`transaction.events.raw`).
"""

from typing import Any, Literal

import structlog
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

log = structlog.get_logger()
router = APIRouter()


class SessionEvent(BaseModel):
    type: Literal["mousemove", "click", "keydown", "scroll", "focus", "blur"]
    ts_ms: int = Field(..., description="Milliseconds since session start")
    # Type-specific fields live in extras so we don't have to fork the schema per event.
    # We'll add stricter per-type validation once the SDK is stable.
    x: int | None = None
    y: int | None = None
    key_code: int | None = None
    dwell_ms: int | None = None
    depth: float | None = None


class SessionEventBatch(BaseModel):
    session_id: str
    user_id: str
    events: list[SessionEvent]


class TransactionEvent(BaseModel):
    tx_id: str
    session_id: str
    amount: float
    currency: str = "USD"
    payee_account: str
    payee_name: str | None = None
    payee_bank_code: str | None = None
    transfer_type: Literal["domestic", "international", "crypto"] = "domestic"
    is_new_payee: bool = False


@router.post("/events/session", status_code=status.HTTP_202_ACCEPTED)
async def ingest_session_events(batch: SessionEventBatch) -> dict[str, Any]:
    # TODO(phase-2): publish to Kafka topic `session.events.raw`
    log.info(
        "events.session.received",
        session_id=batch.session_id,
        user_id=batch.user_id,
        event_count=len(batch.events),
    )
    return {"status": "received", "event_count": len(batch.events)}


@router.post("/events/transaction", status_code=status.HTTP_202_ACCEPTED)
async def ingest_transaction_event(tx: TransactionEvent) -> dict[str, Any]:
    # TODO(phase-2): publish to Kafka topic `transaction.events.raw`
    log.info("events.transaction.received", tx_id=tx.tx_id, session_id=tx.session_id)
    return {"status": "received", "tx_id": tx.tx_id}
