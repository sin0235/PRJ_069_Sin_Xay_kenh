import uuid

import pytest
from fastapi.testclient import TestClient

from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.models.entities import GlobalUser, Workspace as AuthWorkspace
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import BrandBriefVersion, Workspace
from src.auth.mat_khau_noi_bo import hash_password
from src.config import settings
from src.modules.auth import router as auth_router
from tests.conftest import setup_test_auth_user


@pytest.fixture
def founder_local(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setenv("DEV_AUTH_BYPASS", "0")
    monkeypatch.setenv("AUTH_MODE", "local_password")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "0")
    monkeypatch.setenv("FOUNDER_EMAIL", "phuctoan235@gmail.com")
    monkeypatch.setenv("FOUNDER_PASSWORD_HASH", hash_password("mat-khau-founder-kiem-thu"))
    monkeypatch.setenv("BAHA_AUTH_JWT_SECRET", "secret-chi-dung-trong-kiem-thu")
    monkeypatch.setenv("BAHA_AUTH_JWT_ISSUER", "issuer-kiem-thu")
    monkeypatch.setenv("BAHA_AUTH_JWT_AUDIENCE", "audience-kiem-thu")
    workspace_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    monkeypatch.setenv("SIN_WORKSPACE_ID", workspace_id)
    monkeypatch.setattr(settings, "app_env", "production")
    auth_router._clear_login_failures("testclient")

    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    auth_db = AuthSessionLocal()
    content_db = SessionLocal()
    try:
        auth_db.add(AuthWorkspace(id=workspace_id, name="PRJ_069", slug=f"prj069-{uuid.uuid4().hex[:8]}", status="ACTIVE"))
        auth_db.add(GlobalUser(id=user_id, email="phuctoan235@gmail.com", full_name="Founder PRJ_069", status="ACTIVE"))
        content_db.add(Workspace(id=workspace_id, name="PRJ_069", slug=f"prj069-{uuid.uuid4().hex[:8]}"))
        brief_id = str(uuid.uuid4())
        content_db.add(BrandBriefVersion(
            id=brief_id,
            workspace_id=workspace_id,
            version=1,
            brand_name="Kênh thử nghiệm",
            objective="Kiểm tra phiên Founder",
            voice_description="Rõ ràng",
            current_audience="Người xem TikTok",
            target_audience="Người xem TikTok",
            topics_included_json='["video"]',
            topics_excluded_json='[]',
            status="APPROVED",
        ))
        auth_db.commit()
        content_db.commit()
        setup_test_auth_user(auth_db, workspace_id, user_id, "phuctoan235@gmail.com", "WORKSPACE_OWNER")
    finally:
        auth_db.close()
        content_db.close()

    yield {"workspace_id": workspace_id, "brief_id": brief_id}

    auth_db = AuthSessionLocal()
    content_db = SessionLocal()
    try:
        auth_workspace = auth_db.query(AuthWorkspace).filter(AuthWorkspace.id == workspace_id).first()
        if auth_workspace:
            auth_db.delete(auth_workspace)
        auth_user = auth_db.query(GlobalUser).filter(GlobalUser.id == user_id).first()
        if auth_user:
            auth_db.delete(auth_user)
        auth_db.commit()
        content_workspace = content_db.query(Workspace).filter(Workspace.id == workspace_id).first()
        if content_workspace:
            content_db.delete(content_workspace)
        content_db.commit()
    finally:
        auth_db.close()
        content_db.close()


def test_founder_dang_nhap_va_dung_cookie_truy_cap_api_workspace(founder_local):
    client = TestClient(app)
    response = client.post(
        "/v1/auth/login",
        headers={"Origin": "http://127.0.0.1:3000"},
        json={"email": "phuctoan235@gmail.com", "password": "mat-khau-founder-kiem-thu"},
    )

    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].casefold()
    assert "samesite=strict" in response.headers["set-cookie"].casefold()
    session = client.get("/v1/auth/me")
    assert session.status_code == 200
    assert session.json()["workspace"]["id"] == founder_local["workspace_id"]
    brief = client.get(f"/v1/briefs/{founder_local['brief_id']}", headers={"X-Workspace-Id": founder_local["workspace_id"]})
    assert brief.status_code == 200


def test_sai_mat_khau_va_origin_khac_local_bi_tu_choi(founder_local):
    client = TestClient(app)
    wrong_password = client.post(
        "/v1/auth/login",
        headers={"Origin": "http://127.0.0.1:3000"},
        json={"email": "phuctoan235@gmail.com", "password": "khong-dung"},
    )
    foreign_origin = client.post(
        "/v1/auth/login",
        headers={"Origin": "https://example.invalid"},
        json={"email": "phuctoan235@gmail.com", "password": "mat-khau-founder-kiem-thu"},
    )

    assert wrong_password.status_code == 401
    assert "set-cookie" not in wrong_password.headers
    assert foreign_origin.status_code == 403


def test_cookie_founder_khong_dung_duoc_workspace_khac(founder_local):
    client = TestClient(app)
    login = client.post(
        "/v1/auth/login",
        headers={"Origin": "http://127.0.0.1:3000"},
        json={"email": "phuctoan235@gmail.com", "password": "mat-khau-founder-kiem-thu"},
    )
    assert login.status_code == 200

    response = client.get(f"/v1/briefs/{founder_local['brief_id']}", headers={"X-Workspace-Id": str(uuid.uuid4())})
    assert response.status_code == 403
