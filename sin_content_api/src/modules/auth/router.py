# -*- coding: utf-8 -*-
"""Router xác thực (Authentication) cho PRJ_069 Content Intelligence & BAHA Creator Studio."""

import os
import time
import json
import base64
import hmac
import hashlib
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status, Header

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    email: str
    password: str

class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str
    role: str

class WorkspaceSummary(BaseModel):
    id: str
    name: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
    workspace: WorkspaceSummary

def _create_jwt(user_id: str, email: str, full_name: str, role: str, workspace_id: str) -> str:
    secret = os.getenv("BAHA_AUTH_JWT_SECRET", "sin-dev-secret-do-not-use-in-production")
    issuer = os.getenv("BAHA_AUTH_JWT_ISSUER", "baha-auth-issuer")
    audience = os.getenv("BAHA_AUTH_JWT_AUDIENCE", "sin-content-test")

    def b64url(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "sub": user_id,
        "iss": issuer,
        "aud": audience,
        "exp": int(time.time()) + 86400 * 30, # 30 ngày
        "workspace_id": workspace_id,
        "email": email,
        "name": full_name,
        "role": role,
    }

    enc_header = b64url(json.dumps(header).encode("utf-8"))
    enc_payload = b64url(json.dumps(claims).encode("utf-8"))
    sig_input = f"{enc_header}.{enc_payload}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), sig_input, hashlib.sha256).digest()
    enc_sig = b64url(sig)

    return f"{enc_header}.{enc_payload}.{enc_sig}"

@auth_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """
    Xác thực người dùng và cấp JWT Bearer Token có hiệu lực cao nhất.
    Hỗ trợ tài khoản Quản trị tối cao (sin@test.com / 121232).
    """
    clean_email = payload.email.strip().lower()
    
    # 1. Kiểm tra tài khoản Quản trị tối cao của Founder
    if clean_email == "sin@test.com" and payload.password == "121232":
        token = _create_jwt(
            user_id="usr_sin_owner",
            email="sin@test.com",
            full_name="Sin Admin (Highest Privilege)",
            role="PLATFORM_OWNER",
            workspace_id="default_ws",
        )
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserProfile(
                id="usr_sin_owner",
                email="sin@test.com",
                full_name="Sin Admin (Highest Privilege)",
                role="PLATFORM_OWNER",
            ),
            workspace=WorkspaceSummary(
                id="default_ws",
                name="BAHA Group Workspace",
            ),
        )

    # 2. Hỗ trợ tài khoản mặc định Creator
    if clean_email == "creator@baha.vn" and payload.password == "123456":
        token = _create_jwt(
            user_id="usr_creator_default",
            email="creator@baha.vn",
            full_name="BAHA Creator",
            role="WORKSPACE_OWNER",
            workspace_id="default_ws",
        )
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserProfile(
                id="usr_creator_default",
                email="creator@baha.vn",
                full_name="BAHA Creator",
                role="WORKSPACE_OWNER",
            ),
            workspace=WorkspaceSummary(
                id="default_ws",
                name="BAHA Group Workspace",
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Email hoặc mật khẩu không chính xác.",
        headers={"WWW-Authenticate": "Bearer"},
    )

@auth_router.get("/me")
def get_me(authorization: Optional[str] = Header(None)):
    """Trả về thông tin phiên đăng nhập hiện tại từ Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Thiếu token xác thực.")
    token = authorization[len("Bearer "):].strip()
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError()
        raw_payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(raw_payload.encode("ascii")).decode("utf-8"))
        return {
            "user_id": claims.get("sub"),
            "email": claims.get("email"),
            "full_name": claims.get("name"),
            "role": claims.get("role"),
            "workspace_id": claims.get("workspace_id"),
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Token không hợp lệ.")
