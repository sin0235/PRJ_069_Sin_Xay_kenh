import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

from src.auth.mat_khau_noi_bo import hash_password
from scripts.khoi_tao_production_noi_bo import workspace_id_for_project


def _backup_database(source: Path, destination: Path) -> None:
    source_db = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True)
    target_db = sqlite3.connect(destination)
    try:
        source_db.backup(target_db)
    finally:
        target_db.close()
        source_db.close()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_khoi_tao_co_so_du_lieu_that_tach_rieng_va_chay_lai_an_toan(tmp_path):
    api_root = Path(__file__).resolve().parents[1]
    project_root = api_root.parent
    seed_dir = tmp_path / "nguon"
    data_dir = tmp_path / "du_lieu"
    seed_dir.mkdir()
    for name in ("sin_content_offline.db", "baha_auth_live.db"):
        _backup_database(api_root / name, seed_dir / name)
    original_hashes = {name: _sha256(api_root / name) for name in ("sin_content_offline.db", "baha_auth_live.db")}
    llm_env = tmp_path / "9rt.env"
    llm_env.write_text("base_url=https://gateway.example/v1\napi-key=sample-not-real-api-key\n", encoding="utf-8")
    workspace_id = workspace_id_for_project("PRJ_069")
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": os.pathsep.join((str(api_root), str(project_root))),
        "PRJ069_BOOTSTRAP_SEED_DIR": str(seed_dir),
        "PRJ069_BOOTSTRAP_DATA_DIR": str(data_dir),
        "LLM_API_KEY_FILE": str(llm_env),
        "LLM_ENABLED": "false",
        "LLM_BASE_URL": "https://gateway.example/v1",
        "LLM_MODEL": "cx/gpt-6-luna",
        "LLM_ENCRYPTION_MASTER_KEY": "test-master-key-not-for-use-32-bytes-minimum",
        "APP_ENV": "production",
        "TESTING": "0",
        "DEV_AUTH_BYPASS": "0",
        "AUTH_MODE": "local_password",
        "FOUNDER_EMAIL": "phuctoan235@gmail.com",
        "FOUNDER_PASSWORD_HASH": hash_password("test-founder-password-only"),
        "SIN_WORKSPACE_ID": workspace_id,
        "BAHA_AUTH_JWT_SECRET": "test-jwt-secret-not-for-use-at-least-forty-characters",
        "BAHA_AUTH_JWT_ISSUER": "issuer-test",
        "BAHA_AUTH_JWT_AUDIENCE": "audience-test",
    })
    script = api_root / "scripts" / "khoi_tao_production_noi_bo.py"

    for expected_state in ("initialized", "already_initialized"):
        result = subprocess.run([sys.executable, str(script)], env=env, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr
        assert expected_state in result.stdout
        assert "sample-not-real-api-key" not in result.stdout + result.stderr

    content_db = sqlite3.connect(data_dir / "sin_content_production.db")
    auth_db = sqlite3.connect(data_dir / "baha_auth_production.db")
    try:
        assert content_db.execute("select count(*) from workspaces where id=?", (workspace_id,)).fetchone()[0] == 1
        assert content_db.execute("select count(*) from users where email=?", ("phuctoan235@gmail.com",)).fetchone()[0] == 1
        llm = content_db.execute("select is_enabled,base_url,model,api_key_ciphertext from platform_llm_configurations").fetchone()
        assert llm[:3] == (1, "https://gateway.example/v1", "cx/gpt-6-luna")
        assert "sample-not-real-api-key" not in llm[3]
        role = auth_db.execute(
            "select r.code,ra.scope_type from role_assignments ra join roles r on r.id=ra.role_id join memberships m on m.id=ra.membership_id where m.workspace_id=?",
            (workspace_id,),
        ).fetchall()
        assert role == [("WORKSPACE_OWNER", "WORKSPACE")]
        policy = auth_db.execute("select stages_json from approval_policies where workspace_id=? and status='ACTIVE'", (workspace_id,)).fetchone()
        assert json.loads(policy[0]) == [{"stage_key": "FINAL", "allowed_role": "WORKSPACE_OWNER"}]
    finally:
        content_db.close()
        auth_db.close()

    assert original_hashes == {name: _sha256(api_root / name) for name in original_hashes}
    marker = json.loads((data_dir / ".prj069-production.json").read_text(encoding="utf-8"))
    assert marker["workspace_id"] == workspace_id
