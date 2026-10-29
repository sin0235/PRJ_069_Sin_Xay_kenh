import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.services.danh_tinh_service import load_actor_for_user
from src.auth import tenancy
from src.auth.platform_auth import require_platform_owner
from src.config import settings
from src.database import Base, SessionLocal, engine
from src.models.entities import Workspace as ContentWorkspace
from src.modules.auth.router import auth_router
from tests.conftest import setup_test_auth_user


app = FastAPI()
app.include_router(auth_router)


@app.post("/protected-test-route")
def _protected_test_route(tenant: tenancy.TenantContext = Depends(tenancy.get_current_tenant_context)):
    return {"user_id": tenant.user_id, "workspace_id": tenant.workspace_id}


ORIGIN = "https://studio.example.test"
PASSWORD = "test-only-owner-password"


def _password_hash(password: str) -> str:
    salt = b"auth-test-salt"
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
    return f"pbkdf2_sha256$600000${encode(salt)}${encode(derived)}"


@pytest.fixture
def configured_owner(monkeypatch):
    AuthBase.metadata.create_all(bind=AuthEngine)
    Base.metadata.create_all(bind=engine)
    user_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    email = f"owner-{uuid.uuid4().hex}@example.test"

    with AuthSessionLocal() as db:
        setup_test_auth_user(db, workspace_id, user_id, email, "WORKSPACE_OWNER")
        db.execute(text(
            "CREATE TABLE IF NOT EXISTS local_password_credentials "
            "(user_id VARCHAR(36) PRIMARY KEY, password_hash VARCHAR(512) NOT NULL)"
        ))
        db.execute(
            text("INSERT INTO local_password_credentials (user_id, password_hash) VALUES (:user_id, :password_hash)"),
            {"user_id": user_id, "password_hash": _password_hash(PASSWORD)},
        )
        db.commit()

    with SessionLocal() as db:
        db.add(ContentWorkspace(id=workspace_id, name="Test workspace", slug=f"test-{workspace_id}"))
        db.commit()

    monkeypatch.setitem(settings.__dict__, "auth_owner_email", email)
    monkeypatch.setitem(settings.__dict__, "auth_workspace_id", workspace_id)
    monkeypatch.setitem(settings.__dict__, "auth_allowed_origins", ORIGIN)
    monkeypatch.setattr(settings, "platform_owner_user_ids", "")
    return {"user_id": user_id, "workspace_id": workspace_id, "email": email}


def test_configured_owner_can_log_in_with_stored_password(configured_owner):
    response = TestClient(app).post(
        "/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": configured_owner["email"], "password": PASSWORD},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == configured_owner["user_id"]
    assert data["workspace"]["id"] == configured_owner["workspace_id"]
    assert data["access_token"]


def test_login_cookie_authenticates_me_and_rechecks_workspace(configured_owner):
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": configured_owner["email"], "password": PASSWORD},
    )
    assert login.status_code == 200

    client.cookies.set("baha_auth_token", login.json()["access_token"])
    response = client.get(
        "/auth/me",
        headers={"X-Workspace-Id": configured_owner["workspace_id"]},
    )

    assert response.status_code == 200
    assert response.json()["workspace_id"] == configured_owner["workspace_id"]


def test_cookie_session_resolves_workspace_without_local_workspace_header(configured_owner):
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": configured_owner["email"], "password": PASSWORD},
    )
    assert login.status_code == 200
    client.cookies.set("baha_auth_token", login.json()["access_token"])

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["workspace_id"] == configured_owner["workspace_id"]
    assert response.json()["user"]["id"] == configured_owner["user_id"]


def test_cookie_auth_requires_trusted_origin_for_mutations(configured_owner):
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": configured_owner["email"], "password": PASSWORD},
    )
    assert login.status_code == 200
    client.cookies.set("baha_auth_token", login.json()["access_token"])

    headers = {"X-Workspace-Id": configured_owner["workspace_id"]}
    assert client.post("/protected-test-route", headers=headers).status_code == 403
    assert client.post(
        "/protected-test-route",
        headers={**headers, "Origin": "https://attacker.example"},
    ).status_code == 403
    assert client.post(
        "/protected-test-route",
        headers={**headers, "Origin": f"{ORIGIN}/"},
    ).status_code == 403
    allowed = client.post(
        "/protected-test-route",
        headers={**headers, "Origin": ORIGIN},
    )
    assert allowed.status_code == 200
    assert allowed.json()["user_id"] == configured_owner["user_id"]


def test_empty_legacy_bearer_header_does_not_mask_session_cookie(configured_owner):
    client = TestClient(app)
    login = client.post(
        "/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": configured_owner["email"], "password": PASSWORD},
    )
    assert login.status_code == 200
    client.cookies.set("baha_auth_token", login.json()["access_token"])

    response = client.post(
        "/protected-test-route",
        headers={
            "Authorization": "Bearer ",
            "Origin": ORIGIN,
            "X-Workspace-Id": configured_owner["workspace_id"],
        },
    )
    assert response.status_code == 200


def test_login_rejects_untrusted_origin_even_for_valid_owner(configured_owner):
    response = TestClient(app).post(
        "/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"email": configured_owner["email"], "password": PASSWORD},
    )

    assert response.status_code == 403


def test_login_limits_repeated_bad_passwords(configured_owner):
    client = TestClient(app)
    payload = {"email": configured_owner["email"], "password": "wrong-test-password"}
    responses = [client.post("/auth/login", headers={"Origin": ORIGIN}, json=payload) for _ in range(6)]

    assert [response.status_code for response in responses] == [401, 401, 401, 401, 401, 429]


def test_owner_direct_creation_requires_active_workspace_owner_grant(configured_owner):
    with AuthSessionLocal() as db:
        actor = load_actor_for_user(db, configured_owner["workspace_id"], configured_owner["user_id"])
        assert actor is not None
        tenant = tenancy.TenantContext(
            workspace_id=configured_owner["workspace_id"],
            user_id=configured_owner["user_id"],
            actor=actor,
            auth_db=db,
            request_id="test-request",
        )
        owner_direct_creation = getattr(tenancy, "owner_direct_creation", lambda _tenant: False)

        assert owner_direct_creation(tenant) is True

        actor.roles[0]["scope_type"] = "TEAM"
        assert owner_direct_creation(tenant) is False


def test_platform_owner_role_claim_alone_does_not_grant_admin_access(monkeypatch):
    monkeypatch.setattr(settings, "platform_owner_user_ids", "")
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": "unconfigured-user",
        "iss": "kiem-thu-nha-cung-cap",
        "aud": "sin-content-test",
        "exp": int(time.time()) + 3600,
        "role": "PLATFORM_OWNER",
    }).encode()).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}".encode()
    secret = "kiem-thu-bang-khoa-gia-lap"
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    token = f"{header}.{payload}.{signature.rstrip(b'=').decode()}"
    from starlette.requests import Request

    request = Request({
        "type": "http",
        "method": "GET",
        "scheme": "https",
        "path": "/v1/platform/config",
        "headers": [],
        "query_string": b"",
        "server": ("studio.example.test", 443),
        "client": ("127.0.0.1", 12345),
    })

    with pytest.raises(HTTPException) as error:
        require_platform_owner(request, authorization=f"Bearer {token}")

    assert error.value.status_code == 403


def test_platform_owner_ids_have_no_embedded_production_defaults(monkeypatch):
    monkeypatch.setattr(settings, "platform_owner_user_ids", "")

    assert settings.platform_owner_ids_set == set()


def test_production_password_login_requires_origin_and_rechecks_revoked_membership(configured_owner, monkeypatch):
    from baha_auth.src.models.entities import Membership

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setenv("BAHA_AUTH_JWT_SECRET", "production-test-only-jwt-key-with-32-bytes")
    client = TestClient(app)
    payload = {"email": configured_owner["email"], "password": PASSWORD}
    assert client.post("/auth/login", json=payload).status_code == 403
    login = client.post("/auth/login", headers={"Origin": ORIGIN}, json=payload)
    assert login.status_code == 200
    client.cookies.set("baha_auth_token", login.json()["access_token"])
    assert client.get("/auth/me").status_code == 200

    with AuthSessionLocal() as db:
        membership = db.query(Membership).filter_by(
            workspace_id=configured_owner["workspace_id"], user_id=configured_owner["user_id"]
        ).one()
        membership.status = "REVOKED"
        db.commit()

    assert client.get("/auth/me").status_code == 403
    assert client.post("/auth/login", headers={"Origin": ORIGIN}, json=payload).status_code == 401


def test_owner_direct_creation_does_not_override_final_approval(configured_owner, monkeypatch):
    from baha_auth.src.policy.evaluator import ResourceContext, evaluate_permission

    monkeypatch.setenv("BAHA_AUTH_APP_ENV", "production")
    with AuthSessionLocal() as db:
        actor = load_actor_for_user(db, configured_owner["workspace_id"], configured_owner["user_id"])
        tenant = tenancy.TenantContext(
            workspace_id=actor.workspace_id, user_id=actor.user_id, actor=actor, auth_db=db, request_id="approval-test"
        )
        assert tenancy.owner_direct_creation(tenant) is True
        decision = evaluate_permission(actor, "media.approve", ResourceContext(
            workspace_id=actor.workspace_id, resource_id="own-media", creator_id=actor.user_id
        ))
        assert decision.allowed is False
        assert decision.reason_code == "SELF_FINAL_APPROVAL_DENIED"


def test_audit_failure_denies_action_without_logging_exception_secrets(configured_owner, monkeypatch, caplog):
    secret_marker = "test-sensitive-audit-parameter"
    auth = tenancy._canonical_auth_modules()

    def fail_audit(*args, **kwargs):
        raise RuntimeError(secret_marker)

    auth["write_audit_event"] = fail_audit
    monkeypatch.setattr(tenancy, "_canonical_auth_modules", lambda: auth)
    with AuthSessionLocal() as db:
        actor = load_actor_for_user(db, configured_owner["workspace_id"], configured_owner["user_id"])
        tenant = tenancy.TenantContext(
            workspace_id=actor.workspace_id, user_id=actor.user_id, actor=actor, auth_db=db, request_id="audit-test"
        )
        with pytest.raises(HTTPException) as error:
            tenancy.authorize_action(tenant, "media.upload")

    assert error.value.status_code == 503
    assert secret_marker not in str(error.value.detail)
    assert secret_marker not in caplog.text


def test_frontend_v1_session_route_authenticates_cookie_without_exposing_login_alias(configured_owner, monkeypatch):
    from src.main import app as production_app

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setenv("BAHA_AUTH_JWT_SECRET", "production-test-only-jwt-key-with-32-bytes")
    client = TestClient(production_app)
    assert client.get("/v1/auth/me").status_code == 401
    login = client.post("/auth/login", headers={"Origin": ORIGIN}, json={
        "email": configured_owner["email"], "password": PASSWORD,
    })
    assert login.status_code == 200
    client.cookies.set("baha_auth_token", login.json()["access_token"])

    response = client.get("/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["user"]["id"] == configured_owner["user_id"]
    assert response.json()["workspace"]["id"] == configured_owner["workspace_id"]
    assert "access_token" not in response.json()
    assert client.get("/auth/me").json()["user"] == response.json()["user"]
    assert client.post("/v1/auth/login", headers={"Origin": ORIGIN}, json={}).status_code == 404

    from baha_auth.src.models.entities import RoleAssignment
    with AuthSessionLocal() as db:
        db.query(RoleAssignment).filter_by(workspace_id=configured_owner["workspace_id"]).delete()
        db.commit()
    assert client.get("/v1/auth/me").status_code == 403
    assert client.get("/auth/me").status_code == 403
