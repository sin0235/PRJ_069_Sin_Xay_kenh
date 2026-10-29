"""Xác thực bearer và đánh giá RBAC qua kho Baha Auth chuẩn."""

from __future__ import annotations

import os
import re
import sys
import uuid
import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Optional
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from src.database import get_db as get_content_db
from src.models.entities import Workspace
from src.config import settings


_WORKSPACE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class TenantContext:
    workspace_id: str
    user_id: str
    actor: Any
    auth_db: Optional[Session]
    request_id: str
    dev_auth_bypass: bool = False


def dev_auth_bypass_enabled(request: Request) -> bool:
    """Allow auth bypass only for explicitly enabled local development requests."""
    client_host = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        is_loopback = client_host.lower() == "localhost"
    origin = request.headers.get("origin")
    if origin:
        try:
            origin_host = urlsplit(origin).hostname or ""
        except ValueError:
            return False
        try:
            is_local_origin = ipaddress.ip_address(origin_host).is_loopback
        except ValueError:
            is_local_origin = origin_host.lower() == "localhost"
        is_loopback = is_loopback and is_local_origin
    return (
        os.getenv("DEV_AUTH_BYPASS") == "1"
        and settings.app_env.lower() in {"offline", "development", "dev", "local", "test"}
        and is_loopback
    )


def _canonical_auth_modules() -> dict[str, Any]:
    """Nạp Baha Auth bằng namespace chuẩn khi toàn bộ cấu hình tường minh có mặt."""
    secret = os.getenv("BAHA_AUTH_JWT_SECRET")
    issuer = os.getenv("BAHA_AUTH_JWT_ISSUER")
    audience = os.getenv("BAHA_AUTH_JWT_AUDIENCE")
    database_url = os.getenv("BAHA_AUTH_DATABASE_URL")
    if not all((secret, issuer, audience, database_url)):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dịch vụ phân quyền chưa được cấu hình.",
        )

    project_root = str(Path(__file__).resolve().parents[3])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from baha_auth.src.database import (  # type: ignore[import-not-found]
            clear_tenant_context,
            get_db as get_auth_db,
            set_tenant_context,
        )
        from baha_auth.src.policy.evaluator import (  # type: ignore[import-not-found]
            ActorContext,
            ResourceContext,
            evaluate_permission,
        )
        from baha_auth.src.services.danh_tinh_service import (  # type: ignore[import-not-found]
            load_actor_for_user,
        )
        from baha_auth.src.services.nhat_ky_kiem_toan import (  # type: ignore[import-not-found]
            write_audit_event,
        )
        from baha_auth.src.xac_minh_danh_tinh import (  # type: ignore[import-not-found]
            verify_bearer_token,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dịch vụ phân quyền chưa sẵn sàng.",
        ) from exc

    return {
        "secret": secret,
        "issuer": issuer,
        "audience": audience,
        "get_auth_db": get_auth_db,
        "set_tenant_context": set_tenant_context,
        "clear_tenant_context": clear_tenant_context,
        "verify_bearer_token": verify_bearer_token,
        "load_actor_for_user": load_actor_for_user,
        "evaluate_permission": evaluate_permission,
        "write_audit_event": write_audit_event,
        "ActorContext": ActorContext,
        "ResourceContext": ResourceContext,
    }


def require_trusted_origin(request: Request, *, required: bool = True) -> None:
    raw_origin = request.headers.get("origin")
    if not raw_origin:
        if required:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin không hợp lệ.")
        return
    try:
        parsed = urlsplit(raw_origin)
        origin = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
        valid = (
            parsed.scheme in {"http", "https"}
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and parsed.path == ""
            and not parsed.query
            and not parsed.fragment
            and origin in settings.auth_allowed_origins_set
        )
    except ValueError:
        valid = False
    if not valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin không hợp lệ.")


def owner_direct_creation(tenant: TenantContext) -> bool:
    """Cho phép owner đã cấu hình bỏ bước duyệt riêng cho luồng tạo trực tiếp."""
    actor = tenant.actor
    if (
        tenant.dev_auth_bypass
        or not tenant.auth_db
        or not actor
        or actor.user_id != tenant.user_id
        or actor.workspace_id != tenant.workspace_id
        or actor.membership_status != "ACTIVE"
        or actor.user_status != "ACTIVE"
        or actor.workspace_status != "ACTIVE"
    ):
        return False

    owner_grant = any(
        role.get("role_code") in {"WORKSPACE_OWNER", "PLATFORM_OWNER"}
        and role.get("scope_type") == "WORKSPACE"
        and role.get("scope_id") in {None, tenant.workspace_id}
        and role.get("assignment_status") == "ACTIVE"
        and role.get("role_status") == "ACTIVE"
        and role.get("is_active") is True
        for role in actor.roles
    )
    if not owner_grant or (not settings.auth_owner_email and not settings.platform_owner_ids_set):
        return False

    try:
        from baha_auth.src.models.entities import GlobalUser

        user = tenant.auth_db.get(GlobalUser, tenant.user_id)
    except Exception:
        return False
    return bool(
        user
        and user.status == "ACTIVE"
        and (
            user.id in settings.platform_owner_ids_set
            or user.email.casefold() == settings.auth_owner_email
        )
    )


def _close_generator(generator: Iterator[Session]) -> None:
    close = getattr(generator, "close", None)
    if close is not None:
        close()


def get_current_tenant_context(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    baha_auth_token: Optional[str] = Cookie(None, alias="baha_auth_token"),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    content_db: Session = Depends(get_content_db),
) -> Iterator[TenantContext]:
    """Lấy danh tính từ JWT và xác minh membership hiện hành cho workspace đã chọn."""
    if dev_auth_bypass_enabled(request):
        workspace_id = x_workspace_id or "default_ws"
        if not _WORKSPACE_ID.fullmatch(workspace_id):
            raise HTTPException(status_code=400, detail="Workspace không hợp lệ.")
        yield TenantContext(
            workspace_id=workspace_id,
            user_id="dev-user",
            actor=None,
            auth_db=None,
            request_id=str(uuid.uuid4()),
            dev_auth_bypass=True,
        )
        return

    token = ""
    used_cookie = False
    if authorization is not None:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cần bearer token hợp lệ.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = authorization[len("Bearer "):].strip()
        if not token and baha_auth_token:
            token = baha_auth_token
            used_cookie = True
    elif baha_auth_token:
        token = baha_auth_token
        used_cookie = True

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần bearer token hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if used_cookie and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        require_trusted_origin(request)
    if x_workspace_id is not None and not _WORKSPACE_ID.fullmatch(x_workspace_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần chọn workspace hợp lệ.",
        )

    auth = _canonical_auth_modules()
    try:
        identity = auth["verify_bearer_token"](
            token,
            secret=auth["secret"],
            issuer=auth["issuer"],
            audience=auth["audience"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token không hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    workspace_id = x_workspace_id or identity.workspace_id
    if not workspace_id or not _WORKSPACE_ID.fullmatch(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần chọn workspace hợp lệ.",
        )

    auth_db_generator = auth["get_auth_db"]()
    auth_db: Optional[Session] = None
    try:
        auth_db = next(auth_db_generator)
        auth["set_tenant_context"](workspace_id, auth_db)
        actor = auth["load_actor_for_user"](
            auth_db,
            workspace_id=workspace_id,
            user_id=identity.user_id,
        )
        if actor is None or actor.user_id != identity.user_id or actor.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập workspace đã chọn.",
            )

        # Membership chuẩn không tự tạo workspace trong kho nội dung tách biệt.
        if content_db.query(Workspace.id).filter(Workspace.id == workspace_id).first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập workspace đã chọn.",
            )

        yield TenantContext(
            workspace_id=workspace_id,
            user_id=identity.user_id,
            actor=actor,
            auth_db=auth_db,
            request_id=str(uuid.uuid4()),
        )
    except (HTTPException, RequestValidationError):
        raise
    except Exception as exc:
        if auth_db is not None:
            auth_db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kiểm tra membership hoặc kết nối kho phân quyền.",
        ) from exc
    finally:
        if auth_db is not None:
            try:
                auth_db.rollback()
            except Exception:
                pass
            try:
                auth["clear_tenant_context"](auth_db)
            except Exception:
                pass
        _close_generator(auth_db_generator)
        auth["clear_tenant_context"]()


def _audit_decision(
    ctx: TenantContext,
    auth: dict[str, Any],
    action_key: str,
    decision: Any,
    resource: Any = None,
) -> None:
    try:
        # SET LOCAL clears on commit; bind lại tenant trước transaction audit.
        auth["set_tenant_context"](ctx.workspace_id, ctx.auth_db)
        auth["write_audit_event"](
            ctx.auth_db,
            workspace_id=ctx.workspace_id,
            actor_id=ctx.user_id,
            actor_type="USER",
            action_key=action_key,
            decision="ALLOW" if decision.allowed else "DENY",
            reason=decision.reason_code,
            policy_version=decision.policy_version,
            resource_type=getattr(resource, "resource_type", None),
            resource_id=getattr(resource, "resource_id", None),
            request_id=ctx.request_id,
            safe_metadata={},
        )
        ctx.auth_db.commit()
    except Exception:
        ctx.auth_db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể ghi nhận quyết định phân quyền.",
        ) from None


def authorize_action(ctx: TenantContext, action_key: str, resource: Any = None) -> None:
    """Đánh giá action; request tổng hợp chỉ xét assignment cấp workspace."""
    if ctx.dev_auth_bypass:
        return
    auth = _canonical_auth_modules()
    try:
        actor = ctx.actor
        if resource is None:
            # Assignment TEAM/PROJECT/OWN không được nâng thành quyền đọc toàn tenant.
            actor = auth["ActorContext"](
                user_id=ctx.actor.user_id,
                workspace_id=ctx.actor.workspace_id,
                membership_id=ctx.actor.membership_id,
                membership_status=ctx.actor.membership_status,
                roles=[role for role in ctx.actor.roles if role.get("scope_type") == "WORKSPACE"],
                department_ids=[],
                team_ids=[],
                user_status=ctx.actor.user_status,
                workspace_status=ctx.actor.workspace_status,
            )
        decision = auth["evaluate_permission"](
            actor=actor,
            action_key=action_key,
            resource=resource,
        )
        _audit_decision(ctx, auth, action_key, decision, resource)
    except (HTTPException, RequestValidationError):
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chính sách quyền chưa sẵn sàng.",
        ) from exc

    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không đủ quyền cho thao tác hoặc phạm vi tài nguyên này.",
        )


def authorize_resource(
    ctx: TenantContext,
    action_key: str,
    *,
    resource_type: str,
    resource_id: Optional[str],
    workspace_id: Optional[str],
    org_unit_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    creator_id: Optional[str] = None,
    artifact_version: Optional[int] = None,
    content_hash: Optional[str] = None,
    project_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    require_creator: bool = False,
) -> None:
    """Kiểm tra scope trên row đã được truy vấn server-side trong tenant."""
    if (
        not resource_id
        or not workspace_id
        or workspace_id != ctx.workspace_id
        or (require_creator and not creator_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể xác minh phạm vi hoặc nguồn tạo của tài nguyên.",
        )

    if ctx.dev_auth_bypass:
        return

    auth = _canonical_auth_modules()
    try:
        resource = auth["ResourceContext"](
            workspace_id=workspace_id,
            resource_id=resource_id,
            resource_type=resource_type,
            org_unit_id=org_unit_id,
            owner_id=owner_id,
            creator_id=creator_id,
            artifact_version=artifact_version,
            content_hash=content_hash,
            project_id=project_id,
            brand_id=brand_id,
            channel_id=channel_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể tạo ngữ cảnh tài nguyên cho chính sách quyền.",
        ) from exc
    authorize_action(ctx, action_key, resource=resource)


def require_action(action_key: str) -> Callable[..., TenantContext]:
    """Dependency cho route tổng hợp; chỉ grant workspace được phép qua guard này."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        authorize_action(ctx, action_key)
        return ctx

    dependency.__name__ = f"require_action_{action_key.replace('.', '_')}"
    dependency.required_action = action_key  # type: ignore[attr-defined]
    return dependency


def require_actions(*action_keys: str) -> Callable[..., TenantContext]:
    """Yêu cầu đồng thời nhiều action trên dữ liệu tổng hợp cấp workspace."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        for action_key in action_keys:
            authorize_action(ctx, action_key)
        return ctx

    dependency.__name__ = "require_actions_" + "_".join(key.replace('.', '_') for key in action_keys)
    dependency.required_actions = tuple(action_keys)  # type: ignore[attr-defined]
    return dependency


def require_resolved_resource_action(action_key: str) -> Callable[..., TenantContext]:
    """Nạp actor cho route mà handler phải truy vấn row và gọi authorize_resource."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        return ctx

    dependency.__name__ = f"require_resolved_resource_{action_key.replace('.', '_')}"
    dependency.required_action = action_key  # type: ignore[attr-defined]
    dependency.requires_resource_authorization = True  # type: ignore[attr-defined]
    return dependency


def require_resolved_resource_actions(*action_keys: str) -> Callable[..., TenantContext]:
    """Nạp actor cho route có nhiều action được kiểm tra trên resource đã phân giải."""
    def dependency(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        return ctx

    dependency.__name__ = "require_resolved_resource_" + "_".join(
        key.replace('.', '_') for key in action_keys
    )
    dependency.required_actions = tuple(action_keys)  # type: ignore[attr-defined]
    dependency.requires_resource_authorization = True  # type: ignore[attr-defined]
    return dependency


def require_role(_: str):
    """Dependency role legacy bị vô hiệu hóa; route phải khai báo action RBAC cụ thể."""
    def deny_legacy_role(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kiểm tra role legacy đã bị vô hiệu hóa; route cần action RBAC cụ thể.",
        )

    deny_legacy_role.__name__ = "deny_legacy_role"
    return deny_legacy_role
