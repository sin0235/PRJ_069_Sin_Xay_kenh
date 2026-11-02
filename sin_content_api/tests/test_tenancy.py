# Test T011: Kiem tra co lap da khach thue (Multi-tenancy Isolation)
import pytest
import uuid
import base64
import json
import time
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import Workspace, User, Membership, BrandBriefVersion
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from tests.conftest import tao_bearer_token, setup_test_auth_user

client = TestClient(app)


class _AccessJwksResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


def _access_token(private_key, *, issuer, audience, email):
    b64url = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    numbers = private_key.public_key().public_numbers()
    integer = lambda value: value.to_bytes((value.bit_length() + 7) // 8, "big")
    kid = uuid.uuid4().hex
    header = b64url(json.dumps({"alg": "RS256", "kid": kid}, separators=(",", ":")).encode())
    claims = b64url(json.dumps({
        "sub": "cloudflare-subject",
        "iss": issuer,
        "aud": audience,
        "exp": int(time.time()) + 300,
        "email": email,
    }, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = b64url(private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256()))
    jwks = {"keys": [{"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
                      "n": b64url(integer(numbers.n)), "e": b64url(integer(numbers.e))}]}
    return f"{header}.{claims}.{signature}", jwks

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    db = SessionLocal()
    auth_db = AuthSessionLocal()
    
    # Tao 2 Workspace va 2 User rieng biet
    ws1 = Workspace(id=str(uuid.uuid4()), name="Workspace 1 - Sin Fashion", slug=f"ws1-{uuid.uuid4().hex[:6]}")
    ws2 = Workspace(id=str(uuid.uuid4()), name="Workspace 2 - Sin Tech", slug=f"ws2-{uuid.uuid4().hex[:6]}")
    
    user_a = User(id=str(uuid.uuid4()), email=f"user_a_{uuid.uuid4().hex[:6]}@baha.vn", full_name="User A", hashed_password="mock")
    user_b = User(id=str(uuid.uuid4()), email=f"user_b_{uuid.uuid4().hex[:6]}@baha.vn", full_name="User B", hashed_password="mock")
    
    db.add_all([ws1, ws2, user_a, user_b])
    db.commit()
    
    # User A thuoc Workspace 1 voi role editor
    m1 = Membership(workspace_id=ws1.id, user_id=user_a.id, role="editor")
    # User B thuoc Workspace 2 voi role editor
    m2 = Membership(workspace_id=ws2.id, user_id=user_b.id, role="editor")
    
    # Brief bi mat thuoc Workspace 1 (co day du cac truong P02)
    brief1 = BrandBriefVersion(
        id=str(uuid.uuid4()),
        workspace_id=ws1.id,
        version=1,
        brand_name="Bi Mat Thuong Hieu Sin Fashion",
        objective="Kenh thoi trang cao cap",
        voice_description="Giong dieu doc quyen cua kenh thoi trang",
        current_audience="Nu 18-24 yeu thich phong cach toi gian",
        target_audience="Nu 18-24 yeu thich phong cach toi gian",
        topics_included_json='["thoi trang toi gian"]',
        topics_excluded_json='["hang gia"]',
        status="APPROVED"
    )
    
    db.add_all([m1, m2, brief1])
    db.commit()

    # Dong bo user vao kho Baha Auth RBAC
    setup_test_auth_user(auth_db, ws1.id, user_a.id, user_a.email, "WORKSPACE_OWNER")
    setup_test_auth_user(auth_db, ws2.id, user_b.id, user_b.email, "WORKSPACE_OWNER")
    
    token_a = tao_bearer_token(user_a.id)
    token_b = tao_bearer_token(user_b.id)
    
    ctx = {
        "ws1_id": ws1.id,
        "ws2_id": ws2.id,
        "user_a_id": user_a.id,
        "user_b_id": user_b.id,
        "user_a_email": user_a.email,
        "user_b_email": user_b.email,
        "token_a": token_a,
        "token_b": token_b,
        "brief1_id": brief1.id,
        "brief1_name": brief1.brand_name
    }
    db.close()
    auth_db.close()
    yield ctx

def test_user_a_can_access_own_workspace_brief(setup_db):
    """User A truy cap hop le vao brief cua Workspace 1"""
    headers = {
        "Authorization": f"Bearer {setup_db['token_a']}",
        "X-Workspace-Id": setup_db["ws1_id"],
        "X-User-Id": setup_db["user_a_id"]
    }
    response = client.get(f"/v1/briefs/{setup_db['brief1_id']}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["brand_name"] == setup_db["brief1_name"]
    assert data["workspace_id"] == setup_db["ws1_id"]

def test_cross_tenant_access_denied_user_b_cannot_access_workspace_1(setup_db):
    """T011: User B (thuoc Workspace 2) gui header Workspace 1 phai bi 403 Forbidden"""
    headers = {
        "Authorization": f"Bearer {setup_db['token_b']}",
        "X-Workspace-Id": setup_db["ws1_id"], # Co tinh gui ws1
        "X-User-Id": setup_db["user_b_id"]    # Nhung user la B
    }
    response = client.get(f"/v1/briefs/{setup_db['brief1_id']}", headers=headers)
    assert response.status_code == 403
    # Dam bao khong ro ri ten hoac du lieu brief trong response
    assert setup_db["brief1_name"] not in response.text


def test_access_session_maps_verified_email_to_db_user_and_workspace(monkeypatch, setup_db):
    issuer = f"https://test-{uuid.uuid4().hex}.cloudflareaccess.com"
    audience = "test-audience-prj069"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token, jwks = _access_token(
        private_key, issuer=issuer, audience=audience, email=setup_db["user_a_email"],
    )
    from baha_auth.src import xac_minh_danh_tinh
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ISSUER", issuer)
    monkeypatch.setenv("CLOUDFLARE_ACCESS_AUDIENCE", audience)
    monkeypatch.delenv("BAHA_AUTH_JWT_SECRET", raising=False)
    monkeypatch.delenv("BAHA_AUTH_JWT_ISSUER", raising=False)
    monkeypatch.delenv("BAHA_AUTH_JWT_AUDIENCE", raising=False)
    monkeypatch.setattr(xac_minh_danh_tinh.httpx, "get", lambda *_args, **_kwargs: _AccessJwksResponse(jwks))

    response = client.get(
        "/v1/auth/me",
        headers={"Cf-Access-Jwt-Assertion": token, "X-User-Id": "attacker"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["id"] == setup_db["user_a_id"]
    assert response.json()["workspace"]["id"] == setup_db["ws1_id"]


def test_access_session_rejects_bearer_and_client_email_without_access_assertion(setup_db):
    response = client.get(
        "/v1/auth/me",
        headers={
            "Authorization": f"Bearer {setup_db['token_a']}",
            "X-User-Id": setup_db["user_a_id"],
            "X-User-Email": "user_a@baha.vn",
        },
    )

    assert response.status_code == 401


def test_access_assertion_resolves_tenant_by_email_and_ignores_client_user_id(monkeypatch, setup_db):
    issuer = f"https://tenant-{uuid.uuid4().hex}.cloudflareaccess.com"
    audience = "test-audience-prj069"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token, jwks = _access_token(
        private_key, issuer=issuer, audience=audience, email=setup_db["user_a_email"],
    )
    from baha_auth.src import xac_minh_danh_tinh
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ISSUER", issuer)
    monkeypatch.setenv("CLOUDFLARE_ACCESS_AUDIENCE", audience)
    monkeypatch.setattr(xac_minh_danh_tinh.httpx, "get", lambda *_args, **_kwargs: _AccessJwksResponse(jwks))

    response = client.get(
        f"/v1/briefs/{setup_db['brief1_id']}",
        headers={
            "Cf-Access-Jwt-Assertion": token,
            "X-Workspace-Id": setup_db["ws1_id"],
            "X-User-Id": "attacker",
        },
    )

    assert response.status_code == 200
    assert response.json()["workspace_id"] == setup_db["ws1_id"]


def test_access_assertion_cannot_select_another_users_workspace(monkeypatch, setup_db):
    issuer = f"https://tenant-{uuid.uuid4().hex}.cloudflareaccess.com"
    audience = "test-audience-prj069"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token, jwks = _access_token(
        private_key, issuer=issuer, audience=audience, email=setup_db["user_a_email"],
    )
    from baha_auth.src import xac_minh_danh_tinh
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ISSUER", issuer)
    monkeypatch.setenv("CLOUDFLARE_ACCESS_AUDIENCE", audience)
    monkeypatch.setattr(xac_minh_danh_tinh.httpx, "get", lambda *_args, **_kwargs: _AccessJwksResponse(jwks))

    response = client.get(
        f"/v1/briefs/{setup_db['brief1_id']}",
        headers={
            "Cf-Access-Jwt-Assertion": token,
            "X-Workspace-Id": setup_db["ws2_id"],
        },
    )

    assert response.status_code == 403


def test_production_access_is_pinned_to_configured_sin_workspace(monkeypatch, setup_db):
    issuer = f"https://tenant-{uuid.uuid4().hex}.cloudflareaccess.com"
    audience = "test-audience-prj069"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token, jwks = _access_token(
        private_key, issuer=issuer, audience=audience, email=setup_db["user_a_email"],
    )
    from baha_auth.src import xac_minh_danh_tinh
    from src.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setenv("SIN_WORKSPACE_ID", setup_db["ws1_id"])
    monkeypatch.setenv("CLOUDFLARE_ACCESS_ISSUER", issuer)
    monkeypatch.setenv("CLOUDFLARE_ACCESS_AUDIENCE", audience)
    monkeypatch.setattr(xac_minh_danh_tinh.httpx, "get", lambda *_args, **_kwargs: _AccessJwksResponse(jwks))

    response = client.get(
        f"/v1/briefs/{setup_db['brief1_id']}",
        headers={
            "Cf-Access-Jwt-Assertion": token,
            "X-Workspace-Id": setup_db["ws2_id"],
        },
    )

    assert response.status_code == 403

def test_user_b_in_own_workspace_cannot_read_brief1(setup_db):
    """T011: User B dung header Workspace 2 nhung truy cap ID brief cua Workspace 1 phai bi chan"""
    headers = {
        "Authorization": f"Bearer {setup_db['token_b']}",
        "X-Workspace-Id": setup_db["ws2_id"],
        "X-User-Id": setup_db["user_b_id"]
    }
    response = client.get(f"/v1/briefs/{setup_db['brief1_id']}", headers=headers)
    # Phai tra ve 403 Forbidden hoac 404 Not Found
    assert response.status_code in [403, 404]
    # Khong duoc de lo bat ky noi dung nao cua brief 1
    assert setup_db["brief1_name"] not in response.text
