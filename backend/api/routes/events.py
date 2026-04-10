"""POST /events/session and POST /events/transaction.

Phase 2: validates shape, publishes to Kafka, returns 202.

We intentionally do NOT write to Postgres here — the consumer does that.
Keeping the ingest endpoint dumb-and-fast lets us absorb bursts without
blocking the bank's frontend when the DB is under pressure.
"""

from typing import Any, Literal

import structlog
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from backend.kafka import topics
from backend.kafka.producer import publish

log = structlog.get_logger()
router = APIRouter()


class SessionEvent(BaseModel):
    type: Literal["mousemove", "click", "keydown", "scroll", "focus", "blur"]
    ts_ms: int = Field(..., description="Milliseconds since session start")
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
    try:
        publish(
            topics.SESSION_EVENTS_RAW,
            value=batch.model_dump(),
            key=batch.session_id,  # key by session so all of one session's events land on one partition
        )
    except Exception:  # noqa: BLE001
        # Never bubble a Kafka failure back to the bank frontend — we'd rather
        # lose a batch of mouse events than fail the user's session. Alerting
        # on broker down lives in Grafana (phase 6).
        log.exception(
            "events.session.publish_failed",
            session_id=batch.session_id,
            event_count=len(batch.events),
        )

    log.info(
        "events.session.received",
        session_id=batch.session_id,
        user_id=batch.user_id,
        event_count=len(batch.events),
    )
    return {"status": "received", "event_count": len(batch.events)}


@router.post("/events/transaction", status_code=status.HTTP_202_ACCEPTED)
async def ingest_transaction_event(tx: TransactionEvent) -> dict[str, Any]:
    try:
        publish(
            topics.TRANSACTION_EVENTS_RAW,
            value=tx.model_dump(),
            key=tx.session_id,
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "events.transaction.publish_failed",
            tx_id=tx.tx_id,
            session_id=tx.session_id,
        )

    log.info("events.transaction.received", tx_id=tx.tx_id, session_id=tx.session_id)
    return {"status": "received", "tx_id": tx.tx_id}
