# Test Suite cho Pha P02: T020, T021, T022 (Brand Brief & Audience Model)
import pytest
import uuid
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import Workspace, User, Membership, BrandBriefVersion, AuditEvent
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from tests.conftest import tao_bearer_token, setup_test_auth_user

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_p02_env():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    db = SessionLocal()
    auth_db = AuthSessionLocal()
    
    # Tao workspace va cac user voi cac vai tro khac nhau
    ws = Workspace(id=str(uuid.uuid4()), name="Sin Beauty & Wellness", slug=f"beauty-{uuid.uuid4().hex[:6]}")
    user_editor = User(id=str(uuid.uuid4()), email=f"editor_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Editor User", hashed_password="mock")
    user_reviewer = User(id=str(uuid.uuid4()), email=f"reviewer_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Reviewer User", hashed_password="mock")
    user_viewer = User(id=str(uuid.uuid4()), email=f"viewer_{uuid.uuid4().hex[:6]}@baha.vn", full_name="Viewer User", hashed_password="mock")
    
    db.add_all([ws, user_editor, user_reviewer, user_viewer])
    db.commit()
    
    # Gan memberships trong content db
    m_editor = Membership(workspace_id=ws.id, user_id=user_editor.id, role="editor")
    m_reviewer = Membership(workspace_id=ws.id, user_id=user_reviewer.id, role="reviewer")
    m_viewer = Membership(workspace_id=ws.id, user_id=user_viewer.id, role="viewer")
    
    db.add_all([m_editor, m_reviewer, m_viewer])
    db.commit()

    # Dong bo user vao kho Baha Auth RBAC:
    # editor co quyen brief.edit, reviewer co quyen brief.approve, viewer role GUEST khong co quyen duyet
    setup_test_auth_user(auth_db, ws.id, user_editor.id, user_editor.email, "WORKSPACE_OWNER")
    setup_test_auth_user(auth_db, ws.id, user_reviewer.id, user_reviewer.email, "WORKSPACE_OWNER")
    setup_test_auth_user(auth_db, ws.id, user_viewer.id, user_viewer.email, "GUEST")

    token_editor = tao_bearer_token(user_editor.id)
    token_reviewer = tao_bearer_token(user_reviewer.id)
    token_viewer = tao_bearer_token(user_viewer.id)
    
    ctx = {
        "ws_id": ws.id,
        "editor_id": user_editor.id,
        "reviewer_id": user_reviewer.id,
        "viewer_id": user_viewer.id,
        "editor_token": token_editor,
        "reviewer_token": token_reviewer,
        "viewer_token": token_viewer,
        "editor_headers": {
            "Authorization": f"Bearer {token_editor}",
            "X-Workspace-Id": ws.id,
            "X-User-Id": user_editor.id
        },
        "reviewer_headers": {
            "Authorization": f"Bearer {token_reviewer}",
            "X-Workspace-Id": ws.id,
            "X-User-Id": user_reviewer.id
        },
        "viewer_headers": {
            "Authorization": f"Bearer {token_viewer}",
            "X-Workspace-Id": ws.id,
            "X-User-Id": user_viewer.id
        }
    }
    db.close()
    auth_db.close()
    yield ctx

def test_t020_incomplete_or_wrong_brand_brief_rejected(setup_p02_env):
    """T020: Brief thieu truong bat buoc hoac sai quy dinh phai bi tra ve 422 kem field loi"""
    headers = setup_p02_env["editor_headers"]
    
    # 1. Thieu brand_name
    bad_payload_1 = {
        "objective": "Tang nhan dien kenh TikTok",
        "voice_description": "Chuyen nghiep va gan gui",
        "current_audience": "Nguoi xem 18-24",
        "target_audience": "Khach hang mua my pham 25-35",
        "topics_included": ["cham soc da"],
        "topics_excluded": ["kem tron"]
    }
    res1 = client.post("/v1/briefs", json=bad_payload_1, headers=headers)
    assert res1.status_code == 422
    assert "brand_name" in res1.text
    
    # 2. voice_description qua ngan (< 10 ky tu)
    bad_payload_2 = {
        "brand_name": "Sin Beauty",
        "objective": "Tang nhan dien kenh TikTok",
        "voice_description": "Ngan", # Vi pham min_length=10
        "current_audience": "Nguoi xem 18-24",
        "target_audience": "Khach hang mua my pham 25-35",
        "topics_included": ["cham soc da"],
        "topics_excluded": ["kem tron"]
    }
    res2 = client.post("/v1/briefs", json=bad_payload_2, headers=headers)
    assert res2.status_code == 422
    assert "voice_description" in res2.text
    
    # 3. topics_excluded bi rong (Vi pham brand safety)
    bad_payload_3 = {
        "brand_name": "Sin Beauty",
        "objective": "Tang nhan dien kenh TikTok",
        "voice_description": "Chuyen nghiep va gan gui",
        "current_audience": "Nguoi xem 18-24",
        "target_audience": "Khach hang mua my pham 25-35",
        "topics_included": ["cham soc da"],
        "topics_excluded": [] # Vi pham min_length=1
    }
    res3 = client.post("/v1/briefs", json=bad_payload_3, headers=headers)
    assert res3.status_code == 422
    assert "topics_excluded" in res3.text

def test_t021_approved_brief_edited_creates_new_immutable_version(setup_p02_env):
    """
    T021: Chinh sua brief da APPROVED phai tao phien ban bat bien moi (v2),
    phien ban cu (v1) van duoc bao toan APPROVED, phien ban moi can duyet lai (DRAFT).
    """
    editor_headers = setup_p02_env["editor_headers"]
    reviewer_headers = setup_p02_env["reviewer_headers"]
    
    # 1. Editor tao Brief ban dau
    valid_payload = {
        "brand_name": "Sin Skincare Official",
        "objective": "Xay dung kenh chuyen gia da lieu",
        "voice_description": "Chuyen gia khoa hoc, khach quan va dang tin cay",
        "current_audience": "Nu van phong 22-30 quan tam mun",
        "target_audience": "Phu nu 25-40 co nhu cau chong lao hoa",
        "topics_included": ["khoa hoc lan da", "routine toi gian"],
        "topics_excluded": ["kem tron gia re", "quang cao phong dai"],
        "segments": [
            {
                "label": "Dan van phong bi mun do stress",
                "contexts": ["ngoi may lanh nhieu", "thuc khuya"],
                "needs": ["phuc hoi hang rao bao ve da"],
                "disallowed_inferences": ["thu nhap ca nhan"]
            }
        ],
        "allowed_facts": [
            {
                "claim_text": "Chiet xuat Rau ma tinh khiet 95% giup diu da tuc thi",
                "fact_type": "CLINICAL_TRIAL",
                "source_citation": "Bao cao thu nghiem lam sang so 08/2026-SIN"
            }
        ]
    }
    res_create = client.post("/v1/briefs", json=valid_payload, headers=editor_headers)
    assert res_create.status_code == 201
    brief_v1 = res_create.json()
    assert brief_v1["version"] == 1
    assert brief_v1["status"] == "DRAFT"
    brief_v1_id = brief_v1["id"]
    
    # 2. Reviewer phe duyet Brief v1
    res_approve = client.post(
        f"/v1/briefs/{brief_v1_id}/review",
        json={"action": "APPROVE", "notes": "Thong qua brief chien luoc v1"},
        headers=reviewer_headers
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "APPROVED"
    assert res_approve.json()["version"] == 1
    
    # 3. Editor thuc hien chinh sua Brief v1 da APPROVED
    update_payload = {
        "target_audience": "Mo rong sang ca nam gioi 20-35 quan tam cham soc ban than",
        "topics_included": ["khoa hoc lan da", "routine toi gian", "skincare cho nam"]
    }
    res_edit = client.put(f"/v1/briefs/{brief_v1_id}", json=update_payload, headers=editor_headers)
    assert res_edit.status_code == 200
    brief_v2 = res_edit.json()
    
    # 4. Kiem tra phien ban moi: ID moi, version=2, status=DRAFT (can duyet lai)
    assert brief_v2["id"] != brief_v1_id
    assert brief_v2["version"] == 2
    assert brief_v2["status"] == "DRAFT"
    assert "skincare cho nam" in brief_v2["topics_included"]
    assert len(brief_v2["segments"]) == 1 # Segments duoc ke thua sang v2
    assert len(brief_v2["allowed_facts"]) == 1 # Facts duoc ke thua sang v2
    
    # 5. Kiem tra phien ban cu (v1): Van ton tai nguyen ven voi APPROVED va noi dung cu
    res_v1_check = client.get(f"/v1/briefs/{brief_v1_id}", headers=editor_headers)
    assert res_v1_check.status_code == 200
    v1_data = res_v1_check.json()
    assert v1_data["version"] == 1
    assert v1_data["status"] == "APPROVED"
    assert "skincare cho nam" not in v1_data["topics_included"]

def test_t022_viewer_tries_approve_brief_denied(setup_p02_env):
    """T022: Nguoi dung role viewer co tinh phe duyet brief phai bi 403 Forbidden va ghi audit"""
    editor_headers = setup_p02_env["editor_headers"]
    viewer_headers = setup_p02_env["viewer_headers"]
    
    # 1. Tao brief nhap
    payload = {
        "brand_name": "Sin Test Brief",
        "objective": "Thu nghiem phan quyen viewer",
        "voice_description": "Giong dieu thu nghiem chuan",
        "current_audience": "Khan gia hien tai",
        "target_audience": "Khan gia muc tieu",
        "topics_included": ["test"],
        "topics_excluded": ["spam"]
    }
    res_create = client.post("/v1/briefs", json=payload, headers=editor_headers)
    assert res_create.status_code == 201
    brief_id = res_create.json()["id"]
    
    # 2. Viewer co tinh gui request APPROVE
    res_viewer_approve = client.post(
        f"/v1/briefs/{brief_id}/review",
        json={"action": "APPROVE", "notes": "Viewer co tinh vuot quyen"},
        headers=viewer_headers
    )
    # Phai bi tu choi voi HTTP 403 Forbidden
    assert res_viewer_approve.status_code == 403
    assert ("INSUFFICIENT_PERMISSIONS" in res_viewer_approve.text or "Không đủ quyền" in res_viewer_approve.text or "403" in str(res_viewer_approve.status_code))
    
    # 3. Kiem tra brief van o trang thai DRAFT (khong bi duyet trai phep)
    res_check = client.get(f"/v1/briefs/{brief_id}", headers=editor_headers)
    assert res_check.status_code == 200
    assert res_check.json()["status"] == "DRAFT"
