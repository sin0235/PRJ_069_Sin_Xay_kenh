"""API phê duyệt; actor và tài nguyên luôn được phân giải phía máy chủ."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from baha_auth.src.api.deps import ActorContext, get_current_actor
from baha_auth.src.database import get_db
from baha_auth.src.models.entities import ApprovalRun
from baha_auth.src.schemas.contracts import (
    ApprovalDecisionRequest,
    ApprovalRunCreate,
    ApprovalRunOut,
    ApprovalStepOut,
)
from baha_auth.src.services.approval_service import ApprovalService, ApprovalServiceError


router = APIRouter(prefix="/authz/v1/approvals", tags=["Phê duyệt"])


def _run_output(run: ApprovalRun) -> ApprovalRunOut:
    steps = sorted(run.steps, key=lambda item: item.ordinal)
    return ApprovalRunOut(
        id=run.id,
        workspace_id=run.workspace_id,
        artifact_type=run.artifact_type,
        artifact_id=run.artifact_id,
        artifact_version=run.artifact_version,
        content_hash=run.content_hash,
        status=run.status,
        created_by=run.created_by,
        created_at=run.created_at,
        steps=[
            ApprovalStepOut(
                id=step.id,
                stage_key=step.stage_key,
                allowed_role_or_assignee=step.allowed_role_or_assignee,
                status=step.status,
                ordinal=step.ordinal,
            )
            for step in steps
        ],
    )


def _raise_service_error(db: Session, error: ApprovalServiceError) -> None:
    # Các từ chối đã được ghi audit trong cùng session; commit riêng sự kiện đó.
    db.commit()
    raise HTTPException(
        status_code=error.status_code,
        detail={"error_code": error.code},
    )


@router.post("/runs", response_model=ApprovalRunOut, status_code=status.HTTP_201_CREATED)
def create_approval_run(
    payload: ApprovalRunCreate,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    try:
        run = ApprovalService.start_approval_run(
            db,
            actor,
            artifact_type=payload.artifact_type,
            artifact_id=payload.artifact_id,
            expected_version=payload.expected_version,
        )
        db.commit()
        db.refresh(run)
        return _run_output(run)
    except ApprovalServiceError as exc:
        _raise_service_error(db, exc)
    except Exception:
        db.rollback()
        raise


@router.get("/inbox", response_model=List[ApprovalRunOut])
def list_review_inbox(
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    runs = ApprovalService.list_review_inbox(db, actor)
    return [_run_output(run) for run in runs]


@router.post("/decisions", response_model=dict)
def submit_decision(
    payload: ApprovalDecisionRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    try:
        decision = ApprovalService.record_decision(
            db,
            actor,
            step_id=payload.step_id,
            result=payload.result,
            artifact_version=payload.artifact_version,
            content_hash=payload.content_hash,
            reason=payload.reason,
        )
        db.commit()
        return {
            "status": "success",
            "decision_id": decision.id,
            "result": decision.result,
            "decided_at": decision.decided_at.isoformat(),
        }
    except ApprovalServiceError as exc:
        _raise_service_error(db, exc)
    except Exception:
        db.rollback()
        raise
