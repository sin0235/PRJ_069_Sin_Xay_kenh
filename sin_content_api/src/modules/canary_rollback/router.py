"""
API Router for Production Canary and Rollback (Phase P13).
Protected by Canonical RBAC actions.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.tenancy import TenantContext, require_action
from src.schemas.contracts import (
    CanaryDeployRequest, CanaryDeployResponse,
    CanaryResearchRunRequest, CanaryResearchRunResponse,
    CanaryRollbackRequest, CanaryRollbackResponse,
    ProviderRevokeRequest, ProviderAccessStatusResponse
)
from src.modules.canary_rollback.canary_service import canary_service

router = APIRouter(prefix="/v1/canary", tags=["Production Canary & Rollback"])

@router.post(
    "/deployments",
    response_model=CanaryDeployResponse,
    summary="Kích hoạt Canary Deployment cho tenant đã được phê duyệt bằng văn bản (P13)"
)
def create_canary_deployment(
    req: CanaryDeployRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("workspace.settings.update"))
):
    if req.workspace_id != tenant.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant canary deployment prohibited")
    return canary_service.create_canary_deployment(
        db=db,
        user_id=tenant.user_id,
        req=req
    )

@router.post(
    "/runs/execute",
    response_model=CanaryResearchRunResponse,
    summary="Thực thi đợt nghiên cứu Canary với real source IDs, lineage và hạch toán quota (T130)"
)
def execute_canary_research_run(
    req: CanaryResearchRunRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("research.run"))
):
    if req.workspace_id != tenant.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant canary run execution prohibited")
    return canary_service.execute_canary_research_run(
        db=db,
        user_id=tenant.user_id,
        req=req
    )

@router.post(
    "/deployments/{deployment_id}/rollback",
    response_model=CanaryRollbackResponse,
    summary="Kích hoạt quy trình Rollback khẩn cấp cho Canary deployment (T130)"
)
def rollback_canary_deployment(
    deployment_id: str,
    req: CanaryRollbackRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("workspace.settings.update"))
):
    if req.workspace_id != tenant.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant canary rollback prohibited")
    return canary_service.rollback_canary_deployment(
        db=db,
        user_id=tenant.user_id,
        deployment_id=deployment_id,
        rollback_reason=req.rollback_reason
    )

@router.post(
    "/providers/revoke",
    response_model=ProviderAccessStatusResponse,
    summary="Thu hồi quyền truy cập nhà cung cấp dữ liệu trong Canary (T131)"
)
def revoke_provider_access(
    req: ProviderRevokeRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("provider.configure"))
):
    if req.workspace_id != tenant.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant provider revocation prohibited")
    return canary_service.revoke_provider_access(
        db=db,
        user_id=tenant.user_id,
        workspace_id=tenant.workspace_id,
        provider_id=req.provider_id,
        revocation_reason=req.revocation_reason
    )

@router.get(
    "/providers/{provider_id}/status",
    response_model=ProviderAccessStatusResponse,
    summary="Kiểm tra trạng thái nhà cung cấp và thông báo an toàn cho operator (T131)"
)
def get_provider_status(
    provider_id: str,
    workspace_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("workspace.read"))
):
    if workspace_id and workspace_id != tenant.workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant provider status query prohibited")
    return canary_service.check_provider_access(
        db=db,
        workspace_id=tenant.workspace_id,
        provider_id=provider_id
    )
