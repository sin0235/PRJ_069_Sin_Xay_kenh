"""
Bo kiem thu Pha P13: Production Canary & Rollback
Bao gom cac ca kiem thu nghiem ngat:
- T130: tenant canary approved research run ->
        records real source IDs, lineage, quota cost and review output; rollback ready.
- T131: revoked provider access in canary ->
        source marked unavailable, no alternate bypass, UI informs operator safely.
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Cau hinh moi truong cho SQLite in-memory de dam bao doc lap hoan toan
TEST_DATABASE_URL = "sqlite:///file:sin_content_p13_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_p13_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap-p13"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap-p13"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test-p13"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    Workspace, User, BrandBriefVersion, SourceRecord,
    CanaryDeployment, CanaryResearchRun, ProviderAccessGrant,
    WorkspaceBudget
)
from baha_auth.src.database import (
    Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine,
)
from baha_auth.src.models.entities import (
    GlobalUser,
    Membership as AuthMembership,
    Role as AuthRole,
    RoleAssignment,
    Workspace as AuthWorkspace,
)
from src.modules.staging_reliability.budget_guard import budget_guard
from scripts.audit_live_sources import audit_live_sources
from scripts.rollback_canary import execute_rollback

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
        "exp": int(time.time()) + 3600,
    })
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(
        os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{header}.{claims}.{encoded_signature}"

def lay_role(db, code: str):
    role = db.query(AuthRole).filter(AuthRole.code == code).first()
    if role is None:
        role = AuthRole(code=code, name=code, workspace_id=None, is_template=True, status="ACTIVE")
        db.add(role)
        db.flush()
    return role

@pytest.fixture
def p13_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    workspace_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    slug = f"p13-{uuid.uuid4().hex[:8]}"

    # 1. Khoi tao Workspace va User
    with SessionLocal() as db:
        ws = Workspace(id=workspace_id, name="P13 Canary Workspace", slug=slug)
        user = User(id=user_id, email=f"canary-owner-{user_id}@test.invalid", hashed_password="mock")
        db.add_all([ws, user])

        # Khoi tao Ngan sach ban dau (100 units)
        budget = budget_guard.get_or_create_budget(db, workspace_id, default_allocated=100.0)

        # Khoi tao Brand Brief Version
        brief = BrandBriefVersion(
            workspace_id=workspace_id,
            version=1,
            brand_name="Canary Bento Co",
            objective="Canary research validation",
            voice_description="Thuc te, tin cay",
            language="vi-VN",
            current_audience="Dan van phong",
            target_audience="Nhan vien tre",
            status="APPROVED",
        )
        db.add(brief)

        # Khoi tao 3 SourceRecord thuc te (Real sources)
        s1 = SourceRecord(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            provider_id="tiktok",
            raw_external_id="tt_real_01",
            canonical_url="https://tiktok.com/@bento/video/01",
            title="Video nau bento that 01",
            observed_at=datetime.now(timezone.utc),
            synthetic=False,
            rights_basis="SIGNED_LICENSE",
            is_purged=False
        )
        s2 = SourceRecord(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            provider_id="tiktok",
            raw_external_id="tt_real_02",
            canonical_url="https://tiktok.com/@bento/video/02",
            title="Video nau bento that 02",
            observed_at=datetime.now(timezone.utc),
            synthetic=False,
            rights_basis="SIGNED_LICENSE",
            is_purged=False
        )
        db.add_all([s1, s2])
        db.commit()
        brief_id = brief.id
        s1_id = s1.id
        s2_id = s2.id

    # 2. Khoi tao RBAC Baha Auth
    with AuthSessionLocal() as auth_db:
        auth_db.add(AuthWorkspace(id=workspace_id, name="P13 WS", slug=f"auth-{slug}", status="ACTIVE"))
        auth_db.add(GlobalUser(id=user_id, email=f"canary-owner-{user_id}@test.invalid", status="ACTIVE"))
        auth_db.flush()

        mem_id = str(uuid.uuid4())
        auth_db.add(AuthMembership(id=mem_id, workspace_id=workspace_id, user_id=user_id, status="ACTIVE"))
        auth_db.flush()

        role_owner = lay_role(auth_db, "WORKSPACE_OWNER")
        auth_db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=mem_id,
            role_id=role_owner.id,
            scope_type="WORKSPACE",
            scope_id=workspace_id,
            status="ACTIVE",
        ))
        auth_db.commit()

    return {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "brief_id": brief_id,
        "source_ids": [s1_id, s2_id],
        "headers": {
            "Authorization": f"Bearer {tao_bearer(user_id)}",
            "X-Workspace-Id": workspace_id,
            "X-User-Id": user_id,
        },
    }


def test_t130_tenant_canary_approved_research_run_and_rollback(p13_fixture):
    """
    T130: tenant canary approved research run ->
    records real source IDs, lineage, quota cost and review output; rollback ready.
    """
    ws_id = p13_fixture["workspace_id"]
    headers = p13_fixture["headers"]
    brief_id = p13_fixture["brief_id"]
    expected_sources = p13_fixture["source_ids"]

    # 1. Kich hoat Canary Deployment (yeu cau human_approval va signed_rights)
    resp_deploy = client.post(
        "/v1/canary/deployments",
        json={
            "workspace_id": ws_id,
            "tenant_name": "Canary Tenant Alpha",
            "human_approval_id": "APPR_DOC_2026_10_22_ALPHA",
            "signed_rights_reference": "CONTRACT_TIKTOK_RIGHTS_2026_SIGNED",
            "traffic_percentage": 5.0,
        },
        headers=headers,
    )
    assert resp_deploy.status_code == 200, f"Response: {resp_deploy.text}"
    deploy_data = resp_deploy.json()
    deployment_id = deploy_data["deployment_id"]

    assert deploy_data["status"] == "CANARY_ACTIVE"
    assert deploy_data["traffic_percentage"] == 5.0
    assert deploy_data["is_rollback_ready"] is True

    # 2. Thuc thi Canary Research Run (T130)
    resp_run = client.post(
        "/v1/canary/runs/execute",
        json={
            "deployment_id": deployment_id,
            "workspace_id": ws_id,
            "brief_version_id": brief_id,
            "estimated_quota_units": 2.5,
            "reviewer_notes": "Xac minh chat luong tren 100% nguon that da ky ban quyen.",
        },
        headers=headers,
    )
    assert resp_run.status_code == 200, f"Response: {resp_run.text}"
    run_data = resp_run.json()

    # CAM KET T130:
    # 2.1 Records Real Source IDs (Khong dung mock/synthetic ID)
    assert len(run_data["real_source_ids"]) > 0
    for sid in run_data["real_source_ids"]:
        assert "synthetic" not in sid.lower()
    for exp_id in expected_sources:
        assert exp_id in run_data["real_source_ids"]

    # 2.2 Lineage (Dong doi du lieu)
    lineage = run_data["data_lineage"]
    assert lineage["brief_version_id"] == brief_id
    assert lineage["canary_deployment_id"] == deployment_id
    assert lineage["lineage_hash"] is not None
    assert "pipeline_stages" in lineage

    # 2.3 Quota Cost (Hach toan chi phi quota)
    assert run_data["quota_cost_units"] == 2.5
    with SessionLocal() as db:
        budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_id).first()
        assert budget.spent_units == pytest.approx(2.5)

    # 2.4 Review Output (Danh gia phe duyet cua con nguoi)
    review = run_data["review_output"]
    assert review["review_status"] == "APPROVED"
    assert review["human_approval_reference"] == "APPR_DOC_2026_10_22_ALPHA"
    assert review["signed_rights_verified"] is True

    # 2.5 Rollback Ready (San sang rollback)
    assert run_data["is_rollback_ready"] is True

    # 3. Kiem thu quy trinh Rollback Canary (T130 Rollback ready)
    resp_rollback = client.post(
        f"/v1/canary/deployments/{deployment_id}/rollback",
        json={
            "deployment_id": deployment_id,
            "workspace_id": ws_id,
            "rollback_reason": "Kiem thu rollback an toan theo T130",
        },
        headers=headers,
    )
    assert resp_rollback.status_code == 200
    rb_data = resp_rollback.json()
    assert rb_data["status"] == "ROLLED_BACK"
    assert rb_data["rollback_reason"] == "Kiem thu rollback an toan theo T130"
    assert rb_data["rolled_back_at"] is not None

    # 4. Kiem tra sau khi Rollback: Khong the tiep tuc chay run tren deployment da thu hoi
    resp_run_after = client.post(
        "/v1/canary/runs/execute",
        json={
            "deployment_id": deployment_id,
            "workspace_id": ws_id,
            "brief_version_id": brief_id,
            "estimated_quota_units": 1.0,
        },
        headers=headers,
    )
    assert resp_run_after.status_code == 400
    assert "rolled_back" in resp_run_after.text.lower()


def test_t131_revoked_provider_access_in_canary_no_bypass(p13_fixture):
    """
    T131: revoked provider access in canary ->
    source marked unavailable, no alternate bypass, UI informs operator safely.
    """
    ws_id = p13_fixture["workspace_id"]
    headers = p13_fixture["headers"]
    provider_id = "TIKTOK_OFFICIAL"

    # 1. Them mot bai viet nguon thuoc provider nay
    with SessionLocal() as db:
        src = SourceRecord(
            id=str(uuid.uuid4()),
            workspace_id=ws_id,
            provider_id=provider_id,
            raw_external_id="tt_canary_prov_01",
            canonical_url="https://tiktok.com/@brand/canary_p1",
            title="Video TikTok Official Canary",
            observed_at=datetime.now(timezone.utc),
            synthetic=False,
            rights_basis="SIGNED_LICENSE",
            is_purged=False
        )
        grant = ProviderAccessGrant(
            workspace_id=ws_id,
            provider_id=provider_id,
            status="ACTIVE",
            rights_basis="SIGNED_LICENSE",
            no_bypass_enforced=True
        )
        db.add_all([src, grant])
        db.commit()
        src_id = src.id

    # Kiem tra provider ban dau dang ACTIVE
    resp_init = client.get(
        f"/v1/canary/providers/{provider_id}/status?workspace_id={ws_id}",
        headers=headers
    )
    assert resp_init.status_code == 200
    assert resp_init.json()["status"] == "ACTIVE"

    # 2. THU HOI QUYEN TRUY CAP NHA CUNG CAP (REVOKE ACCESS)
    resp_revoke = client.post(
        "/v1/canary/providers/revoke",
        json={
            "workspace_id": ws_id,
            "provider_id": provider_id,
            "revocation_reason": "Doi tac yeu cau thu hoi giay phep du lieu live theo T131",
        },
        headers=headers,
    )
    assert resp_revoke.status_code == 200
    revoke_data = resp_revoke.json()

    # CAM KET T131:
    # 2.1 Status = REVOKED
    assert revoke_data["status"] == "REVOKED"
    # 2.2 Tuyet doi cam alternate bypass (No alternate bypass)
    assert revoke_data["no_bypass_enforced"] is True
    # 2.3 UI/Operator duoc thong bao an toan
    assert "thu hồi an toàn" in revoke_data["message"]
    assert "no alternate bypass" in revoke_data["message"]

    # 3. Kiem tra lai Provider Status
    resp_status = client.get(
        f"/v1/canary/providers/{provider_id}/status?workspace_id={ws_id}",
        headers=headers
    )
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert status_data["status"] == "REVOKED"
    assert status_data["no_bypass_enforced"] is True
    assert "không khả dụng" in status_data["message"]

    # 4. Kiem tra Source da bi danh dau unavailable / purged trong CSDL
    with SessionLocal() as db:
        src_db = db.query(SourceRecord).filter(SourceRecord.id == src_id).first()
        assert src_db.is_purged is True
        assert src_db.purged_at is not None

        # 5. Kiem tra toan he thong bang script kiem toan audit_live_sources tren session live
        audit_res = audit_live_sources(db)
        assert audit_res["banned_sources_detected"] == 0
        assert audit_res["revoked_active_sources_detected"] == 0
        assert audit_res["no_alternate_bypass_confirmed"] is True
        assert audit_res["audit_gate_passed"] is True

    # Kiem tra dong thoi audit tren file offline DB tren dia
    audit_offline = audit_live_sources("03_ban_lam_viec/sin_content_api/sin_content_offline.db")
    assert audit_offline["banned_sources_detected"] == 0
    assert audit_offline["revoked_active_sources_detected"] == 0
    assert audit_offline["no_alternate_bypass_confirmed"] is True
    assert audit_offline["audit_gate_passed"] is True

