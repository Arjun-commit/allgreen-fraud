"""SQLAlchemy ORM models.

Verbose column names on purpose -- this touches money and compliance.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass



class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    bank_user_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    baseline_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="user")



class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    session_token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    device_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    friction_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
    events: Mapped[list[SessionEventRow]] = relationship(back_populates="session")

    __table_args__ = (
        CheckConstraint(
            "friction_level IS NULL OR friction_level IN ('none','soft','hard')",
            name="ck_sessions_friction_level",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('allowed','abandoned','blocked')",
            name="ck_sessions_outcome",
        ),
    )


# Named SessionEventRow to avoid collision with the pydantic type in events.py

class SessionEventRow(Base):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    event_type: Mapped[str] = mapped_column(String(32))
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)

    session: Mapped[Session] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_session_events_session_time", "session_id", "timestamp_ms"),
    )



class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    payee_account: Mapped[str] = mapped_column(String(64))
    payee_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payee_bank_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_new_payee: Mapped[bool] = mapped_column(Boolean, default=False)
    transfer_type: Mapped[str] = mapped_column(String(32), default="domestic")

    behavioral_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    friction_applied: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','blocked','under_review')",
            name="ck_transactions_status",
        ),
        CheckConstraint(
            "transfer_type IN ('domestic','international','crypto')",
            name="ck_transactions_transfer_type",
        ),
        Index("ix_transactions_created_at", "created_at"),
        Index("ix_transactions_user_created", "user_id", "created_at"),
    )



class FrictionEvent(Base):
    __tablename__ = "friction_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sessions.id"))
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True
    )
    friction_type: Mapped[str] = mapped_column(String(50))
    trigger_score: Mapped[float] = mapped_column(Float)
    user_response: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )



class AnalystCase(Base):
    __tablename__ = "analyst_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"))
    assigned_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','investigating','closed_fraud','closed_legit')",
            name="ck_analyst_cases_status",
        ),
    )



class PendingChange(Base):
    __tablename__ = "pending_changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    change_type: Mapped[str] = mapped_column(String(32))  # 'thresholds', etc.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    requested_by: Mapped[str] = mapped_column(String(64))
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')",
            name="ck_pending_changes_status",
        ),
    )
