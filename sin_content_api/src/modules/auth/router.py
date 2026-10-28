"""API trả phiên làm việc sau khi Cloudflare Access đã xác minh danh tính."""

import os
import ipaddress
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from baha_auth.src.models.entities import GlobalUser, Membership, Workspace as AuthWorkspace
from baha_auth.src.services.danh_tinh_service import load_actor_for_user
from src.auth.tenancy import _canonical_auth_modules, dev_auth_bypass_enabled, verify_access_assertion
from src.auth.mat_khau_noi_bo import (
    SESSION_COOKIE,
    create_session_token,
    local_password_mode,
    verify_password,
    verify_session_token,
)
from src.database import get_db as get_content_db
from src.models.entities import Workspace as ContentWorkspace
from src.config import settings


auth_router = APIRouter(prefix="/v1/auth", tags=["Authentication"])
_LOGIN_LIMIT = 50
_LOGIN_WINDOW_SECONDS = 15 * 60
# shortcut: giới hạn mất khi tiến trình khởi động lại; nâng cấp khi có kho phiên dùng chung.
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_login_attempts_lock = threading.Lock()


class LocalLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


def _same_site_loopback_request(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
        host = parsed.hostname or ""
    except ValueError:
        return False
    try:
        ip_obj = ipaddress.ip_address(host)
        is_allowed = ip_obj.is_loopback or host.startswith(("10.", "172.", "192.168."))
    except ValueError:
        is_allowed = host.lower() in {
            "localhost",
            "127.0.0.1",
            "192.168.1.175",
            "nhap-xaykenh-proj069.bahagroup.vn",
        } or host.lower().endswith(".bahagroup.vn")
    except Exception:
        return False
    return is_allowed


def _login_is_limited(key: str, now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    with _login_attempts_lock:
        attempts = _login_attempts[key]
        while attempts and attempts[0] <= now - _LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= _LOGIN_LIMIT


def _record_login_failure(key: str, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    with _login_attempts_lock:
        attempts = _login_attempts[key]
        while attempts and attempts[0] <= now - _LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        attempts.append(now)


def _clear_login_failures(key: str) -> None:
    with _login_attempts_lock:
        _login_attempts.pop(key, None)


def _cookie_secure() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "false").strip().casefold() in {"1", "true", "yes"}


@auth_router.post("/login")
def login_local_founder(
    payload: LocalLoginRequest,
    request: Request,
    response: Response,
):
    if not _same_site_loopback_request(request):
        raise HTTPException(status_code=403, detail="Yêu cầu đăng nhập không hợp lệ.")

    attempt_key = request.client.host if request.client else "unknown"
    if _login_is_limited(attempt_key):
        raise HTTPException(status_code=429, detail="Đăng nhập tạm thời bị giới hạn. Hãy thử lại sau.")

    # Không có giá trị mặc định cho email, hash mật khẩu, workspace: thiếu cấu hình thì từ chối.
    founder_email = os.getenv("FOUNDER_EMAIL", "").strip()
    password_hash = os.getenv("FOUNDER_PASSWORD_HASH", "").strip()
    workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
    if not (founder_email and password_hash and workspace_id):
        raise HTTPException(status_code=503, detail="Đăng nhập cục bộ chưa được cấu hình đầy đủ.")
    auth = _canonical_auth_modules()
    secret, issuer, audience = auth["secret"], auth["issuer"], auth["audience"]

    password_ok = verify_password(payload.password, password_hash)
    email_ok = payload.email.strip().casefold() == founder_email.casefold()
    if not (password_ok and email_ok):
        _record_login_failure(attempt_key)
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng.")

    # Danh tính phiên lấy từ Baha Auth DB, không dùng ID cố định trong mã nguồn.
    auth_db_generator = auth["get_auth_db"]()
    try:
        auth_db = next(auth_db_generator)
        user = auth_db.query(GlobalUser).filter(
            func.lower(GlobalUser.email) == founder_email.casefold()
        ).first()
        user_id = user.id if user and user.status == "ACTIVE" else None
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Không đọc được cơ sở dữ liệu phân quyền.") from exc
    finally:
        _close_auth_generator(auth_db_generator)
    if not user_id:
        raise HTTPException(status_code=403, detail="Tài khoản Founder chưa có trong Baha Auth hoặc không ACTIVE.")

    token = create_session_token(
        user_id,
        workspace_id,
        secret=secret,
        issuer=issuer,
        audience=audience,
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


@auth_router.get("/me")
def get_me(
    request: Request,
    cf_access_assertion: str | None = Header(None, alias="Cf-Access-Jwt-Assertion"),
    content_db: Session = Depends(get_content_db),
):
    if dev_auth_bypass_enabled(request):
        target_ws = request.headers.get("X-Workspace-Id") or os.getenv("SIN_WORKSPACE_ID", "").strip() or "b6102190-1f6f-5624-bfb8-2e1091fa2560"
        if not target_ws or target_ws in {"default_ws", "default", "undefined", "null"}:
            target_ws = "b6102190-1f6f-5624-bfb8-2e1091fa2560"
        return {
            "user": {"id": "b83ca206-f7a9-54be-a230-035cda108f4b", "email": "phuctoan235@gmail.com", "full_name": "Trần Phúc Toàn"},
            "workspace": {"id": target_ws, "name": "SIN Creator OS PRJ_069", "role": "WORKSPACE_OWNER"},
            "workspaces": [{"id": target_ws, "name": "SIN Creator OS PRJ_069", "role": "WORKSPACE_OWNER"}],
        }
    local_mode = local_password_mode(settings.app_env)
    auth = _canonical_auth_modules()
    if local_mode:
        token = request.cookies.get(SESSION_COOKIE)
        target_workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
        if not token:
            raise HTTPException(status_code=401, detail="Cần đăng nhập vào SIN Creator OS.")
        if not target_workspace_id:
            raise HTTPException(status_code=503, detail="Chưa cấu hình workspace của SIN Creator OS.")
        try:
            identity = verify_session_token(
                token,
                secret=auth["secret"],
                issuer=auth["issuer"],
                audience=auth["audience"],
                expected_workspace_id=target_workspace_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.") from exc
        user_filter = GlobalUser.id == identity.user_id
    else:
        identity = verify_access_assertion(cf_access_assertion)
        user_filter = func.lower(GlobalUser.email) == (identity.email or "").casefold()

    auth_db_generator = auth["get_auth_db"]()
    auth_db: Session | None = None
    try:
        auth_db = next(auth_db_generator)
        user = auth_db.query(GlobalUser).filter(user_filter).first()
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản chưa được cấp quyền trong Baha Auth.")

        target_workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
        if settings.app_env.lower() == "production" and not target_workspace_id:
            raise HTTPException(status_code=503, detail="Chưa cấu hình workspace của SIN Creator OS.")
        memberships = auth_db.query(Membership).join(AuthWorkspace).filter(
            Membership.user_id == user.id,
            Membership.status == "ACTIVE",
            AuthWorkspace.status == "ACTIVE",
        )
        if target_workspace_id:
            memberships = memberships.filter(Membership.workspace_id == target_workspace_id)

        workspaces = []
        for membership in memberships.all():
            workspace = membership.workspace
            content_workspace = content_db.query(ContentWorkspace).filter(
                ContentWorkspace.id == workspace.id,
            ).first()
            if not content_workspace:
                continue
            actor = load_actor_for_user(auth_db, workspace.id, user.id)
            if not actor:
                continue
            roles = [grant["role_code"] for grant in actor.roles]
            role = "WORKSPACE_OWNER" if "WORKSPACE_OWNER" in roles else (roles[0] if roles else "MEMBER")
            workspaces.append({"id": workspace.id, "name": workspace.name, "role": role})

        if not workspaces:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản chưa có workspace được cấp trong SIN Creator OS.")
        return {
            "user": {"id": user.id, "email": user.email, "full_name": user.full_name or user.email},
            "workspace": workspaces[0],
            "workspaces": workspaces,
        }
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
        _close_auth_generator(auth_db_generator)


def _close_auth_generator(generator):
    close = getattr(generator, "close", None)
    if close:
        close()
