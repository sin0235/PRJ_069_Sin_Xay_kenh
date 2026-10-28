import hashlib
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = API_ROOT / "scripts" / "khoi_tao_production_noi_bo.py"
DATABASES = ("sin_content_production.db", "baha_auth_production.db", "sin_dieu_phoi_dung.db")


def _create_seed(seed_dir: Path) -> None:
    seed_dir.mkdir(parents=True)
    for name in DATABASES:
        with sqlite3.connect(seed_dir / name) as db:
            db.execute("CREATE TABLE preserved_records (value TEXT NOT NULL)")
            db.execute("INSERT INTO preserved_records VALUES (?)", (name,))
    (seed_dir / "media_assets").mkdir()
    (seed_dir / "media_assets" / "existing.bin").write_bytes(b"existing media bytes")


def _run_bootstrap(
    tmp_path: Path,
    *,
    mode: str,
    seed_dir: Path | None,
    allowed_origins: str = "https://studio.example.test",
    cookie_secure: str = "true",
    owner_password: str = "test-only-owner-password",
) -> subprocess.CompletedProcess:
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    password_file = tmp_path / "owner-password"
    password_file.write_text(owner_password + "\n", encoding="utf-8")
    password_file.chmod(0o600)
    env = os.environ.copy()
    env.update({
        "APP_ENV": "production",
        "TESTING": "0",
        "DEV_AUTH_BYPASS": "0",
        "PRJ069_BOOTSTRAP_MODE": mode,
        "PRJ069_BOOTSTRAP_DATA_DIR": str(data_dir),
        "AUTH_OWNER_EMAIL": "owner@example.test",
        "AUTH_OWNER_PASSWORD_FILE": str(password_file),
        "AUTH_ALLOWED_ORIGINS": allowed_origins,
        "AUTH_COOKIE_SECURE": cookie_secure,
        "SIN_WORKSPACE_ID": str(uuid.uuid5(uuid.NAMESPACE_URL, str(tmp_path))),
        "SIN_WORKSPACE_NAME": "Isolated bootstrap test",
        "SIN_DUNG_DB_PATH": str(data_dir / DATABASES[2]),
        "BAHA_AUTH_JWT_SECRET": "isolated-test-jwt-secret-with-enough-entropy",
        "BAHA_AUTH_JWT_ISSUER": "isolated-test-issuer",
        "BAHA_AUTH_JWT_AUDIENCE": "isolated-test-audience",
        "LLM_ENCRYPTION_MASTER_KEY": "isolated-test-encryption-key-with-enough-entropy",
    })
    if seed_dir is not None:
        env["PRJ069_BOOTSTRAP_SOURCE_DIR"] = str(seed_dir)
    else:
        env.pop("PRJ069_BOOTSTRAP_SOURCE_DIR", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_http_owner_cookie_requires_explicit_opt_in_and_http_origin(tmp_path):
    result = _run_bootstrap(
        tmp_path,
        mode="fresh",
        seed_dir=None,
        allowed_origins="http://studio.lan:3069",
        cookie_secure="false",
    )

    assert result.returncode == 0, result.stderr


def test_insecure_cookie_is_rejected_for_https_origin(tmp_path):
    result = _run_bootstrap(
        tmp_path,
        mode="fresh",
        seed_dir=None,
        allowed_origins="https://studio.example.test",
        cookie_secure="false",
    )

    assert result.returncode != 0
    assert "AUTH_COOKIE_SECURE" in result.stderr


def test_allowed_origins_reject_non_origin_path(tmp_path):
    result = _run_bootstrap(
        tmp_path,
        mode="fresh",
        seed_dir=None,
        allowed_origins="https://studio.example.test/studio",
    )

    assert result.returncode != 0
    assert "AUTH_ALLOWED_ORIGINS" in result.stderr


def test_allowed_origins_reject_origin_path_slash(tmp_path):
    result = _run_bootstrap(
        tmp_path,
        mode="fresh",
        seed_dir=None,
        allowed_origins="https://studio.example.test/",
    )

    assert result.returncode != 0
    assert "AUTH_ALLOWED_ORIGINS" in result.stderr


def test_copy_bootstrap_preserves_existing_databases_and_media_idempotently(tmp_path):
    seed_dir = tmp_path / "seed"
    _create_seed(seed_dir)
    source_before = {
        path.relative_to(seed_dir): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in seed_dir.rglob("*") if path.is_file()
    }

    first = _run_bootstrap(tmp_path, mode="copy", seed_dir=seed_dir)

    assert first.returncode == 0, first.stderr
    data_dir = tmp_path / "data"
    for name in DATABASES:
        assert not Path(f"{data_dir / name}-wal").exists()
        assert not Path(f"{data_dir / name}-shm").exists()
        with sqlite3.connect(data_dir / name) as db:
            assert db.execute("SELECT value FROM preserved_records").fetchone() == (name,)
    assert (data_dir / "media_assets" / "existing.bin").read_bytes() == b"existing media bytes"
    assert source_before == {
        path.relative_to(seed_dir): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in seed_dir.rglob("*") if path.is_file()
    }

    with sqlite3.connect(data_dir / DATABASES[0]) as db:
        db.execute("UPDATE preserved_records SET value = 'newer target data'")

    second = _run_bootstrap(tmp_path, mode="copy", seed_dir=seed_dir)

    assert second.returncode == 0, second.stderr
    with sqlite3.connect(data_dir / DATABASES[0]) as db:
        assert db.execute("SELECT value FROM preserved_records").fetchone() == ("newer target data",)


def test_copy_bootstrap_requires_an_explicit_source_directory(tmp_path):
    result = _run_bootstrap(tmp_path, mode="copy", seed_dir=None)

    assert result.returncode != 0
    assert "PRJ069_BOOTSTRAP_SOURCE_DIR" in result.stderr
    assert list((tmp_path / "data").iterdir()) == []


def test_adopt_bootstrap_preserves_and_backups_mounted_databases_and_media(tmp_path):
    data_dir = tmp_path / "data"
    _create_seed(data_dir)

    first = _run_bootstrap(tmp_path, mode="adopt", seed_dir=None)

    assert first.returncode == 0, first.stderr
    for name in DATABASES:
        with sqlite3.connect(data_dir / name) as db:
            assert db.execute("SELECT value FROM preserved_records").fetchone() == (name,)
    assert (data_dir / "media_assets" / "existing.bin").read_bytes() == b"existing media bytes"

    backups = list(data_dir.glob(".prj069-bootstrap-backup-*"))
    assert len(backups) == 1
    for name in DATABASES:
        with sqlite3.connect(backups[0] / name) as db:
            assert db.execute("SELECT value FROM preserved_records").fetchone() == (name,)
    assert (backups[0] / "media_assets" / "existing.bin").read_bytes() == b"existing media bytes"

    with sqlite3.connect(data_dir / DATABASES[0]) as db:
        db.execute("UPDATE preserved_records SET value = 'newer target data'")

    second = _run_bootstrap(tmp_path, mode="adopt", seed_dir=None)

    assert second.returncode == 0, second.stderr
    with sqlite3.connect(data_dir / DATABASES[0]) as db:
        assert db.execute("SELECT value FROM preserved_records").fetchone() == ("newer target data",)
    assert len(list(data_dir.glob(".prj069-bootstrap-backup-*"))) == 1


def test_adopt_bootstrap_refuses_an_empty_mount(tmp_path):
    result = _run_bootstrap(tmp_path, mode="adopt", seed_dir=None)

    assert result.returncode != 0
    assert "adopt" in result.stderr
    data_dir = tmp_path / "data"
    assert list(data_dir.iterdir()) == []


def test_adopt_bootstrap_refuses_partial_mount_without_creating_missing_data(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    original = data_dir / DATABASES[0]
    original.write_bytes(b"existing partial NAS data")

    result = _run_bootstrap(tmp_path, mode="adopt", seed_dir=None)

    assert result.returncode != 0
    assert original.read_bytes() == b"existing partial NAS data"
    assert list(data_dir.iterdir()) == [original]


def test_adopt_preserves_existing_password_credential_and_emits_no_secrets(tmp_path):
    assert _run_bootstrap(tmp_path, mode="fresh", seed_dir=None).returncode == 0
    data_dir = tmp_path / "data"
    with sqlite3.connect(data_dir / DATABASES[1]) as db:
        original_credential = db.execute("SELECT user_id, password_hash FROM local_password_credentials").fetchone()
    (data_dir / ".prj069-bootstrap.json").unlink()

    result = _run_bootstrap(
        tmp_path, mode="adopt", seed_dir=None, owner_password="different-test-only-owner-password"
    )

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(data_dir / DATABASES[1]) as db:
        assert db.execute("SELECT user_id, password_hash FROM local_password_credentials").fetchone() == original_credential
    public_output = result.stdout + result.stderr + (data_dir / ".prj069-bootstrap.json").read_text()
    for secret in (
        "test-only-owner-password", "different-test-only-owner-password", original_credential[1],
        "isolated-test-jwt-secret-with-enough-entropy", "isolated-test-encryption-key-with-enough-entropy",
    ):
        assert secret not in public_output


def test_copy_corrupt_database_leaves_source_and_empty_target_unchanged(tmp_path):
    source = tmp_path / "seed"
    _create_seed(source)
    corrupt_database = source / DATABASES[1]
    corrupt_database.write_bytes(b"not a SQLite database")
    source_before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}

    result = _run_bootstrap(tmp_path, mode="copy", seed_dir=source)

    assert result.returncode != 0
    assert list((tmp_path / "data").iterdir()) == []
    assert source_before == {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    assert "test-only-owner-password" not in result.stdout + result.stderr


def test_bootstrap_refuses_unmarked_existing_target_without_overwriting(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    existing = data_dir / DATABASES[0]
    existing.write_bytes(b"do not overwrite")

    result = _run_bootstrap(tmp_path, mode="fresh", seed_dir=None)

    assert result.returncode != 0
    assert existing.read_bytes() == b"do not overwrite"


def test_fresh_bootstrap_provisions_isolated_databases_and_is_idempotent(tmp_path):
    first = _run_bootstrap(tmp_path, mode="fresh", seed_dir=None)

    assert first.returncode == 0, first.stderr
    data_dir = tmp_path / "data"
    assert all((data_dir / name).is_file() for name in DATABASES)
    assert (data_dir / "media_assets").is_dir()

    with sqlite3.connect(data_dir / DATABASES[0]) as db:
        db.execute("CREATE TABLE bootstrap_preservation_check (value TEXT NOT NULL)")
        db.execute("INSERT INTO bootstrap_preservation_check VALUES ('keep me')")
    with sqlite3.connect(data_dir / DATABASES[1]) as db:
        email, user_id = db.execute(
            "SELECT email, id FROM global_users WHERE email = 'owner@example.test'"
        ).fetchone()
        workspace_id = db.execute(
            "SELECT id FROM workspaces WHERE id = ?", (str(uuid.uuid5(uuid.NAMESPACE_URL, str(tmp_path))),)
        ).fetchone()[0]
        assert email == "owner@example.test"
        assert db.execute(
            "SELECT password_hash FROM local_password_credentials WHERE user_id = ?", (user_id,)
        ).fetchone()[0] != "test-only-owner-password"
        assert db.execute(
            """SELECT count(*) FROM role_assignments ra
               JOIN roles r ON r.id = ra.role_id
               WHERE ra.workspace_id = ? AND ra.membership_id IN
                   (SELECT id FROM memberships WHERE workspace_id = ? AND user_id = ?)
                 AND ra.scope_type = 'WORKSPACE' AND ra.scope_id = ?
                 AND ra.status = 'ACTIVE' AND r.code = 'WORKSPACE_OWNER'""",
            (workspace_id, workspace_id, user_id, workspace_id),
        ).fetchone()[0] == 1
    marker_text = (data_dir / ".prj069-bootstrap.json").read_text(encoding="utf-8")
    assert "test-only-owner-password" not in marker_text
    assert "owner@example.test" not in marker_text
    assert "isolated-test-jwt-secret" not in marker_text

    second = _run_bootstrap(tmp_path, mode="fresh", seed_dir=None)

    assert second.returncode == 0, second.stderr
    with sqlite3.connect(data_dir / DATABASES[0]) as db:
        assert db.execute("SELECT value FROM bootstrap_preservation_check").fetchone() == ("keep me",)


def test_changing_allowed_origins_does_not_block_rerun(tmp_path):
    assert _run_bootstrap(tmp_path, mode="fresh", seed_dir=None).returncode == 0

    result = _run_bootstrap(
        tmp_path, mode="fresh", seed_dir=None,
        allowed_origins="https://studio.example.test,https://other.example.test",
    )

    assert result.returncode == 0, result.stderr
