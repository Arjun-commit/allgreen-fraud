"""Case endpoints for the analyst UI. Phase 1: empty stubs."""

from typing import Any, Literal

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel

log = structlog.get_logger()
router = APIRouter()


class CaseResolveRequest(BaseModel):
    outcome: Literal["confirmed_fraud", "legitimate", "escalated"]
    notes: str | None = None


@router.get("/cases")
async def list_cases(
    status: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    # TODO(phase-5): real query against analyst_cases + transactions join.
    log.debug("cases.list", status=status, min_score=min_score, page=page)
    return {"items": [], "page": page, "limit": limit, "total": 0}


@router.post("/cases/{case_id}/resolve")
async def resolve_case(case_id: str, body: CaseResolveRequest) -> dict[str, str]:
    log.info("cases.resolve", case_id=case_id, outcome=body.outcome)
    return {"case_id": case_id, "status": "resolved", "outcome": body.outcome}


@router.get("/analytics/model-performance")
async def model_performance() -> dict[str, Any]:
    # TODO(phase-5): pull real numbers from MLflow + case outcomes.
    return {
        "period": "last_30_days",
        "lstm": {"auc": None, "precision": None, "recall": None},
        "xgboost": {"auc": None, "precision": None, "recall": None},
        "ensemble": {"auc": None},
        "friction_effectiveness": {
            "soft_friction_abandon_rate": None,
            "hard_block_scam_confirmation_rate": None,
        },
    }
