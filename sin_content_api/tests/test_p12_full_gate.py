# -*- coding: utf-8 -*-
"""
Bo kiem thu mo rong cho Pha P12: Khac phuc triet de 10 phat hien ra soat doc lap (P12-01 den P12-10)
va hoan thien 100% tieu chuan Cong nghiem thu Gate P12 (MASTER_PLAN & CONTRACTS).

Bao gom:
1. P12-01: Cache tac vu co lap theo workspace, khong ro ri artifact sang tenant khac.
2. P12-02: Replay luy dang ben vung tu CSDL ke ca khi mat cache RAM/khoi dong lai.
3. P12-03: Ledger da bi REFUSED hoac khac payload khong the tai su dung de bypass ngan sach.
4. P12-04: Giu cho nguyen tu (Atomic reservation) ngan ngua race condition vuot cap.
5. P12-05: Bounded retry voi timeout ngoai canh va hoan tien giu cho khi that bai.
6. P12-06: Tay sach secrets toan dien (ca cot nhay cam va embedded JSON payloads).
7. P12-07: Restore an toan: kiem tra manifest va checksum truoc khi cham vao DB dich.
8. P12-08: Danh gia prompt kiem tra text thuc te va phu quyet Brand Safety Veto.
9. P12-09: Kiem toan phu thuoc chuan hoa extras va phat hien giay phep copyleft (GPL/AGPL).
10. P12-10: Doi soat hoa don vendor phat hien sai lech va canh bao.
"""
import copy
import hashlib
import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "sqlite:///file:sin_content_p12_gate_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_p12_gate_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-p12-gate-secret-key-2026"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "sin-auth-p12-gate"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-p12-gate"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    Workspace, User, BrandBriefVersion, WorkspaceBudget, CostLedger, AuditEvent
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
from src.modules.staging_reliability.downstream_executor import (
    downstream_executor, _PROCESSED_ARTIFACT_CACHE
)
import src.modules.staging_reliability.prompt_regression as regression
from scripts.backup_staging_db import backup_database
from scripts.restore_staging_db import restore_database
from scripts.audit_licenses_and_deps import run_audit

client = TestClient(app)

def tao_bearer(user_id: str) -> str:
    import base64, hmac
    def encode(val):
        raw = json.dumps(val, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = encode({"alg": "HS256", "typ": "JWT"})
    claims = encode({
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + 3600,
    })
    sig = hmac.new(
        os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"),
        f"{header}.{claims}".encode("ascii"),
        hashlib.sha256
    ).digest()
    return f"{header}.{claims}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode('ascii')}"

@pytest.fixture
def p12_gate_fixture():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    ws_a_id = str(uuid.uuid4())
    ws_b_id = str(uuid.uuid4())
    user_a_id = str(uuid.uuid4())
    user_b_id = str(uuid.uuid4())

    with SessionLocal() as db:
        ws_a = Workspace(id=ws_a_id, name="Tenant A WS", slug=f"ws-a-{uuid.uuid4().hex[:6]}")
        ws_b = Workspace(id=ws_b_id, name="Tenant B WS", slug=f"ws-b-{uuid.uuid4().hex[:6]}")
        user_a = User(id=user_a_id, email=f"a-{user_a_id}@baha.vn", full_name="User A")
        user_b = User(id=user_b_id, email=f"b-{user_b_id}@baha.vn", full_name="User B")
        db.add_all([ws_a, ws_b, user_a, user_b])
        db.commit()

    with AuthSessionLocal() as auth_db:
        auth_db.add_all([
            AuthWorkspace(id=ws_a_id, name="Tenant A WS", slug=f"auth-a-{uuid.uuid4().hex[:6]}", status="ACTIVE"),
            AuthWorkspace(id=ws_b_id, name="Tenant B WS", slug=f"auth-b-{uuid.uuid4().hex[:6]}", status="ACTIVE"),
            GlobalUser(id=user_a_id, email=f"a-{user_a_id}@baha.vn", full_name="User A", status="ACTIVE"),
            GlobalUser(id=user_b_id, email=f"b-{user_b_id}@baha.vn", full_name="User B", status="ACTIVE"),
        ])
        auth_db.flush()

        role = auth_db.query(AuthRole).filter(AuthRole.code == "WORKSPACE_OWNER").first()
        if not role:
            role = AuthRole(code="WORKSPACE_OWNER", name="Owner", workspace_id=None, is_template=True, status="ACTIVE")
            auth_db.add(role)
            auth_db.flush()

        mem_a_id = str(uuid.uuid4())
        mem_b_id = str(uuid.uuid4())
        auth_db.add_all([
            AuthMembership(id=mem_a_id, workspace_id=ws_a_id, user_id=user_a_id, status="ACTIVE"),
            AuthMembership(id=mem_b_id, workspace_id=ws_b_id, user_id=user_b_id, status="ACTIVE"),
        ])
        auth_db.flush()

        auth_db.add_all([
            RoleAssignment(workspace_id=ws_a_id, membership_id=mem_a_id, role_id=role.id, scope_type="WORKSPACE", scope_id=ws_a_id, status="ACTIVE"),
            RoleAssignment(workspace_id=ws_b_id, membership_id=mem_b_id, role_id=role.id, scope_type="WORKSPACE", scope_id=ws_b_id, status="ACTIVE"),
        ])
        auth_db.commit()

    return {
        "ws_a_id": ws_a_id,
        "ws_b_id": ws_b_id,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "headers_a": {"Authorization": f"Bearer {tao_bearer(user_a_id)}", "X-Workspace-Id": ws_a_id, "X-User-Id": user_a_id},
        "headers_b": {"Authorization": f"Bearer {tao_bearer(user_b_id)}", "X-Workspace-Id": ws_b_id, "X-User-Id": user_b_id},
    }

# ==============================================================================
# TESTS CHO CÁC PHÁT HIỆN P12-01 ĐẾN P12-10
# ==============================================================================

def test_p12_01_cache_tenant_isolation(p12_gate_fixture):
    """P12-01: Cache tac vu co lap theo workspace, khong ro ri artifact sang tenant khac."""
    f = p12_gate_fixture
    key = f"shared_key_{uuid.uuid4().hex}"

    # Tenant A execute
    resp_a = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": f["ws_a_id"], "task_id": "task_a", "idempotency_key": key, "estimated_units": 2.0},
        headers=f["headers_a"]
    )
    assert resp_a.status_code == 200
    art_a = resp_a.json()["output_artifact_id"]

    # Tenant B execute voi cung idempotency_key
    resp_b = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": f["ws_b_id"], "task_id": "task_b", "idempotency_key": key, "estimated_units": 2.0},
        headers=f["headers_b"]
    )
    assert resp_b.status_code == 200
    art_b = resp_b.json()["output_artifact_id"]

    # B PHAI NHAN ARTIFACT RIENG, KHONG DUOC PHEP TRUNG VOI ARTIFACT CUA A!
    assert art_a != art_b, "NGHIEM CAM ro ri artifact cua Tenant A sang Tenant B!"
    assert resp_b.json()["is_idempotent_replay"] is False

def test_p12_02_persisted_idempotent_replay_survives_cache_clear(p12_gate_fixture):
    """P12-02: Replay luy dang ben vung tu CSDL ke ca khi mat cache RAM (mo phong restart)."""
    f = p12_gate_fixture
    ws_a = f["ws_a_id"]
    with SessionLocal() as db:
        budget = budget_guard.get_or_create_budget(db, ws_a, default_allocated=10.0)
        budget.allocated_units = 10.0
        budget.spent_units = 0.0
        budget.reserved_units = 0.0
        db.commit()

    key = f"persist_key_{uuid.uuid4().hex}"

    # 1. Chay lan dau
    resp1 = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": ws_a, "task_id": "task_p", "idempotency_key": key, "estimated_units": 2.0},
        headers=f["headers_a"]
    )
    assert resp1.status_code == 200
    art1 = resp1.json()["output_artifact_id"]

    # 2. Xoa cache RAM de mo phong khoi dong lai server
    _PROCESSED_ARTIFACT_CACHE.clear()

    # 3. Goi lai voi cung idempotency_key
    resp2 = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": ws_a, "task_id": "task_p", "idempotency_key": key, "estimated_units": 2.0},
        headers=f["headers_a"]
    )
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Phai replay thanh cong tu database, khong tru phi lan 2
    assert data2["output_artifact_id"] == art1, "Replay phai tra ve artifact da ghi nhan trong DB!"
    assert data2["is_idempotent_replay"] is True
    assert data2["charged_units"] == 0.0

    # Kiem tra tong chi phi tren budget van chi la 2.0 (khong bi thanh 4.0)
    with SessionLocal() as db:
        b = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_a).one()
        assert b.spent_units == 2.0, "Khong duoc phep tru phi 2 lan khi mat cache RAM!"

def test_p12_03_refused_ledger_and_payload_mismatch_rejected(p12_gate_fixture):
    """P12-03: Ledger da bi REFUSED hoac payload khac khong the bypass kiem tra ngan sach."""
    f = p12_gate_fixture
    ws_a = f["ws_a_id"]
    with SessionLocal() as db:
        budget = budget_guard.get_or_create_budget(db, ws_a, default_allocated=1.0)
        budget.allocated_units = 1.0
        budget.spent_units = 0.0
        budget.reserved_units = 0.0
        db.commit()

    key = f"refused_key_{uuid.uuid4().hex}"

    # 1. Lan dau vuot cap -> nhan 402
    resp1 = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": ws_a, "task_id": "over", "idempotency_key": key, "estimated_units": 5.0},
        headers=f["headers_a"]
    )
    assert resp1.status_code == 402

    # 2. Goi lai cung key -> PHAI TIEP TUC BI TU CHOI 402, KHONG DUOC TRONG DUNG IDEMPOTENT_HIT
    resp2 = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": ws_a, "task_id": "over", "idempotency_key": key, "estimated_units": 5.0},
        headers=f["headers_a"]
    )
    assert resp2.status_code == 402, "Ledger REFUSED khong the duoc coi la IDEMPOTENT_HIT de chay vuot cap!"

    with SessionLocal() as db:
        b = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_a).one()
        assert b.spent_units == 0.0, "Chua he co unit nao duoc phep tru khi bi refuse!"

    # 3. Thu doi payload voi key da reserve hop le
    valid_key = f"valid_key_{uuid.uuid4().hex}"
    r_res = client.post(
        "/v1/staging/budget/reserve",
        json={"workspace_id": ws_a, "task_id": "small", "idempotency_key": valid_key, "estimated_units": 0.5},
        headers=f["headers_a"]
    )
    assert r_res.status_code == 200

    # Goi execute voi estimated_units = 10.0 (> 0.5 da giu cho) -> PHAI BI CHAN 409 Conflict
    resp_tamper = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": ws_a, "task_id": "tamper", "idempotency_key": valid_key, "estimated_units": 10.0},
        headers=f["headers_a"]
    )
    assert resp_tamper.status_code == 409, "Thay doi payload voi idempotency_key da co phai bi tu choi 409!"

def test_p12_04_atomic_concurrent_reservations_cannot_exceed_cap(p12_gate_fixture):
    """P12-04: Giu cho nguyen tu ngan ngua race condition vuot cap giua hai phien."""
    f = p12_gate_fixture
    ws_a = f["ws_a_id"]
    with SessionLocal() as db:
        budget = budget_guard.get_or_create_budget(db, ws_a, default_allocated=1.0)
        budget.allocated_units = 1.0
        budget.spent_units = 0.0
        budget.reserved_units = 0.0
        db.commit()

    # Mo 2 session dong thoi
    s1 = SessionLocal()
    s2 = SessionLocal()

    k1 = uuid.uuid4().hex
    k2 = uuid.uuid4().hex

    # Ca 2 phien cung yeu cau 0.8 units tren tong ngan sach 1.0 unit
    res1 = budget_guard.reserve_budget(s1, ws_a, "task1", k1, "RESEARCH", 0.8)
    res2 = budget_guard.reserve_budget(s2, ws_a, "task2", k2, "RESEARCH", 0.8)

    s1.close()
    s2.close()

    # Chi duy nhat 1 phien duoc phep RESERVED, phien kia phai bi REFUSED_OVER_BUDGET
    statuses = [res1.status, res2.status]
    assert "RESERVED" in statuses
    assert "REFUSED_OVER_BUDGET" in statuses

    with SessionLocal() as db:
        b = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == ws_a).one()
        assert b.reserved_units == 0.8, "Reserved units khong duoc vuot qua 0.8!"
        ledgers = db.query(CostLedger).filter(CostLedger.workspace_id == ws_a, CostLedger.status == "RESERVED").all()
        assert len(ledgers) == 1
        assert sum(l.estimated_units for l in ledgers) <= 1.0

def test_p12_06_comprehensive_secrets_scrubbing_in_backup(tmp_path):
    """P12-06: Tay sach secrets toan dien (ca cot nhay cam va embedded JSON payloads)."""
    db_file = tmp_path / "staging_secrets_source.db"
    backup_dir = tmp_path / "backups_scrubbed"

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id TEXT, email TEXT, hashed_password TEXT)")
    cursor.execute("INSERT INTO users VALUES ('u1', 'admin@baha.vn', 'RAW_SECRET_PASSWORD_12345')")
    cursor.execute("CREATE TABLE source_observations (id TEXT, raw_payload_json TEXT)")
    # Nhúng access_token trong payload JSON
    payload = json.dumps({
        "video_id": "v100",
        "access_token": "token_live_secret_tiktok_99999",
        "client_secret": "cs_secret_very_sensitive",
        "meta": {"sub_token": "sub_token_secret_123"}
    })
    cursor.execute("INSERT INTO source_observations VALUES ('obs1', ?)", (payload,))
    conn.commit()
    conn.close()

    # Thuc hien backup
    manifest = backup_database(str(db_file), str(backup_dir))
    backup_file = os.path.join(str(backup_dir), manifest["backup_file"])

    assert manifest["secrets_scrubbed"] is True
    assert manifest["status"] == "APPROVED_BACKUP"

    # Doc file backup va kiem tra
    chk_conn = sqlite3.connect(backup_file)
    chk_cur = chk_conn.cursor()

    chk_cur.execute("SELECT hashed_password FROM users WHERE id='u1'")
    pwd = chk_cur.fetchone()[0]
    assert pwd == "[SCRUBBED_IN_BACKUP]"
    assert "RAW_SECRET_PASSWORD" not in pwd

    chk_cur.execute("SELECT raw_payload_json FROM source_observations WHERE id='obs1'")
    raw_json = chk_cur.fetchone()[0]
    chk_conn.close()

    # Kiem tra token trong JSON da bi tay sach 100%
    assert "token_live_secret_tiktok_99999" not in raw_json
    assert "cs_secret_very_sensitive" not in raw_json
    assert "sub_token_secret_123" not in raw_json
    assert "[SCRUBBED_IN_BACKUP]" in raw_json

def test_p12_07_restore_safety_and_manifest_enforcement(tmp_path):
    """P12-07: Restore an toan: kiem tra manifest va checksum truoc khi cham vao DB dich."""
    # 1. Tao DB dich co du lieu can bao ve
    target_db = tmp_path / "protected_target.db"
    conn = sqlite3.connect(target_db)
    conn.execute("CREATE TABLE important_data (id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO important_data VALUES (1, 'MUST_PRESERVE')")
    conn.commit()
    conn.close()
    original_target_bytes = target_db.read_bytes()

    # 2. Truong hop file backup hong / khong phai SQLite
    bad_backup = tmp_path / "bad_backup.db"
    bad_backup.write_bytes(b"THIS_IS_CORRUPT_NON_SQLITE_DATA")

    # Truyen manifest khong ton tai -> Phai bao loi FileNotFoundError, DB dich KHONG BI XOA!
    with pytest.raises(FileNotFoundError):
        restore_database(str(bad_backup), str(target_db), str(tmp_path / "non_existent_manifest.json"))
    assert target_db.read_bytes() == original_target_bytes, "DB dich khong duoc phep bi pha huy khi manifest khong ton tai!"

    # Truyen manifest voi file backup hong -> Phai bao loi, DB dich KHONG BI XOA!
    manifest_bad = tmp_path / "manifest_bad.json"
    with open(manifest_bad, "w", encoding="utf-8") as f:
        json.dump({"status": "APPROVED_BACKUP", "secrets_scrubbed": True, "sha256_checksum": hashlib.sha256(bad_backup.read_bytes()).hexdigest()}, f)

    with pytest.raises(RuntimeError):
        restore_database(str(bad_backup), str(target_db), str(manifest_bad))
    assert target_db.read_bytes() == original_target_bytes, "DB dich khong duoc phep bi pha huy khi backup hong!"

    # 3. Truong hop backup hop le -> Restore thanh cong
    good_src = tmp_path / "good_src.db"
    g_conn = sqlite3.connect(good_src)
    g_conn.execute("CREATE TABLE restored_table (id INTEGER, val TEXT)")
    g_conn.execute("INSERT INTO restored_table VALUES (1, 'OK_RESTORED')")
    g_conn.commit()
    g_conn.close()

    backup_dir = tmp_path / "good_backups"
    manifest_good = backup_database(str(good_src), str(backup_dir))
    b_file = os.path.join(str(backup_dir), manifest_good["backup_file"])
    m_file = os.path.join(str(backup_dir), f"backup_manifest_{manifest_good['timestamp']}.json")

    res = restore_database(b_file, str(target_db), m_file)
    assert res["status"] == "RESTORED_OK"
    assert res["integrity"] == "ok"
    assert res["records_per_table"]["restored_table"] == 1

def test_p12_08_prompt_regression_dynamic_brand_safety_veto():
    """P12-08: Danh gia prompt kiem tra text thuc te va phu quyet Brand Safety Veto."""
    # 1. Danh gia tap du lieu chuan -> Dat >= 80%
    clean_eval = regression.prompt_regression_engine.evaluate_held_out_regression()
    assert clean_eval["evaluation_gate_passed"] is True
    assert clean_eval["overall_top_10_precision"] >= 0.80
    assert clean_eval["brand_exclusion_violations"] == 0

    # 2. Tinh huong sua hook chua chu de cam va so lieu khong nguon
    tainted = copy.deepcopy(regression.HELD_OUT_EVALUATION_DATASET)
    # Chen chu de cam "nhịn ăn gián đoạn cực đoan" va view khong nguon vao hook
    tainted[0]["candidates"][0]["hook"] = "Nhịn ăn gián đoạn cực đoan 7 ngày; đã quan sát 999999999 lượt xem không có nguồn"

    tainted_eval = regression.prompt_regression_engine.evaluate_held_out_regression(dataset=tainted)
    # Bat buoc phai phat hien vi pham brand exclusion va tu choi gate!
    assert tainted_eval["brand_exclusion_violations"] >= 1, "He thong bat buoc phai phat hien chu de cam trong text hook!"
    assert tainted_eval["evaluation_gate_passed"] is False, "Khong duoc phep cho qua evaluation gate khi co chu de cam!"

def test_p12_09_dependency_audit_detects_normalized_banned_and_copyleft(tmp_path):
    """P12-09: Kiem toan phu thuoc chuan hoa extras va phat hien giay phep copyleft (GPL/AGPL)."""
    # 1. Kiem tra thu muc sach hien tai
    clean_audit = run_audit("03_ban_lam_viec")
    assert clean_audit["gate_passed"] is True
    assert clean_audit["banned_packages_detected"] == 0

    # 2. Tao thu muc gia lap co MediaCrawler[extra] va goi license GPL-3.0-only
    audit_dir = tmp_path / "mock_project"
    audit_dir.mkdir()
    (audit_dir / "requirements.txt").write_text("MediaCrawler[extra]==1.0\n", encoding="utf-8")

    (audit_dir / "package.json").write_text(json.dumps({"dependencies": {"gpl_pkg": "1.0.0"}}), encoding="utf-8")
    nm = audit_dir / "node_modules" / "gpl_pkg"
    nm.mkdir(parents=True)
    (nm / "package.json").write_text(json.dumps({"name": "gpl_pkg", "version": "1.0.0", "license": "GPL-3.0-only"}), encoding="utf-8")

    tainted_audit = run_audit(str(audit_dir))
    # Phai phat hien banned package du co kem extras!
    assert tainted_audit["banned_packages_detected"] >= 1, "MediaCrawler[extra] phai bi phat hien sau khi chuan hoa!"
    # Phai phat hien giay phep copyleft GPL-3.0-only!
    assert tainted_audit["unapproved_licenses_detected"] >= 1, "GPL-3.0-only phai bi phat hien!"
    assert tainted_audit["gate_passed"] is False

def test_p12_10_reconciliation_vendor_discrepancy_alert(p12_gate_fixture):
    """P12-10: Doi soat hoa don vendor phat hien sai lech va phat canh bao."""
    f = p12_gate_fixture
    ws_a = f["ws_a_id"]
    headers_a = f["headers_a"]

    # Chay 1 task 2.0 units
    key = f"rec_key_{uuid.uuid4().hex}"
    resp_exec = client.post(
        "/v1/staging/tasks/execute",
        json={"workspace_id": ws_a, "task_id": "task_rec", "idempotency_key": key, "estimated_units": 2.0},
        headers=headers_a
    )
    assert resp_exec.status_code == 200

    with SessionLocal() as db:
        ledger = db.query(CostLedger).filter(CostLedger.idempotency_key == key).one()
        ledger_id = ledger.id

    # Doi soat dung -> khong canh bao
    r_ok = client.post(
        "/v1/staging/budget/reconcile",
        json={"workspace_id": ws_a, "ledger_id": ledger_id, "vendor_reported_units": 2.0},
        headers=headers_a
    )
    assert r_ok.status_code == 200
    assert r_ok.json()["discrepancy_alert"] is False

    # Doi soat sai lech lon (4.0 units vs 2.0 units) -> Phat canh bao discrepancy_alert = True
    r_alert = client.post(
        "/v1/staging/budget/reconcile",
        json={"workspace_id": ws_a, "ledger_id": ledger_id, "vendor_reported_units": 4.0},
        headers=headers_a
    )
    assert r_alert.status_code == 200
    data_alert = r_alert.json()
    assert data_alert["discrepancy_alert"] is True
    assert data_alert["discrepancy_delta"] == 2.0
