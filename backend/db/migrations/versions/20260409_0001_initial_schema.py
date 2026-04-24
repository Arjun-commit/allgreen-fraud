"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-09

Creates: users, sessions, session_events, transactions, friction_events, analyst_cases.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Required for gen_random_uuid() on older PG installs. PG15 has it built-in
    # via pgcrypto; cheap insurance to enable it explicitly.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bank_user_id", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("baseline_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("session_token", sa.String(128), nullable=False, unique=True),
        sa.Column("device_hash", sa.String(64)),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("risk_score", sa.Float()),
        sa.Column("friction_level", sa.String(20)),
        sa.Column("outcome", sa.String(20)),
        sa.CheckConstraint(
            "friction_level IS NULL OR friction_level IN ('none','soft','hard')",
            name="ck_sessions_friction_level",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('allowed','abandoned','blocked')",
            name="ck_sessions_outcome",
        ),
    )

    op.create_table(
        "session_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id")),
        sa.Column("event_type", sa.String(32)),
        sa.Column(
            "event_data",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("timestamp_ms", sa.BigInteger()),
    )
    op.create_index(
        "ix_session_events_session_time",
        "session_events",
        ["session_id", "timestamp_ms"],
    )

    op.create_table(
        "transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("payee_account", sa.String(64), nullable=False),
        sa.Column("payee_name", sa.String(128)),
        sa.Column("payee_bank_code", sa.String(32)),
        sa.Column("is_new_payee", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("transfer_type", sa.String(32), server_default="domestic"),
        sa.Column("behavioral_score", sa.Float()),
        sa.Column("context_score", sa.Float()),
        sa.Column("final_risk_score", sa.Float()),
        sa.Column("friction_applied", sa.String(20)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','approved','blocked','under_review')",
            name="ck_transactions_status",
        ),
        sa.CheckConstraint(
            "transfer_type IN ('domestic','international','crypto')",
            name="ck_transactions_transfer_type",
        ),
    )
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])
    op.create_index(
        "ix_transactions_user_created", "transactions", ["user_id", "created_at"]
    )

    op.create_table(
        "friction_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id")),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id"),
            nullable=True,
        ),
        sa.Column("friction_type", sa.String(50)),
        sa.Column("trigger_score", sa.Float()),
        sa.Column("user_response", sa.String(20)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )

    op.create_table(
        "analyst_cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id")
        ),
        sa.Column("assigned_to", sa.String(64)),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('open','investigating','closed_fraud','closed_legit')",
            name="ck_analyst_cases_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("analyst_cases")
    op.drop_table("friction_events")
    op.drop_index("ix_transactions_user_created", table_name="transactions")
    op.drop_index("ix_transactions_created_at", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_session_events_session_time", table_name="session_events")
    op.drop_table("session_events")
    op.drop_table("sessions")
    op.drop_table("users")
