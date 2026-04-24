"""Threshold settings API with maker-checker approval flow.

Two-person approval for threshold changes. In-memory fallback when
Postgres isn't available.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = structlog.get_logger()
router = APIRouter()



class ThresholdChangeRequest(BaseModel):
    medium: float = Field(ge=10, le=90)
    high: float = Field(ge=20, le=95)
    critical: float = Field(ge=30, le=99)
    friction_medium: str = "awareness_prompt"
    friction_high: str = "cooling_timer"
    friction_critical: str = "callback_required"
    requested_by: str = "analyst"  # in prod, extracted from JWT


class ApprovalRequest(BaseModel):
    approved_by: str  # must differ from requested_by


class RejectRequest(BaseModel):
    rejected_by: str
    reason: str | None = None



_pending_changes: dict[str, dict[str, Any]] = {}

# Current active thresholds (loaded from DB in prod)
_active_thresholds: dict[str, Any] = {
    "medium": 45.0,
    "high": 65.0,
    "critical": 80.0,
    "friction_medium": "awareness_prompt",
    "friction_high": "cooling_timer",
    "friction_critical": "callback_required",
}



@router.get("/settings/thresholds")
async def get_thresholds() -> dict[str, Any]:
    """Current active thresholds."""
    return {
        "thresholds": _active_thresholds,
        "pending_changes": [
            c for c in _pending_changes.values() if c["status"] == "pending"
        ],
    }


@router.post("/settings/thresholds")
async def propose_threshold_change(body: ThresholdChangeRequest) -> dict[str, Any]:
    """Propose a threshold change (step 1 of maker-checker).

    Creates a pending change that needs approval from a different analyst.
    """
    # Validate ordering
    if not (body.medium < body.high < body.critical):
        raise HTTPException(
            status_code=422,
            detail="Thresholds must be in order: medium < high < critical",
        )

    change_id = str(uuid.uuid4())
    change = {
        "id": change_id,
        "change_type": "thresholds",
        "payload": body.model_dump(),
        "requested_by": body.requested_by,
        "approved_by": None,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
    }

    # Try Postgres first
    saved_to_db = _save_pending_to_db(change)
    if not saved_to_db:
        _pending_changes[change_id] = change

    log.info(
        "settings.change_proposed",
        change_id=change_id,
        by=body.requested_by,
        medium=body.medium,
        high=body.high,
        critical=body.critical,
    )

    return {
        "change_id": change_id,
        "status": "pending",
        "message": "Change proposed. Awaiting approval from a different analyst.",
    }


@router.post("/settings/thresholds/{change_id}/approve")
async def approve_threshold_change(
    change_id: str, body: ApprovalRequest,
) -> dict[str, Any]:
    """Approve a pending threshold change (step 2 of maker-checker).

    The approver must be different from the requester.
    """
    change = _pending_changes.get(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Pending change not found")

    if change["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Change already {change['status']}",
        )

    if body.approved_by == change["requested_by"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot approve your own change (maker-checker requires different users)",
        )

    # Apply the change
    payload = change["payload"]
    _active_thresholds.update({
        "medium": payload["medium"],
        "high": payload["high"],
        "critical": payload["critical"],
        "friction_medium": payload["friction_medium"],
        "friction_high": payload["friction_high"],
        "friction_critical": payload["friction_critical"],
    })

    change["status"] = "approved"
    change["approved_by"] = body.approved_by
    change["resolved_at"] = datetime.now(timezone.utc).isoformat()

    log.info(
        "settings.change_approved",
        change_id=change_id,
        by=body.approved_by,
    )

    return {
        "change_id": change_id,
        "status": "approved",
        "active_thresholds": _active_thresholds,
    }


@router.post("/settings/thresholds/{change_id}/reject")
async def reject_threshold_change(
    change_id: str, body: RejectRequest,
) -> dict[str, Any]:
    """Reject a pending threshold change."""
    change = _pending_changes.get(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Pending change not found")

    if change["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Change already {change['status']}",
        )

    change["status"] = "rejected"
    change["resolved_at"] = datetime.now(timezone.utc).isoformat()

    log.info(
        "settings.change_rejected",
        change_id=change_id,
        by=body.rejected_by,
        reason=body.reason,
    )

    return {"change_id": change_id, "status": "rejected"}



def _save_pending_to_db(change: dict) -> bool:
    """Try to persist to Postgres. Returns False if DB unavailable."""
    try:
        from backend.db.models import PendingChange
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            row = PendingChange(
                id=uuid.UUID(change["id"]),
                change_type=change["change_type"],
                payload=change["payload"],
                requested_by=change["requested_by"],
                status="pending",
            )
            db.add(row)
            db.commit()
            return True
        finally:
            db.close()
    except Exception:
        return False
