"""Dependency xác minh bearer và thực thi phân quyền cho FastAPI."""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from baha_auth.src.config import settings
from baha_auth.src.database import get_db, set_tenant_context
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.services.danh_tinh_service import load_actor_for_user
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event
from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, verify_bearer_token


_bearer = HTTPBearer(auto_error=False)


def get_current_actor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    db: Session = Depends(get_db),
) -> ActorContext:
    """Xác minh bearer trước, rồi nạp membership đang hoạt động trong tenant đã chọn."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "BEARER_TOKEN_REQUIRED", "message": "Yêu cầu bearer token hợp lệ."},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not x_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "WORKSPACE_REQUIRED", "message": "Yêu cầu header X-Workspace-Id."},
        )
    if not all((settings.jwt_secret_key, settings.jwt_issuer, settings.jwt_audience)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "IDENTITY_PROVIDER_NOT_CONFIGURED", "message": "Chưa cấu hình nhà cung cấp danh tính để xác minh bearer."},
        )

    try:
        identity = verify_bearer_token(
            credentials.credentials,
            secret=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except InvalidBearerToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": str(exc), "message": "Bearer token không hợp lệ."},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    set_tenant_context(x_workspace_id, db)
    actor = load_actor_for_user(db, x_workspace_id, identity.user_id)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACTIVE_MEMBERSHIP_REQUIRED", "message": "Người dùng chưa có membership đang hoạt động trong workspace này."},
        )
    return actor


def require_action(action_key: str):
    """Tạo dependency kiểm tra action ở phạm vi workspace trước khi chạy route."""
    def permission_checker(
        request: Request,
        actor: ActorContext = Depends(get_current_actor),
        db: Session = Depends(get_db),
    ) -> ActorContext:
        decision = evaluate_permission(actor, action_key)
        write_audit_event(
            db,
            workspace_id=actor.workspace_id,
            actor_id=actor.user_id,
            actor_type="USER",
            action_key=action_key,
            decision=decision.decision,
            reason=decision.internal_reason,
            policy_version=decision.policy_version,
            request_id=request.headers.get("X-Request-Id"),
        )
        db.commit()
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": decision.reason_code,
                    "message": "Bạn không có quyền thực hiện action này.",
                    "action_key": action_key,
                    "policy_version": decision.policy_version,
                },
            )
        return actor
    return permission_checker
