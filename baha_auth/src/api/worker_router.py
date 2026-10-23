"""API grant/recheck worker có xác thực service principal và grant hẹp."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from baha_auth.src.api.deps import ActorContext, get_current_actor
from baha_auth.src.config import settings
from baha_auth.src.database import get_db, set_tenant_context
from baha_auth.src.models.entities import BusinessResource, Workspace
from baha_auth.src.schemas.contracts import (
    DelegatedJobGrantOut,
    DelegatedJobGrantRequest,
    WorkerRecheckRequest,
    WorkerRecheckResponse,
)
from baha_auth.src.services.worker_service import WorkerAuthService, WorkerServiceError
from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, VerifiedIdentity, verify_bearer_token


router = APIRouter(prefix="/authz/v1/workers", tags=["Worker"])
_bearer = HTTPBearer(auto_error=False)


def _verified_worker_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> VerifiedIdentity:
    required = (
        settings.jwt_secret_key,
        settings.jwt_issuer,
        settings.worker_jwt_audience,
        settings.worker_jwt_subject,
    )
    if any(not value or not value.strip() for value in required):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "WORKER_AUTH_NOT_CONFIGURED"},
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "WORKER_BEARER_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        identity = verify_bearer_token(
            credentials.credentials,
            secret=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.worker_jwt_audience,
        )
    except InvalidBearerToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_WORKER_BEARER"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if identity.subject != settings.worker_jwt_subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "WORKER_SUBJECT_DENIED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if identity.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "WORKER_WORKSPACE_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity


def _raise_service_error(db: Session, error: WorkerServiceError) -> None:
    db.commit()
    raise HTTPException(status_code=error.status_code, detail={"error_code": error.code})


@router.post("/grants", response_model=DelegatedJobGrantOut, status_code=status.HTTP_201_CREATED)
def issue_worker_grant(
    payload: DelegatedJobGrantRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    try:
        grant = WorkerAuthService.issue_grant(
            db,
            actor,
            job_id=payload.job_id,
            target_resource=payload.target_resource,
            allowed_actions=payload.allowed_actions,
            expires_at=payload.expires_at,
        )
        resource = db.query(BusinessResource).filter(
            BusinessResource.id == grant.target_resource,
            BusinessResource.workspace_id == grant.workspace_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if (
            resource is None
            or resource.artifact_version != grant.target_artifact_version
            or resource.content_hash != grant.target_content_hash
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_code": "WORKER_RESOURCE_NOT_AVAILABLE"})
        db.commit()
        db.refresh(grant)
        return DelegatedJobGrantOut(
            id=grant.id,
            workspace_id=grant.workspace_id,
            job_id=grant.job_id,
            initiating_membership_id=grant.initiating_membership_id,
            target_resource=grant.target_resource,
            resource_type=resource.resource_type,
            artifact_version=grant.target_artifact_version,
            content_hash=grant.target_content_hash,
            policy_version=grant.policy_version,
            allowed_actions=json.loads(grant.allowed_actions_json),
            expires_at=grant.expires_at,
            status=grant.status,
        )
    except WorkerServiceError as exc:
        _raise_service_error(db, exc)
    except Exception:
        db.rollback()
        raise


@router.post("/recheck", response_model=WorkerRecheckResponse)
def recheck_worker_runtime(
    payload: WorkerRecheckRequest,
    identity: VerifiedIdentity = Depends(_verified_worker_identity),
    db: Session = Depends(get_db),
):
    try:
        # Gắn tenant đã ký trước khi truy vấn đầu tiên để PostgreSQL áp dụng RLS.
        set_tenant_context(identity.workspace_id, db)
        workspace = db.query(Workspace).filter(
            Workspace.id == identity.workspace_id,
            Workspace.status == "ACTIVE",
        ).first()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "WORKER_WORKSPACE_DENIED"},
            )
        result = WorkerAuthService.recheck_runtime_permission(
            db,
            job_id=payload.job_id,
            action_key=payload.action_key,
            worker_subject=identity.subject,
            expected_workspace_id=identity.workspace_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return WorkerRecheckResponse(
        allowed=result.allowed,
        job_id=payload.job_id,
        action_key=payload.action_key,
        status="AUTHORIZED" if result.allowed else "DENIED",
        reason=(
            "Đã xác minh lại quyền thực thi."
            if result.allowed
            else "Grant không còn hợp lệ hoặc quyền hiện tại không cho phép."
        ),
        workspace_id=result.workspace_id,
        target_resource=result.target_resource,
        resource_type=result.resource_type,
        artifact_version=result.artifact_version,
        content_hash=result.content_hash,
        policy_version=result.policy_version,
    )
