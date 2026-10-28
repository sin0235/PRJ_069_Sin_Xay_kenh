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
from urllib.parse import urlparse

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import get_db as get_content_db
from src.models.entities import Workspace
from src.config import settings
from src.auth.mat_khau_noi_bo import SESSION_COOKIE, local_password_mode, verify_session_token


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
    """Allow auth bypass for explicitly enabled local development and LAN/test requests."""
    client_host = request.client.host if request.client else ""
    try:
        ip_obj = ipaddress.ip_address(client_host)
        is_loopback = ip_obj.is_loopback or client_host.startswith(("10.", "172.", "192.168."))
    except ValueError:
        is_loopback = client_host.lower() in {"localhost", "127.0.0.1", "192.168.1.175"}
    origin = request.headers.get("origin")
    if origin:
        try:
            origin_host = urlparse(origin).hostname or ""
        except ValueError:
            return False
        try:
            origin_ip = ipaddress.ip_address(origin_host)
            is_local_origin = origin_ip.is_loopback or origin_host.startswith(("10.", "172.", "192.168."))
        except ValueError:
            is_local_origin = origin_host.lower() in {
                "localhost",
                "127.0.0.1",
                "192.168.1.175",
                "nhap-xaykenh-proj069.bahagroup.vn",
            } or origin_host.lower().endswith(".bahagroup.vn")
        is_loopback = is_loopback and is_local_origin
    return (
        os.getenv("DEV_AUTH_BYPASS") == "1"
        and settings.app_env.lower() in {"offline", "development", "dev", "local", "test"}
        and is_loopback
    )


def _canonical_auth_modules() -> dict[str, Any]:
    """Nạp Baha Auth bằng namespace chuẩn khi toàn bộ cấu hình tường minh có mặt."""
    if settings.app_env.lower() == "production" and not all(
        os.getenv(name, "").strip()
        for name in ("BAHA_AUTH_JWT_SECRET", "BAHA_AUTH_JWT_ISSUER", "BAHA_AUTH_JWT_AUDIENCE", "BAHA_AUTH_DATABASE_URL")
    ):
        # Production không được dùng giá trị mặc định trong mã nguồn.
        raise HTTPException(status_code=503, detail="Cấu hình xác thực production chưa đầy đủ.")
    # Giá trị mặc định chỉ để chạy kiểm thử cục bộ; production đã bị chặn ở trên nếu thiếu biến môi trường.
    secret = os.getenv("BAHA_AUTH_JWT_SECRET", "khoa-chi-dung-kiem-thu-cuc-bo-khong-phai-bi-mat-0123456789")
    issuer = os.getenv("BAHA_AUTH_JWT_ISSUER", "prj069-nas-test")
    audience = os.getenv("BAHA_AUTH_JWT_AUDIENCE", "sin-content-test")
    database_url = os.getenv("BAHA_AUTH_DATABASE_URL", "sqlite:////persist/baha_auth_e2e_test.db")

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
        from baha_auth.src.models.entities import GlobalUser
        from baha_auth.src.xac_minh_danh_tinh import (  # type: ignore[import-not-found]
            verify_cloudflare_access_jwt,
            verify_bearer_token,
        )
        return {
            "secret": secret,
            "issuer": issuer,
            "audience": audience,
            "get_auth_db": get_auth_db,
            "set_tenant_context": set_tenant_context,
            "clear_tenant_context": clear_tenant_context,
            "verify_bearer_token": verify_bearer_token,
            "verify_cloudflare_access_jwt": verify_cloudflare_access_jwt,
            "GlobalUser": GlobalUser,
            "load_actor_for_user": load_actor_for_user,
            "write_audit_event": write_audit_event,
            "ActorContext": ActorContext,
            "ResourceContext": ResourceContext,
            "evaluate_permission": evaluate_permission,
        }
    except Exception as exc:
        return {
            "secret": secret,
            "issuer": issuer,
            "audience": audience,
            "database_url": database_url,
            "get_auth_db": None,
            "set_tenant_context": lambda *a, **k: None,
            "clear_tenant_context": lambda *a, **k: None,
            "verify_bearer_token": None,
            "verify_cloudflare_access_jwt": None,
            "GlobalUser": None,
            "load_actor_for_user": None,
            "write_audit_event": lambda *a, **k: None,
            "ActorContext": None,
            "ResourceContext": None,
            "evaluate_permission": lambda *a, **k: True,
        }


def verify_access_assertion(token: Optional[str]) -> Any:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần danh tính Cloudflare Access đã xác minh.",
        )
    issuer = os.getenv("CLOUDFLARE_ACCESS_ISSUER", "").strip()
    audience = os.getenv("CLOUDFLARE_ACCESS_AUDIENCE", "").strip()
    if not issuer or not audience:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Xác thực Cloudflare Access chưa được cấu hình.",
        )
    auth = _canonical_auth_modules()
    try:
        return auth["verify_cloudflare_access_jwt"](token, issuer=issuer, audience=audience)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assertion Cloudflare Access không hợp lệ hoặc đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _close_generator(generator: Iterator[Session]) -> None:
    close = getattr(generator, "close", None)
    if close is not None:
        close()


def get_current_tenant_context(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    cf_access_assertion: Optional[str] = Header(None, alias="Cf-Access-Jwt-Assertion"),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    content_db: Session = Depends(get_content_db),
) -> Iterator[TenantContext]:
    """Lấy danh tính từ JWT và xác minh membership hiện hành cho workspace đã chọn."""
    if dev_auth_bypass_enabled(request):
        workspace_id = x_workspace_id or os.getenv("SIN_WORKSPACE_ID", "").strip() or "b6102190-1f6f-5624-bfb8-2e1091fa2560"
        if not workspace_id or workspace_id in {"default_ws", "default", "undefined", "null"}:
            workspace_id = "b6102190-1f6f-5624-bfb8-2e1091fa2560"
        if not _WORKSPACE_ID.fullmatch(workspace_id):
            workspace_id = "b6102190-1f6f-5624-bfb8-2e1091fa2560"
        yield TenantContext(
            workspace_id=workspace_id,
            user_id="b83ca206-f7a9-54be-a230-035cda108f4b",
            actor=None,
            auth_db=None,
            request_id=str(uuid.uuid4()),
            dev_auth_bypass=True,
        )
        return

    local_mode = local_password_mode(settings.app_env)
    local_session = request.cookies.get(SESSION_COOKIE) if local_mode else None
    test_bearer_allowed = os.getenv("TESTING") == "1" and settings.app_env.lower() in {"offline", "development", "dev", "local", "test"}
    if local_mode and not local_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần đăng nhập vào SIN Creator OS.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not local_mode and not cf_access_assertion and not (test_bearer_allowed and authorization and authorization.startswith("Bearer ")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần danh tính Cloudflare Access đã xác minh.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    effective_workspace_id = x_workspace_id
    if not effective_workspace_id or effective_workspace_id in {"default_ws", "default", "undefined", "null"}:
        effective_workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip() or "b6102190-1f6f-5624-bfb8-2e1091fa2560"
    if not _WORKSPACE_ID.fullmatch(effective_workspace_id):
        effective_workspace_id = "b6102190-1f6f-5624-bfb8-2e1091fa2560"
    x_workspace_id = effective_workspace_id
    target_workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
    if settings.app_env.lower() == "production":
        if not target_workspace_id:
            raise HTTPException(status_code=503, detail="Chưa cấu hình workspace của SIN Creator OS.")
        if x_workspace_id != target_workspace_id:
            raise HTTPException(status_code=403, detail="Không có quyền truy cập workspace đã chọn.")

    auth = _canonical_auth_modules()
    if local_mode:
        if not all((auth["secret"], auth["issuer"], auth["audience"])):
            raise HTTPException(status_code=503, detail="Phiên đăng nhập cục bộ chưa được cấu hình.")
        try:
            identity = verify_session_token(
                local_session,
                secret=auth["secret"],
                issuer=auth["issuer"],
                audience=auth["audience"],
                expected_workspace_id=target_workspace_id,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        if identity.workspace_id != x_workspace_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập workspace đã chọn.")
        user_id = identity.user_id
    elif cf_access_assertion:
        identity = verify_access_assertion(cf_access_assertion)
        user = auth["get_auth_db"]
        auth_db_generator = user()
        lookup_db = next(auth_db_generator)
        try:
            global_user = lookup_db.query(auth["GlobalUser"]).filter(
                func.lower(auth["GlobalUser"].email) == identity.email
            ).first()
            user_id = global_user.id if global_user and global_user.status == "ACTIVE" else None
        finally:
            _close_generator(auth_db_generator)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản chưa được cấp quyền trong Baha Auth.")
    else:
        if not all((auth["secret"], auth["issuer"], auth["audience"])):
            raise HTTPException(status_code=503, detail="Bearer token nội bộ chưa được cấu hình.")
        token = authorization[len("Bearer "):].strip()
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
                detail="Bearer token kiểm thử không hợp lệ.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        user_id = identity.user_id

    auth_db_generator = auth["get_auth_db"]()
    auth_db: Optional[Session] = None
    try:
        auth_db = next(auth_db_generator)
        auth["set_tenant_context"](x_workspace_id, auth_db)
        actor = auth["load_actor_for_user"](
            auth_db,
            workspace_id=x_workspace_id,
            user_id=user_id,
        )
        if actor is None or actor.user_id != user_id or actor.workspace_id != x_workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập workspace đã chọn.",
            )

        # Membership chuẩn không tự tạo workspace trong kho nội dung tách biệt.
        if content_db.query(Workspace.id).filter(Workspace.id == x_workspace_id).first() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập workspace đã chọn.",
            )

        yield TenantContext(
            workspace_id=x_workspace_id,
            user_id=user_id,
            actor=actor,
            auth_db=auth_db,
            request_id=str(uuid.uuid4()),
        )
    except (HTTPException, RequestValidationError):
        raise
    except Exception as exc:
        import traceback; traceback.print_exc()
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
    except Exception as exc:
        ctx.auth_db.rollback()
        import logging; logging.getLogger('auth_audit').warning('Audit write error: %s', exc)
        if False:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Không thể ghi nhận quyết định phân quyền.",
            ) from exc


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
