"""Xác thực owner nền tảng từ danh tính được cấu hình, không tin role trong JWT."""

from typing import Optional

from fastapi import Cookie, Header, HTTPException, Request, status

from baha_auth.src.models.entities import GlobalUser
from src.auth.tenancy import _canonical_auth_modules, dev_auth_bypass_enabled, require_trusted_origin
from src.config import settings


def _is_configured_owner(user_id: str, workspace_id: Optional[str]) -> bool:
    configured_by_id = user_id in settings.platform_owner_ids_set
    if not configured_by_id and not settings.auth_owner_email:
        return False
    if not workspace_id:
        return configured_by_id and settings.app_env.casefold() != "production"

    auth = _canonical_auth_modules()
    auth_db_generator = auth["get_auth_db"]()
    auth_db = next(auth_db_generator)
    try:
        auth["set_tenant_context"](workspace_id, auth_db)
        user = auth_db.get(GlobalUser, user_id)
        actor = auth["load_actor_for_user"](auth_db, workspace_id=workspace_id, user_id=user_id)
        return bool(
            user
            and user.status == "ACTIVE"
            and (
                configured_by_id
                or user.email.casefold() == settings.auth_owner_email
            )
            and actor
            and any(
                grant.get("role_code") in {"WORKSPACE_OWNER", "PLATFORM_OWNER"}
                and grant.get("scope_type") == "WORKSPACE"
                and grant.get("scope_id") in {None, workspace_id}
                and grant.get("assignment_status") == "ACTIVE"
                and grant.get("role_status") == "ACTIVE"
                and grant.get("is_active") is True
                for grant in actor.roles
            )
        )
    finally:
        try:
            auth["clear_tenant_context"](auth_db)
        finally:
            close = getattr(auth_db_generator, "close", None)
            if close is not None:
                close()


def require_platform_owner(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    baha_auth_token: Optional[str] = Cookie(None, alias="baha_auth_token"),
) -> str:
    """Trả user_id khi JWT và danh tính owner được cấu hình còn hợp lệ."""
    if dev_auth_bypass_enabled(request):
        return "dev-user"

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

    auth = _canonical_auth_modules()
    if cf_access_assertion:
        identity = verify_access_assertion(cf_access_assertion)
        auth_db_generator = auth["get_auth_db"]()
        try:
            auth_db = next(auth_db_generator)
            user = auth_db.query(auth["GlobalUser"]).filter(
                func.lower(auth["GlobalUser"].email) == identity.email,
            ).first()
            user_id = user.id if user and user.status == "ACTIVE" else None
        finally:
            close = getattr(auth_db_generator, "close", None)
            if close:
                close()
        if not user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản chưa được cấp quyền nền tảng.")
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

    if not _is_configured_owner(identity.user_id, identity.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền Quản Trị Viên Nền Tảng (Platform Owner).",
        )
    return identity.user_id
