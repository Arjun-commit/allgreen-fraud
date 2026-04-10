"""Pure event handlers — no Kafka, no framework imports.

Lives separately from kafka_consumer.py so unit tests can exercise the
persistence logic without needing librdkafka or a running broker.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session as OrmSession

from backend.db.models import Session as SessionRow
from backend.db.models import SessionEventRow, Transaction, User

log = structlog.get_logger()


def get_or_create_user(db: OrmSession, bank_user_id: str) -> User:
    user = db.query(User).filter(User.bank_user_id == bank_user_id).one_or_none()
    if user is None:
        user = User(bank_user_id=bank_user_id)
        db.add(user)
        db.flush()
    return user


def get_or_create_session(
    db: OrmSession, session_token: str, user: User
) -> SessionRow:
    sess = (
        db.query(SessionRow)
        .filter(SessionRow.session_token == session_token)
        .one_or_none()
    )
    if sess is None:
        sess = SessionRow(session_token=session_token, user_id=user.id)
        db.add(sess)
        db.flush()
    return sess


def handle_session_events(db: OrmSession, payload: dict[str, Any]) -> int:
    """Persist a batch of session events. Returns rows written."""
    session_token = payload["session_id"]
    bank_user_id = payload["user_id"]
    events = payload.get("events", [])

    user = get_or_create_user(db, bank_user_id)
    sess = get_or_create_session(db, session_token, user)

    rows = [
        SessionEventRow(
            session_id=sess.id,
            event_type=e["type"],
            event_data={
                k: v
                for k, v in e.items()
                if k not in {"type", "ts_ms"} and v is not None
            },
            timestamp_ms=int(e["ts_ms"]),
        )
        for e in events
    ]
    if rows:
        db.bulk_save_objects(rows)
    return len(rows)


def handle_transaction(db: OrmSession, payload: dict[str, Any]) -> Transaction | None:
    """Persist a transaction tied to an existing session.

    Returns None if the session hasn't been seen yet (out-of-order delivery);
    the caller should commit the offset anyway because we'd never catch up.
    """
    session_token = payload["session_id"]
    sess = (
        db.query(SessionRow)
        .filter(SessionRow.session_token == session_token)
        .one_or_none()
    )
    if sess is None:
        log.warning("tx.session_missing", session_token=session_token)
        return None

    tx = Transaction(
        id=uuid.UUID(payload["tx_id"]) if _is_uuid(payload["tx_id"]) else uuid.uuid4(),
        session_id=sess.id,
        user_id=sess.user_id,
        amount=payload["amount"],
        currency=payload.get("currency", "USD"),
        payee_account=payload["payee_account"],
        payee_name=payload.get("payee_name"),
        payee_bank_code=payload.get("payee_bank_code"),
        is_new_payee=bool(payload.get("is_new_payee", False)),
        transfer_type=payload.get("transfer_type", "domestic"),
    )
    db.add(tx)
    return tx


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(s)
        return True
    except (ValueError, TypeError):
        return False
