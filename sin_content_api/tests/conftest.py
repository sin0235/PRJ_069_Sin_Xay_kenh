# conftest.py: Cau hinh moi truong kiem thu va Auth Fixture chuan cho SIN Content Intelligence API
import os
import sys
import uuid
import time
import json
import base64
import hmac
import hashlib
from pathlib import Path

# 1. Luon them thu muc goc api va project root vao sys.path
api_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
project_root = os.path.abspath(os.path.join(api_root, ".."))
for p in [api_root, project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

# 2. Thiet lap JWT Secrets va DB mac dinh truoc khi import bat ky module nao
os.environ.setdefault("APP_ENV", "offline")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("LLM_ENABLED", "false")
os.environ.setdefault("BAHA_AUTH_JWT_SECRET", "kiem-thu-bang-khoa-gia-lap")
os.environ.setdefault("BAHA_AUTH_JWT_ISSUER", "kiem-thu-nha-cung-cap")
os.environ.setdefault("BAHA_AUTH_JWT_AUDIENCE", "sin-content-test")
os.environ.setdefault("BAHA_AUTH_DATABASE_URL", "sqlite:///file:baha_auth_conftest_test?mode=memory&cache=shared&uri=true")
os.environ.setdefault("DATABASE_URL", "sqlite:///file:sin_content_conftest_test?mode=memory&cache=shared&uri=true")

import pytest
from baha_auth.src.models.entities import (
    GlobalUser, Membership as AuthMembership, Role as AuthRole, RoleAssignment, Workspace as AuthWorkspace
)

def tao_bearer_token(user_id: str) -> str:
    """Sinh JWT token Bearer hop le phuc vu kiem thu xac thuc baha_auth."""
    secret = os.environ.get("BAHA_AUTH_JWT_SECRET", "kiem-thu-bang-khoa-gia-lap")
    issuer = os.environ.get("BAHA_AUTH_JWT_ISSUER", "kiem-thu-nha-cung-cap")
    audience = os.environ.get("BAHA_AUTH_JWT_AUDIENCE", "sin-content-test")

    def encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = encode({"alg": "HS256", "typ": "JWT"})
    claims = encode({
        "sub": user_id,
        "iss": issuer,
        "aud": audience,
        "exp": int(time.time()) + 3600,
    })
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{header}.{claims}.{encoded_signature}"

def setup_test_auth_user(auth_db, ws_id: str, user_id: str, email: str, role_code: str = "WORKSPACE_OWNER"):
    """Thiet lap user va vai tro trong CSDL baha_auth phuc vu kiem thu."""
    auth_ws = auth_db.query(AuthWorkspace).filter(AuthWorkspace.id == ws_id).first()
    if not auth_ws:
        auth_ws = AuthWorkspace(id=ws_id, name=f"WS-{ws_id[:8]}", slug=f"slug-{ws_id[:8]}", status="ACTIVE")
        auth_db.add(auth_ws)
        auth_db.flush()

    auth_user = auth_db.query(GlobalUser).filter(GlobalUser.id == user_id).first()
    if not auth_user:
        auth_user = GlobalUser(id=user_id, email=email, status="ACTIVE")
        auth_db.add(auth_user)
        auth_db.flush()

    auth_mem = auth_db.query(AuthMembership).filter(
        AuthMembership.workspace_id == ws_id, AuthMembership.user_id == user_id
    ).first()
    if not auth_mem:
        auth_mem = AuthMembership(id=str(uuid.uuid4()), workspace_id=ws_id, user_id=user_id, status="ACTIVE")
        auth_db.add(auth_mem)
        auth_db.flush()

    role = auth_db.query(AuthRole).filter(AuthRole.code == role_code).first()
    if not role:
        role = AuthRole(code=role_code, name=role_code, workspace_id=None, is_template=True, status="ACTIVE")
        auth_db.add(role)
        auth_db.flush()

    ra = auth_db.query(RoleAssignment).filter(
        RoleAssignment.workspace_id == ws_id, RoleAssignment.membership_id == auth_mem.id
    ).first()
    if not ra:
        ra = RoleAssignment(
            workspace_id=ws_id,
            membership_id=auth_mem.id,
            role_id=role.id,
            scope_type="WORKSPACE",
            scope_id=ws_id,
            status="ACTIVE"
        )
        auth_db.add(ra)
        auth_db.flush()

    auth_db.commit()

setup_auth_user = setup_test_auth_user


@pytest.fixture(autouse=True)
def clean_dieu_phoi_dung_store():
    """Tự động dọn sạch kho lưu trữ điều phối dựng giữa các test."""
    try:
        from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
        QuanLyPhienDung.xoa_toan_bo_du_lieu_tam()
    except Exception:
        pass
    yield
    try:
        from src.modules.dieu_phoi_dung.phien_dung import QuanLyPhienDung
        QuanLyPhienDung.xoa_toan_bo_du_lieu_tam()
    except Exception:
        pass

