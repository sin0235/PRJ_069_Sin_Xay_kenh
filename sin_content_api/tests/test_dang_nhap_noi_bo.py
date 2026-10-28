"""Kiểm thử đăng nhập Founder cục bộ: danh tính lấy từ Baha Auth DB, không có mật khẩu dự phòng."""

import base64
import json
import os
import sys
import uuid
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///file:sin_content_login_test?mode=memory&cache=shared&uri=true"
os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///file:baha_auth_login_test?mode=memory&cache=shared&uri=true"
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-dang-nhap-bang-khoa-gia-lap-0123456789"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-dang-nhap"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from fastapi.testclient import TestClient

from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.models.entities import GlobalUser
from src.auth.mat_khau_noi_bo import SESSION_COOKIE, hash_password
from src.main import app
from src.modules.auth import router as auth_router

MAT_KHAU = "mat-khau-kiem-thu-12-ky-tu"
EMAIL = "founder-kiem-thu@example.invalid"
WORKSPACE_ID = str(uuid.uuid4())

client = TestClient(app)


@pytest.fixture(autouse=True)
def cau_hinh(monkeypatch):
    monkeypatch.setenv("FOUNDER_EMAIL", EMAIL)
    monkeypatch.setenv("FOUNDER_PASSWORD_HASH", hash_password(MAT_KHAU))
    monkeypatch.setenv("SIN_WORKSPACE_ID", WORKSPACE_ID)
    auth_router._login_attempts.clear()
    AuthBase.metadata.create_all(bind=AuthEngine)
    with AuthSessionLocal() as db:
        db.query(GlobalUser).delete()
        db.commit()


def tao_founder(status="ACTIVE") -> str:
    user_id = str(uuid.uuid4())
    with AuthSessionLocal() as db:
        db.add(GlobalUser(id=user_id, email=EMAIL, status=status))
        db.commit()
    return user_id


def doc_sub(token: str) -> str:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["sub"]


def dang_nhap(mat_khau=MAT_KHAU):
    return client.post("/v1/auth/login", json={"email": EMAIL, "password": mat_khau})


def test_phien_mang_id_nguoi_dung_trong_auth_db():
    user_id = tao_founder()
    response = dang_nhap()
    assert response.status_code == 200
    assert doc_sub(response.cookies[SESSION_COOKIE]) == user_id


def test_mat_khau_du_phong_cu_bi_tu_choi():
    tao_founder()
    assert dang_nhap("BahaGroup@2026").status_code == 401


def test_sai_mat_khau_bi_tu_choi():
    tao_founder()
    assert dang_nhap("mat-khau-sai-hoan-toan").status_code == 401


def test_founder_chua_co_trong_auth_db_bi_tu_choi():
    assert dang_nhap().status_code == 403


def test_founder_khong_active_bi_tu_choi():
    tao_founder(status="SUSPENDED")
    assert dang_nhap().status_code == 403


def test_thieu_cau_hinh_thi_tu_choi(monkeypatch):
    tao_founder()
    monkeypatch.delenv("FOUNDER_PASSWORD_HASH")
    assert dang_nhap().status_code == 503
