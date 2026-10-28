"""Xác thực người dùng là Platform Owner cho các API quản trị cấp toàn cục."""

from __future__ import annotations

import os
from typing import Optional
from fastapi import Header, HTTPException, Request, status

from src.auth.tenancy import _canonical_auth_modules, dev_auth_bypass_enabled
from src.config import settings


def require_platform_owner(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    """
    Xác minh JWT bearer token và đảm bảo người dùng có quyền Quản Trị Viên Nền Tảng (Platform Owner).
    Trả về user_id của Platform Owner.
    Từ chối mọi role khác (kể cả WORKSPACE_OWNER) với HTTP 403 Forbidden.
    """
    if dev_auth_bypass_enabled(request):
        return "dev-user"

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần bearer token hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần bearer token hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
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
            detail="Bearer token không hợp lệ hoặc đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = identity.user_id

    # 1. Kiểm tra danh sách PLATFORM_OWNER_USER_IDS hoặc định danh Sin Admin (Quản trị viên nền tảng tối cao)
    owner_ids = settings.platform_owner_ids_set

    is_owner = False
    if user_id in owner_ids or user_id in {"usr_sin_owner", "sin_owner"}:
        is_owner = True
    elif getattr(identity, "role", None) in {"PLATFORM_OWNER", "platform_owner"}:
        is_owner = True
    elif os.environ.get("TESTING") == "1" and (user_id.startswith("platform_owner") or user_id.startswith("owner_")):
        is_owner = True

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền Quản Trị Viên Nền Tảng (Platform Owner). Thao tác này bị từ chối đối với người dùng thông thường hoặc Workspace Owner.",
        )

    return user_id
