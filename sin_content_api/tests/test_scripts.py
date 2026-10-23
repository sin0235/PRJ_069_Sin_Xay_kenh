# Tests cho Pha P09: Soan thao kich ban & Kiem dinh tuyen bo san pham (T090 -> T093)
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Them thu muc goc 03_ban_lam_viec vao sys.path de import baha_auth
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Thiet lap moi truong test cho Baha Auth RBAC
TEST_DATABASE_URL = "sqlite:///file:sin_content_p09_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = "sqlite:///file:baha_auth_scripts_test?mode=memory&cache=shared&uri=true"
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test" 

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.entities import (
    Workspace, User, Membership, BrandBriefVersion, AllowedFact, IdeaCard, ScriptDraftVersion
)
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.models.entities import (
    GlobalUser, Membership as AuthMembership, Role as AuthRole, RoleAssignment, Workspace as AuthWorkspace
)
from src.modules.scripts.claim_checker import claim_checker
from src.modules.scripts.timing_calculator import timing_calculator
from src.schemas.contracts import ScriptDraftCreate, ScriptDraftEditRequest, ScriptBlock, ClaimCheck

client = TestClient(app)

def tao_bearer(user_id: str) -> str:
    def encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = encode({"alg": "HS256", "typ": "JWT"})
    claims = encode({
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + 300,
    })
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(
        os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{header}.{claims}.{encoded_signature}"

@pytest.fixture
def p09_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)
    db = SessionLocal()
    auth_db = AuthSessionLocal()

    try:
        ws_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        unique_suffix = uuid.uuid4().hex[:6]
        slug = f"p09-{unique_suffix}"

        # 1. Kho Content DB
        ws = Workspace(id=ws_id, name="P09 Script Workspace", slug=slug)
        db.add(ws)
        user = User(id=user_id, email=f"scriptwriter_{unique_suffix}@p09.vn", hashed_password="mock", full_name="Script Lead")
        db.add(user)
        db.flush()

        membership = Membership(workspace_id=ws.id, user_id=user.id, role="creator")
        db.add(membership)

        # 2. Kho Baha Auth DB (cho RBAC canonical)
        auth_ws = AuthWorkspace(id=ws_id, name="P09 Script Workspace", slug=f"auth-{slug}", status="ACTIVE")
        auth_db.add(auth_ws)
        auth_user = GlobalUser(id=user_id, email=user.email, status="ACTIVE")
        auth_db.add(auth_user)
        auth_db.flush()

        auth_mem_id = str(uuid.uuid4())
        auth_mem = AuthMembership(id=auth_mem_id, workspace_id=ws_id, user_id=user_id, status="ACTIVE")
        auth_db.add(auth_mem)
        auth_db.flush()

        role = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()
        if not role:
            role = AuthRole(code="WORKSPACE_OWNER", name="WORKSPACE_OWNER", workspace_id=None, is_template=True, status="ACTIVE")
            auth_db.add(role)
            auth_db.flush()

        ra = RoleAssignment(
            workspace_id=ws_id,
            membership_id=auth_mem_id,
            role_id=role.id,
            scope_type="WORKSPACE",
            scope_id=ws_id,
            status="ACTIVE"
        )
        auth_db.add(ra)

        # Nguoi duyet doc lap (Reviewer) de tuan thu quy tac Four-Eyes / No-Self-Approval
        reviewer_id = str(uuid.uuid4())
        reviewer_user = User(id=reviewer_id, email=f"reviewer_{unique_suffix}@p09.vn", hashed_password="mock", full_name="Script Reviewer")
        db.add(reviewer_user)
        db.flush()

        rev_membership = Membership(workspace_id=ws.id, user_id=reviewer_user.id, role="reviewer")
        db.add(rev_membership)

        auth_rev_user = GlobalUser(id=reviewer_id, email=reviewer_user.email, status="ACTIVE")
        auth_db.add(auth_rev_user)
        auth_db.flush()

        auth_rev_mem_id = str(uuid.uuid4())
        auth_rev_mem = AuthMembership(id=auth_rev_mem_id, workspace_id=ws_id, user_id=reviewer_id, status="ACTIVE")
        auth_db.add(auth_rev_mem)
        auth_db.flush()

        ra_rev = RoleAssignment(
            workspace_id=ws_id,
            membership_id=auth_rev_mem_id,
            role_id=role.id,
            scope_type="WORKSPACE",
            scope_id=ws_id,
            status="ACTIVE"
        )
        auth_db.add(ra_rev)
        auth_db.commit()

        reviewer_token = tao_bearer(reviewer_id)
        reviewer_headers = {
            "Authorization": f"Bearer {reviewer_token}",
            "X-Workspace-Id": ws_id,
            "X-User-Id": reviewer_id
        }

        # 3. Khoi tao Brief va AllowedFacts
        brief = BrandBriefVersion(
            workspace_id=ws.id,
            version=1,
            brand_name="Sin Bento Pro",
            objective="Sản xuất kịch bản video TikTok 30s chứng minh khả năng chống tràn và giữ nhiệt của hộp cơm văn phòng",
            voice_description="Hài hước, chân thực, tình huống công sở đời thường",
            language="vi-VN",
            current_audience="Dân văn phòng mang cơm trưa",
            target_audience="Dân văn phòng, người đi xe máy, sinh viên",
            topics_included_json=json.dumps(["hộp cơm giữ nhiệt", "chống tràn canh", "inox 304"]),
            topics_excluded_json=json.dumps(["cháy nổ", "lừa đảo", "hàng giả"]),
            production_limits_json=json.dumps(["thời lượng 30s"]),
            status="APPROVED"
        )
        db.add(brief)
        db.flush()

        fact1 = AllowedFact(
            brief_version_id=brief.id,
            claim_text="Giữ nóng 6 tiếng liên tục",
            source_citation="Phiếu thử nghiệm nhiệt độ Quatest 3 số 2026/QT3-882"
        )
        fact2 = AllowedFact(
            brief_version_id=brief.id,
            claim_text="Chống tràn canh tuyệt đối với nắp gioăng silicon",
            source_citation="Thử nghiệm rung lắc mô phỏng xe máy 50km/h"
        )
        fact3 = AllowedFact(
            brief_version_id=brief.id,
            claim_text="Chất liệu inox 304 tiêu chuẩn an toàn thực phẩm",
            source_citation="Chứng nhận kiểm định an toàn vệ sinh thực phẩm TCVN"
        )
        db.add_all([fact1, fact2, fact3])
        db.flush()

        idea = IdeaCard(
            workspace_id=ws.id,
            brief_version_id=brief.id,
            title="Thử thách đi xe máy qua đường xóc với hộp canh nóng",
            target_need="Khắc phục sự cố trào canh và giữ nhiệt thức ăn trưa",
            hook="Bỏ hộp cơm đựng đầy canh vào balo lắc hết cỡ 15 phút xem có giọt nào rỉ ra không",
            content_angle="Tình huống thử thách thực tế (Stress Test Challenge)",
            confidence_tier="EVIDENCE_BACKED",
            status="APPROVED",
            evidence_excerpt_ids_json=json.dumps(["citation_1", "citation_2"])
        )
        db.add(idea)
        db.flush()
        brief_id_val = brief.id
        idea_id_val = idea.id
        db.commit()
        db.close()
        auth_db.close()

        token = tao_bearer(user_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-Id": ws_id,
            "X-User-Id": user_id
        }

        yield {
            "workspace_id": ws_id,
            "user_id": user_id,
            "reviewer_id": reviewer_id,
            "brief_id": brief_id_val,
            "idea_id": idea_id_val,
            "headers": headers,
            "reviewer_headers": reviewer_headers,
        }
    finally:
        pass

# T090: Kich ban chua tuyen bo dinh luong khong co trong AllowedFact -> BLOCKING & Cam duyet (HTTP 422)
def test_t090_unverified_claim_blocks_approval(p09_fixture):
    headers = p09_fixture["headers"]
    idea_id = p09_fixture["idea_id"]

    # Kich ban chua tuyen bo vi pham: "giu nong 24 tieng" (trong khi AllowedFact chi co 6 tieng)
    # va "cam ket 100% khong bao gio trao"
    payload = {
        "idea_id": idea_id,
        "title": "Kịch bản thử thách đường xóc - Bản nháp chứa claim quá đà",
        "target_duration_seconds": 30,
        "hook_variants": [
            "Biến thể 1: Đố bạn để hộp canh này trong balo đi đường xóc mà không trào?",
            "Biến thể 2: Thử thách 24 tiếng giữ nóng hộp cơm văn phòng"
        ],
        "blocks": [
            {
                "block_type": "HOOK",
                "narration": "Thử thách 24 tiếng giữ nóng hộp cơm văn phòng xem có ăn được không nha!",
                "visual_cue": "Quay cận cảnh đồng hồ bấm giờ và hộp cơm",
                "duration_seconds": 5
            },
            {
                "block_type": "SETUP",
                "narration": "Bình thường đi xe máy dằn xóc là canh trào ra tài liệu ướt hết.",
                "visual_cue": "Cảnh balo bị dính nước canh bốc mùi",
                "duration_seconds": 7
            },
            {
                "block_type": "PROOF",
                "narration": "Nhưng với Sin Bento Pro thì cam kết 100% không bao giờ trào dù chạy 50km đường ổ gà.",
                "visual_cue": "Cầm hộp cơm lắc mạnh qua lại trên xe máy",
                "duration_seconds": 10
            },
            {
                "block_type": "CTA",
                "narration": "Bấm vào giỏ hàng góc trái để nhận ưu đãi hôm nay nhé!",
                "visual_cue": "Mũi tên chỉ vào giỏ hàng TikTok Shop",
                "duration_seconds": 8
            }
        ]
    }

    # 1. Tao kich ban qua API
    resp = client.post("/v1/scripts", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    script_id = data["id"]
    assert data["status"] == "NEEDS_FACT_CHECK"
    assert data["blocking_claims_count"] > 0

    # Kiem tra chi tiet claims
    blocking_claims = [c for c in data["claims"] if c["verification_status"] == "BLOCKING"]
    assert len(blocking_claims) >= 1
    claim_texts = " ".join([c["claim_text"] for c in blocking_claims])
    assert ("24 tiếng" in claim_texts or "100%" in claim_texts)

    # 2. Kiem tra no-self-approval: Tac gia tu duyet phai bi chan HTTP 403 Forbidden
    self_appr = client.post(f"/v1/scripts/{script_id}/approve", headers=headers)
    assert self_appr.status_code == 403, "Self approval phai bi chan"

    # Reviewer doc lap phe duyet -> Claim-checker chan vi co BLOCKING claims (HTTP 422)
    approve_resp = client.post(f"/v1/scripts/{script_id}/approve", headers=p09_fixture["reviewer_headers"])
    assert approve_resp.status_code == 422, approve_resp.text
    err_body = approve_resp.json()
    assert err_body["error_code"] == "CANNOT_APPROVE_UNVERIFIED_CLAIMS"
    assert "chưa được kiểm định" in err_body["message_safe"]

    # Kiem tra lai trang thai kich ban van khong phai APPROVED
    get_resp = client.get(f"/v1/scripts/{script_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "NEEDS_FACT_CHECK"

# T091: Kich ban chua tuyen bo khop AllowedFact -> VERIFIED & Phe duyet thanh cong (APPROVED)
def test_t091_verified_claims_permit_approval(p09_fixture):
    headers = p09_fixture["headers"]
    idea_id = p09_fixture["idea_id"]
    user_id = p09_fixture["user_id"]

    # Kich ban chi chua dung tuyen bo hop le: "giu nong 6 tieng", "nap gioang silicon chong tran canh", "inox 304"
    payload = {
        "idea_id": idea_id,
        "title": "Kịch bản chuẩn kỹ thuật - Đã kiểm chứng AllowedFact",
        "target_duration_seconds": 30,
        "hook_variants": [
            "Biến thể 1: Đố bạn để hộp canh này trong balo đi đường xóc mà không trào?",
            "Biến thể 2: Hộp cơm giữ nóng 6 tiếng từ sáng đến trưa cho dân văn phòng"
        ],
        "blocks": [
            {
                "block_type": "HOOK",
                "narration": "Hộp cơm giữ nóng 6 tiếng từ sáng đến trưa, trưa mở ra khói nghi ngút!",
                "visual_cue": "Mở nắp hộp cơm thấy làn khói bốc lên rõ rệt",
                "duration_seconds": 6
            },
            {
                "block_type": "SETUP",
                "narration": "Đi làm bằng xe máy xóc ổ gà sợ nhất canh trào ra ướt hỏng tài liệu máy tính.",
                "visual_cue": "Mô phỏng cảnh đi xe máy qua gờ giảm tốc",
                "duration_seconds": 7
            },
            {
                "block_type": "VALUE",
                "narration": "Em Sin Bento Pro này có nắp gioăng silicon chống tràn canh tuyệt đối, ngăn bên trong làm bằng chất liệu inox 304 an toàn.",
                "visual_cue": "Cầm hộp dốc ngược lắc mạnh không rỉ một giọt, zoom cận lòng khay inox 304",
                "duration_seconds": 11
            },
            {
                "block_type": "CTA",
                "narration": "Trưa nay ăn cơm nóng canh ngon tại văn phòng ngay với giỏ hàng bên dưới nhé!",
                "visual_cue": "Ăn miếng cơm nóng ngon miệng và trỏ tay vào góc màn hình",
                "duration_seconds": 6
            }
        ]
    }

    # 1. Tao kich ban
    resp = client.post("/v1/scripts", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    script_id = data["id"]
    assert data["blocking_claims_count"] == 0
    assert data["status"] == "READY_FOR_REVIEW"

    # 2. Kiem tra no-self-approval: Tac gia tu duyet phai bi chan HTTP 403
    self_appr = client.post(f"/v1/scripts/{script_id}/approve", headers=headers)
    assert self_appr.status_code == 403

    # Reviewer doc lap phe duyet kich ban hop le -> Thanh cong
    approve_resp = client.post(f"/v1/scripts/{script_id}/approve", headers=p09_fixture["reviewer_headers"])
    assert approve_resp.status_code == 200, approve_resp.text
    approved_data = approve_resp.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["approved_by_user_id"] == p09_fixture["reviewer_id"]
    assert approved_data["approved_at"] is not None

# T092: Chinh sua kich ban da APPROVED phai tao version moi bat bien, version cu thanh SUPERSEDED
def test_t092_immutable_versioning_on_edit(p09_fixture):
    headers = p09_fixture["headers"]
    idea_id = p09_fixture["idea_id"]

    # 1. Tao va phe duyet version 1
    create_payload = {
        "idea_id": idea_id,
        "title": "Kịch bản hộp cơm Sin Bento - Version 1",
        "target_duration_seconds": 30,
        "hook_variants": [
            "Hook A: Đi xe máy không lo đổ canh",
            "Hook B: Hộp cơm giữ nóng 6 tiếng"
        ],
        "blocks": [
            {
                "block_type": "HOOK",
                "narration": "Hộp cơm giữ nóng 6 tiếng từ sáng đến trưa",
                "visual_cue": "Mở nắp bốc khói",
                "duration_seconds": 8
            },
            {
                "block_type": "VALUE",
                "narration": "Chất liệu inox 304 nắp gioăng silicon chống tràn canh tuyệt đối",
                "visual_cue": "Dốc ngược hộp",
                "duration_seconds": 14
            },
            {
                "block_type": "CTA",
                "narration": "Mua ngay tại giỏ hàng",
                "visual_cue": "Trỏ giỏ hàng",
                "duration_seconds": 8
            }
        ]
    }
    create_resp = client.post("/v1/scripts", json=create_payload, headers=headers)
    assert create_resp.status_code == 200, create_resp.text
    v1_id = create_resp.json()["id"]

    # Reviewer Approve v1
    appr_resp = client.post(f"/v1/scripts/{v1_id}/approve", headers=p09_fixture["reviewer_headers"])
    assert appr_resp.status_code == 200, appr_resp.text
    assert appr_resp.json()["status"] == "APPROVED"
    assert appr_resp.json()["version"] == 1

    # 2. Thuc hien edit kich ban da APPROVED
    edit_payload = {
        "title": "Kịch bản hộp cơm Sin Bento - Version 2 Cập nhật CTA",
        "blocks": [
            {
                "block_type": "HOOK",
                "narration": "Hộp cơm giữ nóng 6 tiếng từ sáng đến trưa",
                "visual_cue": "Mở nắp bốc khói",
                "duration_seconds": 8
            },
            {
                "block_type": "VALUE",
                "narration": "Chất liệu inox 304 nắp gioăng silicon chống tràn canh tuyệt đối",
                "visual_cue": "Dốc ngược hộp",
                "duration_seconds": 14
            },
            {
                "block_type": "CTA",
                "narration": "Hôm nay đang có voucher giảm giá dùng thử, nhấn ngay giỏ hàng nhé!",
                "visual_cue": "Trỏ giỏ hàng TikTok",
                "duration_seconds": 8
            }
        ]
    }

    edit_resp = client.post(f"/v1/scripts/{v1_id}/edit", json=edit_payload, headers=headers)
    assert edit_resp.status_code == 200, edit_resp.text
    v2_data = edit_resp.json()

    # Kiem tra phien ban moi sinh ra
    assert v2_data["id"] != v1_id
    assert v2_data["version"] == 2
    assert v2_data["status"] == "DRAFT"
    assert "Version 2 Cập nhật CTA" in v2_data["title"]

    # 3. Kiem tra phien ban cu v1 trong DB: Phai thanh SUPERSEDED, khong bi xoa/ghi de
    old_v1_resp = client.get(f"/v1/scripts/{v1_id}", headers=headers)
    assert old_v1_resp.status_code == 200
    old_v1_data = old_v1_resp.json()
    assert old_v1_data["version"] == 1
    assert old_v1_data["status"] == "SUPERSEDED"

    # P09-04: Sua ban SUPERSEDED tiep tuc tao version moi (v3), khong sua de hay trung version
    edit_resp2 = client.post(f"/v1/scripts/{v1_id}/edit", json=edit_payload, headers=headers)
    assert edit_resp2.status_code == 200
    v3_data = edit_resp2.json()
    assert v3_data["version"] == 3

# T093: Kiem soat thoi luong phan canh (Dung sai +/- 3 giay, khong chong cheo, hook >= 2)
def test_t093_timing_tolerance_and_hook_variants():
    # 1. Kiem tra dung sai hop le: Target 30s, actual 32s (lech +2s <= 3s)
    blocks_ok = [
        {"block_type": "HOOK", "narration": "H1", "duration_seconds": 5},
        {"block_type": "SETUP", "narration": "P1", "duration_seconds": 10},
        {"block_type": "VALUE", "narration": "S1", "duration_seconds": 12},
        {"block_type": "CTA", "narration": "C1", "duration_seconds": 5}
    ]
    hooks_ok = ["Hook variant 1", "Hook variant 2"]

    res_ok = timing_calculator.validate_and_calculate_timing(
        target_duration_seconds=30,
        blocks=blocks_ok,
        hook_variants=hooks_ok
    )
    assert res_ok["actual_duration_seconds"] == 32
    assert res_ok["duration_diff"] == 2
    assert res_ok["duration_tolerance_passed"] is True
    assert res_ok["hook_variants_valid"] is True
    assert res_ok["has_overlap"] is False

    # Kiem tra tinh lien tuc cua timeline cac block
    timed = res_ok["timed_blocks"]
    assert timed[0]["start_seconds"] == 0 and timed[0]["end_seconds"] == 5
    assert timed[1]["start_seconds"] == 5 and timed[1]["end_seconds"] == 15
    assert timed[2]["start_seconds"] == 15 and timed[2]["end_seconds"] == 27
    assert timed[3]["start_seconds"] == 27 and timed[3]["end_seconds"] == 32

    # 2. Kiem tra vuot qua dung sai: Target 30s, actual 36s (lech 6s > 3s)
    blocks_fail = [
        {"block_type": "HOOK", "narration": "H1", "duration_seconds": 10},
        {"block_type": "SETUP", "narration": "P1", "duration_seconds": 15},
        {"block_type": "CTA", "narration": "C1", "duration_seconds": 11}
    ]
    res_fail = timing_calculator.validate_and_calculate_timing(
        target_duration_seconds=30,
        blocks=blocks_fail,
        hook_variants=["Hook duy nhất"] # Chi co 1 hook -> khong dat chuan >= 2
    )
    assert res_fail["actual_duration_seconds"] == 36
    assert res_fail["duration_tolerance_passed"] is False
    assert res_fail["hook_variants_valid"] is False
