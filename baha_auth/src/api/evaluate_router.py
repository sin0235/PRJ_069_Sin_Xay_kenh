"""Định tuyến API đánh giá quyền dựa trên tài nguyên do máy chủ phân giải."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from baha_auth.src.api.deps import ActorContext, get_current_actor
from baha_auth.src.database import get_db
from baha_auth.src.models.entities import BusinessResource
from baha_auth.src.config import settings
from baha_auth.src.policy.evaluator import AuthorizationDecision, ResourceContext, evaluate_permission
from baha_auth.src.schemas.contracts import EvaluateRequest, EvaluateResponse
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event


router = APIRouter(prefix="/authz/v1", tags=["Authorization Decision Engine"])


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate_access(
    payload: EvaluateRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
    request: Request = None,
):
    resource_ctx = None
    resource_type = None
    if payload.resource_id:
        resource = db.query(BusinessResource).filter(
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.id == payload.resource_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if resource is None:
            decision = AuthorizationDecision(
                allowed=False,
                decision="DENY",
                reason_code="RESOURCE_NOT_FOUND",
                internal_reason="Tài nguyên không tồn tại trong workspace đang hoạt động.",
                policy_version=settings.policy_version,
            )
        else:
            resource_type = resource.resource_type
            resource_ctx = ResourceContext(
                workspace_id=resource.workspace_id,
                resource_id=resource.id,
                resource_type=resource.resource_type,
                org_unit_id=resource.org_unit_id,
                owner_id=resource.owner_id,
                creator_id=resource.creator_id,
                artifact_version=resource.artifact_version,
                content_hash=resource.content_hash,
                project_id=resource.project_id,
                brand_id=resource.brand_id,
                channel_id=resource.channel_id,
            )
            decision = evaluate_permission(actor, payload.action_key, resource_ctx)
    else:
        decision = evaluate_permission(actor, payload.action_key)

    write_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        actor_type="USER",
        action_key=payload.action_key,
        decision=decision.decision,
        reason=decision.internal_reason,
        policy_version=decision.policy_version,
        resource_type=resource_type,
        resource_id=payload.resource_id,
        request_id=request.headers.get("X-Request-Id") if request else None,
    )
    db.commit()
    return EvaluateResponse(
        allowed=decision.allowed,
        decision=decision.decision,
        reason_code=decision.reason_code,
        internal_reason=decision.internal_reason,
        policy_version=decision.policy_version,
    )
