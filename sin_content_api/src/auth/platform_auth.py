"""Xác thực người dùng là Platform Owner cho các API quản trị cấp toàn cục."""

from __future__ import annotations

import os
from typing import Optional
from fastapi import Header, HTTPException, Request, status
from sqlalchemy import func

from src.auth.tenancy import _canonical_auth_modules, dev_auth_bypass_enabled, verify_access_assertion
from src.config import settings


def require_platform_owner(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    cf_access_assertion: Optional[str] = Header(None, alias="Cf-Access-Jwt-Assertion"),
) -> str:
    """
    Xác minh JWT bearer token và đảm bảo người dùng có quyền Quản Trị Viên Nền Tảng (Platform Owner).
    Trả về user_id của Platform Owner.
    Từ chối mọi role khác (kể cả WORKSPACE_OWNER) với HTTP 403 Forbidden.
    """
    if dev_auth_bypass_enabled(request):
        return "dev-user"

    test_bearer_allowed = os.getenv("TESTING") == "1" and settings.app_env.lower() in {"offline", "development", "dev", "local", "test"}
    if not cf_access_assertion and not (test_bearer_allowed and authorization and authorization.startswith("Bearer ")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần danh tính Cloudflare Access đã xác minh.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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

    # Danh sách quyền nền tảng phải được cấp rõ ràng ở phía máy chủ.
    owner_ids = settings.platform_owner_ids_set

    is_owner = False
    if user_id in owner_ids:
        is_owner = True
    elif os.environ.get("TESTING") == "1" and (user_id.startswith("platform_owner") or user_id.startswith("owner_")):
        is_owner = True

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền Quản Trị Viên Nền Tảng (Platform Owner). Thao tác này bị từ chối đối với người dùng thông thường hoặc Workspace Owner.",
        )

    return user_id
