"""
Bo kiem thu Pha P12: Security, Reliability & Evaluation Staging
Bao gom cac ca kiem thu nghiem ngat:
- T120: tenant fuzzing / auth bypass attempts -> no cross-tenant exposure; 0 unresolved HIGH/CRITICAL issues.
- T121: external timeout after downstream job side effect -> bounded retry, idempotent output, no duplicate costs/artifacts.
- T122: budget of 1 unit and task estimated > cap -> refused/rescoped before billable work; new billable calls stop before budget reservation is exceeded; separately reconcile vendor billing and alert on discrepancies.
- T123: restore staging DB from approved backup -> documented restore works; secrets not embedded in backup artifacts.
- T124: model/prompt variation regression test -> all hard-source tests pass and held-out top-10 >=80% human relevance.
- T125: dependency/software composition/license audit -> no banned/non-commercial unapproved license; known critical vulns closed.
"""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Cau hinh moi truong cho SQLite in-memory de dam bao doc lap hoan toan
TEST_DATABASE_URL = "sqlite:///file:sin_content_p12_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_p12_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap-p12"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap-p12"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test-p12"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    Workspace, User, BrandBriefVersion, IdeaCard, SourceRecord,
    WorkspaceBudget, CostLedger
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
from src.modules.staging_reliability.prompt_regression import prompt_regression_engine
from scripts.backup_staging_db import backup_database
from scripts.restore_staging_db import restore_database
from scripts.audit_licenses_and_deps import run_audit

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
def p12_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    ws_a_id = str(uuid.uuid4())
    ws_b_id = str(uuid.uuid4())
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())

    # 1. Khoi tao 2 Workspaces rieng biet trong Content DB
    with SessionLocal() as db:
        ws_a = Workspace(id=ws_a_id, name="Tenant A Workspace", slug=f"ws-a-{uuid.uuid4().hex[:6]}")
        ws_b = Workspace(id=ws_b_id, name="Tenant B Workspace", slug=f"ws-b-{uuid.uuid4().hex[:6]}")
        user_a = User(id=user_a_id, email=f"user-a-{user_a_id}@test.invalid", hashed_password="mock")
        user_b = User(id=user_b_id, email=f"user-b-{user_b_id}@test.invalid", hashed_password="mock")
        db.add_all([ws_a, ws_b, user_a, user_b])

        # Du lieu nhay cam cua Tenant B
        brief_b = BrandBriefVersion(
            workspace_id=ws_b_id,
            version=1,
            brand_name="Secret Brand B",
            objective="Ke hoach bi mat cua Tenant B",
            voice_description="Bao mat tuyet doi",
            language="vi-VN",
            current_audience="Khach hang VIP B",
            target_audience="Thi phan bi mat",
            status="APPROVED",
        )
        db.add(brief_b)
        db.commit()
        brief_b_id = brief_b.id

    # 2. Khoi tao Auth DB va phan quyen
    with AuthSessionLocal() as auth_db:
        auth_db.add_all([
            AuthWorkspace(id=ws_a_id, name="Tenant A WS", slug=f"auth-a-{uuid.uuid4().hex[:6]}", status="ACTIVE"),
            AuthWorkspace(id=ws_b_id, name="Tenant B WS", slug=f"auth-b-{uuid.uuid4().hex[:6]}", status="ACTIVE"),
            GlobalUser(id=user_a_id, email=f"user-a-{user_a_id}@test.invalid", status="ACTIVE"),
            GlobalUser(id=user_b_id, email=f"user-b-{user_b_id}@test.invalid", status="ACTIVE"),
        ])
        auth_db.flush()

        mem_a_id = str(uuid.uuid4())
        mem_b_id = str(uuid.uuid4())
        auth_db.add_all([
            AuthMembership(id=mem_a_id, workspace_id=ws_a_id, user_id=user_a_id, status="ACTIVE"),
            AuthMembership(id=mem_b_id, workspace_id=ws_b_id, user_id=user_b_id, status="ACTIVE"),
        ])
        auth_db.flush()

        role_owner = lay_role(auth_db, "WORKSPACE_OWNER")
        auth_db.add_all([
            RoleAssignment(
                workspace_id=ws_a_id,
                membership_id=mem_a_id,
                role_id=role_owner.id,
                scope_type="WORKSPACE",
                scope_id=ws_a_id,
                status="ACTIVE",
            ),
            RoleAssignment(
                workspace_id=ws_b_id,
                membership_id=mem_b_id,
                role_id=role_owner.id,
                scope_type="WORKSPACE",
                scope_id=ws_b_id,
                status="ACTIVE",
            )
        ])
        auth_db.commit()

    return {
        "ws_a_id": ws_a_id,
        "ws_b_id": ws_b_id,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "brief_b_id": brief_b_id,
        "headers_a": {
            "Authorization": f"Bearer {tao_bearer(user_a_id)}",
            "X-Workspace-Id": ws_a_id,
            "X-User-Id": user_a_id,
        },
        "headers_b": {
            "Authorization": f"Bearer {tao_bearer(user_b_id)}",
            "X-Workspace-Id": ws_b_id,
            "X-User-Id": user_b_id,
        },
    }


def test_t120_tenant_fuzzing_and_auth_bypass_zero_cross_exposure(p12_fixture):
    """
    T120: tenant fuzzing / auth bypass attempts ->
    no cross-tenant exposure; 0 unresolved HIGH/CRITICAL issues.
    """
    ws_a = p12_fixture["ws_a_id"]
    ws_b = p12_fixture["ws_b_id"]
    user_a = p12_fixture["user_a_id"]
    brief_b_id = p12_fixture["brief_b_id"]

    # 1. Tan cong IDOR: User Tenant A co truy cap brief cua Tenant B
    # Endpoint yeu cau brief trong workspace -> Scoped query tra ve 404 de khong lo su ton tai
    resp_idor = client.get(
        f"/v1/briefs/{brief_b_id}",
        headers=p12_fixture["headers_a"] # Token va Header la cua Tenant A
    )
    assert resp_idor.status_code in [403, 404], "Khong duoc phep xem tai nguyen cua tenant khac!"
    assert "Secret Brand B" not in resp_idor.text, "LO DU LIEU CUA TENANT KHAC!"

    # 2. Tan cong Header Spoofing: User A gui kem header X-Workspace-Id cua Tenant B
    headers_spoofed = {
        "Authorization": f"Bearer {tao_bearer(user_a)}",
        "X-Workspace-Id": ws_b, # GIA DANH WORKSPACE B
        "X-User-Id": user_a,
    }
    resp_spoof = client.get(
        f"/v1/briefs/{brief_b_id}",
        headers=headers_spoofed
    )
    # He thong RBAC Canonical kiem tra User A khong co Membership/Role trong Workspace B -> TU CHOI 403
    assert resp_spoof.status_code in [403, 404], "Gia mao header workspace_id phai bi chan!"
    assert "Secret Brand B" not in resp_spoof.text

    # 3. Fuzzing token gia mao / malformed token
    headers_malformed = {
        "Authorization": "Bearer token_khong_hop_le_fuzzing_xxx.yyy.zzz",
        "X-Workspace-Id": ws_a,
        "X-User-Id": user_a,
    }
    resp_malformed = client.get(
        f"/v1/briefs/{brief_b_id}",
        headers=headers_malformed
    )
    assert resp_malformed.status_code in [401, 403], "Token sai phai bi tu choi xac thuc!"

    # 4. Truy cap channel performance cua tenant khac
    resp_chan_cross = client.get(
        f"/v1/feedback/channels/secret_channel_b/performance?workspace_id={ws_b}",
        headers=p12_fixture["headers_a"]
    )
    assert resp_chan_cross.status_code in [403, 404]


def test_t121_external_timeout_bounded_retry_idempotent_no_duplicate_costs(p12_fixture):
    """
    T121: external timeout after downstream job side effect ->
    bounded retry, idempotent output, no duplicate costs/artifacts.
    """
    ws_a = p12_fixture["ws_a_id"]
    headers_a = p12_fixture["headers_a"]

    # Cap ngan sach ban dau cho Tenant A
    with SessionLocal() as db:
        budget_guard.get_or_create_budget(db, ws_a, default_allocated=50.0)

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    idempotency_key = f"idem_{uuid.uuid4().hex[:12]}"

    # 1. Goi thuc thi task co mo phong timeout downstream
    resp_run = client.post(
        "/v1/staging/tasks/execute",
        json={
            "workspace_id": ws_a,
            "task_id": task_id,
            "idempotency_key": idempotency_key,
            "action_type": "RESEARCH_RUN",
            "estimated_units": 2.5,
            "simulate_timeout": True, # Kich hoat mo phong timeout ngoai canh
            "max_retries": 3,
        },
        headers=headers_a,
    )
    assert resp_run.status_code == 200, f"Response: {resp_run.text}"
    data_run = resp_run.json()

    assert data_run["status"] == "COMPLETED"
    assert data_run["retry_count"] > 0, "Phai thuc hien bounded retry khi gap timeout"
    assert data_run["retry_count"] <= 3, "So lan retry phai bi chan (bounded retry)"
    first_artifact_id = data_run["output_artifact_id"]
    assert first_artifact_id is not None
    assert data_run["charged_units"] == 2.5
    assert data_run["is_idempotent_replay"] is False

    # 2. Goi lai CHINH XAC cung idempotency_key (mo phong retry do timeout o phia client)
    resp_replay = client.post(
        "/v1/staging/tasks/execute",
        json={
            "workspace_id": ws_a,
            "task_id": task_id,
            "idempotency_key": idempotency_key,
            "action_type": "RESEARCH_RUN",
            "estimated_units": 2.5,
            "simulate_timeout": False,
            "max_retries": 3,
        },
        headers=headers_a,
    )
    assert resp_replay.status_code == 200
    data_replay = resp_replay.json()

    # CAM KET T121:
    # - Output luy dang (idempotent output): Tra ve dung artifact truoc do
    assert data_replay["output_artifact_id"] == first_artifact_id, "Phai tra ve artifact cu, khong sinh artifact trung lap"
    # - Khong tru chi phi lan 2 (no duplicate costs)
    assert data_replay["charged_units"] == 0.0, "Goi lai cung idempotency_key khong duoc phep tinh them phi"
    assert data_replay["is_idempotent_replay"] is True


def test_t122_budget_cap_refusal_before_billable_work_and_reconciliation(p12_fixture):
    """
    T122: budget of 1 unit and task estimated > cap ->
    refused/rescoped before billable work; new billable calls stop before budget reservation is exceeded;
    separately reconcile vendor billing and alert on discrepancies.
    """
    ws_a = p12_fixture["ws_a_id"]
    headers_a = p12_fixture["headers_a"]

    # 1. Thiet lap ngan sach con dung 1.0 unit
    with SessionLocal() as db:
        budget = budget_guard.get_or_create_budget(db, ws_a, default_allocated=1.0)
        budget.allocated_units = 1.0
        budget.spent_units = 0.0
        budget.reserved_units = 0.0
        db.commit()

    # Task uoc tinh 5.0 units (> 1.0 unit kha dung)
    task_id = f"task_over_{uuid.uuid4().hex[:8]}"
    idem_key = f"idem_over_{uuid.uuid4().hex[:8]}"

    # 2. Goi reserve budget
    resp_reserve = client.post(
        "/v1/staging/budget/reserve",
        json={
            "workspace_id": ws_a,
            "task_id": task_id,
            "idempotency_key": idem_key,
            "action_type": "RESEARCH_RUN",
            "estimated_units": 5.0, # VUOT QUA NGAN SACH
        },
        headers=headers_a,
    )
    assert resp_reserve.status_code == 200
    data_reserve = resp_reserve.json()

    # CAM KET T122: Tu choi truoc khi thuc hien cong viec tinh phi
    assert data_reserve["status"] == "REFUSED_OVER_BUDGET"
    assert data_reserve["reserved_units"] == 0.0, "Khong duoc phep vuot qua hard reservation cap"

    # Thu execute task nay -> se bi chan voi loi 402 Payment Required
    resp_exec = client.post(
        "/v1/staging/tasks/execute",
        json={
            "workspace_id": ws_a,
            "task_id": task_id,
            "idempotency_key": f"exec_{idem_key}",
            "action_type": "RESEARCH_RUN",
            "estimated_units": 5.0,
        },
        headers=headers_a,
    )
    assert resp_exec.status_code == 402, "Phai bi tu choi thuc thi khi khong du ngan sach"

    # 3. Kiem tra Doi soat hoa don vendor (Reconcile vendor billing)
    # Tao 1 task hop le ton 1.0 unit
    task_ok_id = f"task_ok_{uuid.uuid4().hex[:8]}"
    idem_ok = f"idem_ok_{uuid.uuid4().hex[:8]}"
    resp_ok = client.post(
        "/v1/staging/tasks/execute",
        json={
            "workspace_id": ws_a,
            "task_id": task_ok_id,
            "idempotency_key": idem_ok,
            "action_type": "RESEARCH_RUN",
            "estimated_units": 1.0,
        },
        headers=headers_a,
    )
    assert resp_ok.status_code == 200

    # Lay ledger record cua task nay
    with SessionLocal() as db:
        ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == idem_ok).first()
        assert ledger is not None
        ledger_id = ledger.id

    # Doi soat voi so lieu vendor khop
    resp_rec_ok = client.post(
        "/v1/staging/budget/reconcile",
        json={
            "workspace_id": ws_a,
            "ledger_id": ledger_id,
            "vendor_reported_units": 1.0,
        },
        headers=headers_a,
    )
    assert resp_rec_ok.status_code == 200
    assert resp_rec_ok.json()["reconciled"] is True
    assert resp_rec_ok.json()["discrepancy_alert"] is False

    # Doi soat voi so lieu vendor sai lech lon (1.8 units vs 1.0 unit thuc te)
    resp_rec_discrepancy = client.post(
        "/v1/staging/budget/reconcile",
        json={
            "workspace_id": ws_a,
            "ledger_id": ledger_id,
            "vendor_reported_units": 1.8, # SAI LECH 80%
        },
        headers=headers_a,
    )
    assert resp_rec_discrepancy.status_code == 200
    assert resp_rec_discrepancy.json()["discrepancy_alert"] is True
    assert "CẢNH BÁO: Sai lệch chi phí" in resp_rec_discrepancy.json()["message"]


def test_t123_staging_db_backup_restore_and_secrets_scrubbing(tmp_path):
    """
    T123: restore staging DB from approved backup ->
    documented restore works; secrets not embedded in backup artifacts.
    """
    # 1. Tao mot database tam voi du lieu va secrets
    test_db = tmp_path / "test_staging_source.db"
    backup_dir = tmp_path / "backups"

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT, hashed_password TEXT)")
    cursor.execute("CREATE TABLE posts (id TEXT PRIMARY KEY, title TEXT)")
    cursor.execute("INSERT INTO users VALUES ('u1', 'admin@example.com', 'SECRET_SUPER_HASH_12345')")
    cursor.execute("INSERT INTO posts VALUES ('p1', 'Bai viet staging 01')")
    conn.commit()
    conn.close()

    # 2. Chay backup database
    manifest = backup_database(str(test_db), str(backup_dir))
    backup_file = os.path.join(str(backup_dir), manifest["backup_file"])

    assert os.path.exists(backup_file)
    assert manifest["secrets_scrubbed"] is True
    assert manifest["status"] == "APPROVED_BACKUP"

    # T123: KIEM SOAT SECRETS KHONG DUOC NHUNG VAO ARTIFACT BACKUP
    chk_conn = sqlite3.connect(backup_file)
    chk_cursor = chk_conn.cursor()
    chk_cursor.execute("SELECT hashed_password FROM users WHERE id='u1'")
    saved_pwd = chk_cursor.fetchone()[0]
    chk_conn.close()

    assert saved_pwd == "[SCRUBBED_IN_BACKUP]", "Secrets phai duoc tay sach khoi ban backup!"
    assert "SECRET_SUPER_HASH_12345" not in saved_pwd

    # 3. Chay restore database sang vi tri moi
    restore_target = tmp_path / "test_staging_restored.db"
    manifest_file = os.path.join(str(backup_dir), f"backup_manifest_{manifest['timestamp']}.json")

    restore_res = restore_database(backup_file, str(restore_target), manifest_file)
    assert restore_res["status"] == "RESTORED_OK"
    assert restore_res["integrity"] == "ok"
    assert restore_res["records_per_table"]["posts"] == 1
    assert restore_res["records_per_table"]["users"] == 1


def test_t124_model_prompt_variation_regression_and_human_quality():
    """
    T124: model/prompt variation regression test ->
    all hard-source tests pass and held-out top-10 >=80% human relevance.
    Protocol:
    - >= 3 customer briefs with different categories & excluded topics.
    - Top 10 evaluated per brief: >= 80% RELEVANT (>= 24/30 overall).
    - 0 brand exclusion violations, 0 fabricated metrics.
    """
    eval_result = prompt_regression_engine.evaluate_held_out_regression()

    assert eval_result["evaluation_gate_passed"] is True
    assert eval_result["overall_top_10_precision"] >= 0.80
    assert eval_result["brand_exclusion_violations"] == 0
    assert eval_result["fabricated_metrics_count"] == 0
    assert eval_result["verdict"] == "PASSED"

    # Kiem tra tung brief rieng biet
    for r in eval_result["brief_results"]:
        assert r["precision"] >= 0.80, f"Brief {r['brief_id']} dat duoi 80% relevance!"
        assert r["passed_gate"] is True


def test_t125_dependency_license_audit_no_banned_software():
    """
    T125: dependency/software composition/license audit ->
    no banned/non-commercial unapproved license; known critical vulns closed.
    """
    audit_res = run_audit("03_ban_lam_viec")

    assert audit_res["status"] == "PASS"
    assert audit_res["banned_packages_detected"] == 0
    assert audit_res["unapproved_licenses_detected"] == 0
    assert audit_res["critical_vulnerabilities"] == 0
    assert audit_res["gate_passed"] is True
    assert "No banned/non-commercial unapproved license" in audit_res["verdict"]
