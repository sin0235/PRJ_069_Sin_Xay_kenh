"""Đăng nhập mật khẩu cho owner đã được cấp quyền trong Baha Auth."""

import hashlib
import hmac
import math
import os
import ipaddress
import threading
import time
from collections import OrderedDict
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from baha_auth.src.database import get_db as get_auth_db, set_tenant_context
from baha_auth.src.models.entities import GlobalUser, Membership as AuthMembership, Workspace as AuthWorkspace
from baha_auth.src.services.danh_tinh_service import load_actor_for_user
from baha_auth.src.services.local_password import get_password_hash
from src.auth.mat_khau_noi_bo import SESSION_SECONDS, create_session_token, verify_password
from src.auth.tenancy import TenantContext, require_action, require_trusted_origin
from src.config import settings
from src.database import get_db as get_content_db
from src.models.entities import Workspace as ContentWorkspace


auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
auth_session_router = APIRouter(prefix="/v1/auth", tags=["Authentication"])

_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 900
_LOGIN_BUCKET_LIMIT = 4096
_login_attempts: OrderedDict[str, tuple[float, int]] = OrderedDict()
_login_attempts_lock = Lock()


class LoginRequest(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)
    workspace_id: Optional[str] = Field(default=None, max_length=64)




class WorkspaceSummary(BaseModel):
    id: str
    name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
    workspace: WorkspaceSummary


def _login_key(request: Request, email: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    value = f"{client_host.casefold()}\0{email.casefold()}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _login_retry_after(key: str, now: float) -> int:
    with _login_attempts_lock:
        state = _login_attempts.get(key)
        if state is None:
            return 0
        started, attempts = state
        if now - started >= _LOGIN_WINDOW_SECONDS:
            del _login_attempts[key]
            return 0
        _login_attempts.move_to_end(key)
        if attempts < _LOGIN_MAX_ATTEMPTS:
            return 0
        return max(1, math.ceil(_LOGIN_WINDOW_SECONDS - (now - started)))


def _record_login_failure(key: str, now: float) -> None:
    with _login_attempts_lock:
        state = _login_attempts.get(key)
        if state is None or now - state[0] >= _LOGIN_WINDOW_SECONDS:
            _login_attempts[key] = (now, 1)
        else:
            _login_attempts[key] = (state[0], state[1] + 1)
            _login_attempts.move_to_end(key)
        expired = [bucket for bucket, (started, _) in _login_attempts.items()
                   if now - started >= _LOGIN_WINDOW_SECONDS]
        for bucket in expired:
            _login_attempts.pop(bucket, None)
        while len(_login_attempts) > _LOGIN_BUCKET_LIMIT:
            _login_attempts.popitem(last=False)


def _clear_login_failures(key: str) -> None:
    with _login_attempts_lock:
        _login_attempts.pop(key, None)


def _owner_login_identity(
    *,
    email: str,
    password: str,
    workspace_id: str,
    auth_db: Session,
    content_db: Session,
) -> tuple[GlobalUser, AuthWorkspace, str] | None:
    if not settings.auth_owner_email and not settings.platform_owner_ids_set:
        raise HTTPException(status_code=503, detail="Chưa cấu hình danh tính owner.")

    user = auth_db.query(GlobalUser).filter(func.lower(GlobalUser.email) == email).first()
    password_hash = get_password_hash(auth_db, user.id) if user else None
    password_matches = verify_password(password, password_hash)
    is_configured_owner = bool(
        user
        and (
            user.email.casefold() == settings.auth_owner_email
            or user.id in settings.platform_owner_ids_set
        )
    )
    if not user or user.status != "ACTIVE" or not is_configured_owner or not password_matches:
        return None

    set_tenant_context(workspace_id, auth_db)
    membership = auth_db.query(AuthMembership).filter(
        AuthMembership.workspace_id == workspace_id,
        AuthMembership.user_id == user.id,
        AuthMembership.status == "ACTIVE",
    ).first()
    workspace = auth_db.query(AuthWorkspace).filter(
        AuthWorkspace.id == workspace_id,
        AuthWorkspace.status == "ACTIVE",
    ).first()
    actor = load_actor_for_user(auth_db, workspace_id, user.id)
    if not membership or not workspace or not actor:
        return None

    owner_role = next((
        role for role in actor.roles
        if role.get("role_code") in {"WORKSPACE_OWNER", "PLATFORM_OWNER"}
        and role.get("scope_type") == "WORKSPACE"
        and role.get("scope_id") in {None, workspace_id}
        and role.get("assignment_status") == "ACTIVE"
        and role.get("role_status") == "ACTIVE"
        and role.get("is_active") is True
    ), None)
    if not owner_role or not content_db.query(ContentWorkspace.id).filter(
        ContentWorkspace.id == workspace_id
    ).first():
        return None
    return user, workspace, owner_role["role_code"]


def _create_jwt(user_id: str, workspace_id: str) -> str:
    secret = os.getenv("BAHA_AUTH_JWT_SECRET", "").strip()
    issuer = os.getenv("BAHA_AUTH_JWT_ISSUER", "").strip()
    audience = os.getenv("BAHA_AUTH_JWT_AUDIENCE", "").strip()
    if not all((secret, issuer, audience)) or (
        settings.app_env.casefold() == "production" and len(secret.encode("utf-8")) < 32
    ):
        raise HTTPException(status_code=503, detail="Dịch vụ xác thực chưa được cấu hình an toàn.")
    return create_session_token(
        user_id,
        workspace_id,
        secret=secret,
        issuer=issuer,
        audience=audience,
        lifetime_seconds=SESSION_SECONDS,
    )
    _clear_login_failures(attempt_key)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=8 * 60 * 60,
        path="/",
        secure=False,
        httponly=True,
        samesite="lax",
    )
    return {"success": True}


@auth_router.post("/logout")
def logout_local_founder(request: Request, response: Response):
    if not _same_site_loopback_request(request):
        raise HTTPException(status_code=403, detail="Yêu cầu đăng xuất không hợp lệ.")
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=_cookie_secure(),
        httponly=True,
        samesite="strict",
    )
    return {"success": True}



@auth_router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    auth_db: Session = Depends(get_auth_db),
    content_db: Session = Depends(get_content_db),
) -> LoginResponse:
    require_trusted_origin(request, required=settings.app_env.casefold() == "production")
    email = payload.email.strip().casefold()
    bucket = _login_key(request, email)
    now = time.monotonic()
    retry_after = _login_retry_after(bucket, now)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Đăng nhập tạm thời bị giới hạn. Vui lòng thử lại sau.",
            headers={"Retry-After": str(retry_after)},
        )

    workspace_id = payload.workspace_id or settings.auth_workspace_id
    if not workspace_id:
        raise HTTPException(status_code=503, detail="Chưa cấu hình workspace đăng nhập.")
    identity = _owner_login_identity(
        email=email,
        password=payload.password,
        workspace_id=workspace_id,
        auth_db=auth_db,
        content_db=content_db,
    )
    if identity is None:
        _record_login_failure(bucket, now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _clear_login_failures(bucket)
    user, workspace, role_code = identity
    token = _create_jwt(user.id, workspace.id)
    return LoginResponse(
        access_token=token,
        user=UserProfile(
            id=user.id,
            email=user.email,
            full_name=user.full_name or user.email,
            role=role_code,
        ),
        workspace=WorkspaceSummary(id=workspace.id, name=workspace.name),
    )


@auth_session_router.get("/me", include_in_schema=False)
@auth_router.get("/me")
def get_me(tenant: TenantContext = Depends(require_action("workspace.read"))) -> dict[str, object]:
    if tenant.dev_auth_bypass or tenant.auth_db is None or tenant.actor is None:
        raise HTTPException(status_code=401, detail="Cần phiên xác thực hợp lệ.")
    user = tenant.auth_db.get(GlobalUser, tenant.user_id)
    workspace = tenant.auth_db.get(AuthWorkspace, tenant.workspace_id)
    if not user or not workspace:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập không còn hợp lệ.")
    role = next((
        grant["role_code"] for grant in tenant.actor.roles
        if grant.get("scope_type") == "WORKSPACE"
        and grant.get("assignment_status") == "ACTIVE"
    ), "")
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name or user.email,
            "role": role,
        },
        "workspace": {"id": workspace.id, "name": workspace.name},
        "workspace_id": tenant.workspace_id,
        "request_id": tenant.request_id,
    }
