# Test T011: Kiem tra co lap da khach thue (Multi-tenancy Isolation)
import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import Workspace, User, Membership, BrandBriefVersion
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from tests.conftest import tao_bearer_token, setup_test_auth_user

client = TestClient(app)

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
