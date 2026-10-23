"""
API Router for Staging Reliability & Evaluation (Phase P12).
Protected by Canonical RBAC actions from PERMISSION_REGISTRY.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import TenantContext, require_action
from src.schemas.contracts import (
    BudgetReserveRequest, BudgetReserveResponse,
    TaskExecuteRequest, TaskExecuteResponse,
    ReconciliationRequest, ReconciliationResponse
)
from src.modules.staging_reliability.budget_guard import budget_guard
from src.modules.staging_reliability.downstream_executor import downstream_executor
from src.modules.staging_reliability.prompt_regression import prompt_regression_engine

router = APIRouter(prefix="/v1/staging", tags=["Staging Reliability & Evaluation"])

@router.post(
    "/budget/reserve",
    response_model=BudgetReserveResponse,
    summary="Giữ chỗ hạn mức ngân sách trước khi thực thi công việc tính phí (T122)"
)
def reserve_budget(
    req: BudgetReserveRequest,
    db: Session = Depends(get_db),
    actor: TenantContext = Depends(require_action("ai_budget.update"))
):
    if req.workspace_id != actor.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant budget operations prohibited")
    return budget_guard.reserve_budget(
        db=db,
        workspace_id=actor.workspace_id,
        task_id=req.task_id,
        idempotency_key=req.idempotency_key,
        action_type=req.action_type,
        estimated_units=req.estimated_units
    )

@router.post(
    "/tasks/execute",
    response_model=TaskExecuteResponse,
    summary="Thực thi tác vụ downstream với cơ chế bounded retry và bảo đảm lũy đẳng (T121)"
)
def execute_downstream_task(
    req: TaskExecuteRequest,
    db: Session = Depends(get_db),
    actor: TenantContext = Depends(require_action("research.run"))
):
    if req.workspace_id != actor.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant task execution prohibited")
    user_id = actor.user_id if hasattr(actor, "user_id") else "system"
    return downstream_executor.execute_with_resilience(
        db=db,
        workspace_id=actor.workspace_id,
        user_id=user_id,
        req=req
    )

@router.post(
    "/budget/reconcile",
    response_model=ReconciliationResponse,
    summary="Đối soát chi phí thực tế với hóa đơn vendor và phát hiện sai lệch (T122)"
)
def reconcile_vendor_billing(
    req: ReconciliationRequest,
    db: Session = Depends(get_db),
    actor: TenantContext = Depends(require_action("billing.manage"))
):
    if req.workspace_id != actor.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant reconciliation prohibited")
    return budget_guard.reconcile_vendor_billing(
        db=db,
        workspace_id=actor.workspace_id,
        ledger_id=req.ledger_id,
        vendor_reported_units=req.vendor_reported_units
    )

@router.get(
    "/evaluation/prompt-regression",
    summary="Đánh giá hồi quy prompt trên tập held-out dataset theo Human Quality Study Protocol (T124)"
)
def get_prompt_regression_evaluation(
    actor: TenantContext = Depends(require_action("analytics.read"))
):
    return prompt_regression_engine.evaluate_held_out_regression()
