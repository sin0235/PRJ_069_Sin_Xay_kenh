"""Sao chép DB nguồn vào vùng bền vững và khởi tạo workspace PRJ_069 một lần."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


FOUNDER_EMAIL = "phuctoan235@gmail.com"
PROJECT_CODE = "PRJ_069"
ROLE_CODE = "WORKSPACE_OWNER"
LLM_MODEL = "cx/gpt-6-luna"
DATA_FILES = ("sin_content_production.db", "baha_auth_production.db", "sin_dieu_phoi_dung.db")
# Vai trò mẫu toàn cục của Baha Auth; chế độ "sach" tự tạo thay vì sao chép từ DB cũ.
ROLE_TEMPLATES = (("WORKSPACE_OWNER", "Owner"), ("RESEARCHER", "Researcher"), ("STRATEGIST", "Strategist"), ("EXECUTIVE", "Executive"))


def bootstrap_mode() -> str:
    """"sach": tạo DB trống, không mang dữ liệu thử nghiệm cũ. "ke_thua": sao chép DB nguồn (mặc định, giữ tương thích)."""
    mode = os.getenv("PRJ069_BOOTSTRAP_MODE", "ke_thua").strip().casefold()
    if mode not in {"sach", "ke_thua"}:
        raise RuntimeError("PRJ069_BOOTSTRAP_MODE chỉ nhận 'sach' hoặc 'ke_thua'.")
    return mode


def workspace_id_for_project(project_code: str) -> str:
    if project_code != PROJECT_CODE:
        raise ValueError("Chỉ khởi tạo workspace PRJ_069.")
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "baha-group:PRJ_069:sin-xay-kenh:local-production"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_url(path: Path) -> str:
    resolved = path.resolve()
    return f"sqlite:///{resolved.as_posix()}" if resolved.drive else f"sqlite:////{resolved.as_posix().lstrip('/')}"


def _read_llm_key(path: Path) -> str:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if len(lines) == 1 and "=" not in lines[0]:
        key = lines[0]
    else:
        values = {}
        for line in lines:
            name, separator, value = line.partition("=")
            name = name.strip().casefold()
            if not separator or name not in {"base_url", "llm_base_url", "api-key", "api_key", "llm_api_key", "llm_enabled", "llm_model", "llm_encryption_master_key"} or name in values:
                raise RuntimeError("Tệp 9rt.env có định dạng không hợp lệ.")
            values[name] = value.strip()
        key = values.get("api-key") or values.get("api_key") or values.get("llm_api_key", "")
    if not key or any(char.isspace() for char in key):
        raise RuntimeError("API key trong 9rt.env không hợp lệ.")
    return key


def _snapshot_database(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"Thiếu DB nguồn: {source.name}.")
    source_db = sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True)
    target_db = sqlite3.connect(destination)
    try:
        source_db.backup(target_db)
        if target_db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError(f"DB nguồn không qua kiểm tra toàn vẹn: {source.name}.")
        target_db.execute("PRAGMA journal_mode=DELETE")
        target_db.commit()
    finally:
        target_db.close()
        source_db.close()


def _validate_environment() -> tuple[Path, Path, str, str, str, str, str]:
    if os.getenv("APP_ENV", "").casefold() != "production":
        raise RuntimeError("Chỉ cho phép khởi tạo với APP_ENV=production.")
    if os.getenv("TESTING", "0") != "0" or os.getenv("DEV_AUTH_BYPASS", "0") != "0":
        raise RuntimeError("TESTING và DEV_AUTH_BYPASS phải tắt.")
    if os.getenv("AUTH_MODE", "") != "local_password":
        raise RuntimeError("AUTH_MODE phải là local_password.")

    seed_dir = Path(os.getenv("PRJ069_BOOTSTRAP_SEED_DIR", "/seed")).resolve()
    data_dir = Path(os.getenv("PRJ069_BOOTSTRAP_DATA_DIR", "/data")).resolve()
    founder_email = os.getenv("FOUNDER_EMAIL", "").strip().casefold()
    workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
    password_hash = os.getenv("FOUNDER_PASSWORD_HASH", "").strip()
    secret = os.getenv("BAHA_AUTH_JWT_SECRET", "").strip()
    master_key = os.getenv("LLM_ENCRYPTION_MASTER_KEY", "").strip()
    if founder_email != FOUNDER_EMAIL or workspace_id != workspace_id_for_project(PROJECT_CODE):
        raise RuntimeError("Email Founder hoặc workspace PRJ_069 không khớp cấu hình đã duyệt.")
    if not password_hash.startswith("pbkdf2_sha256$600000$") or len(secret) < 40 or len(master_key) < 32:
        raise RuntimeError("Thiếu hash mật khẩu Founder hoặc khóa mã hóa production đủ mạnh.")
    if os.getenv("LLM_MODEL", "").strip() != LLM_MODEL:
        raise RuntimeError("LLM_MODEL phải là cx/gpt-6-luna.")
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    if not base_url.startswith("https://") or not base_url.endswith("/v1"):
        raise RuntimeError("LLM_BASE_URL phải là endpoint HTTPS /v1.")
    key_file = Path(os.getenv("LLM_API_KEY_FILE", "/run/secrets/9rt.env")).resolve()
    if not key_file.is_file():
        raise RuntimeError("Không tìm thấy tệp 9rt.env được mount cho bước khởi tạo.")
    api_key = _read_llm_key(key_file)
    if len(api_key) < 12:
        raise RuntimeError("API key trong 9rt.env không hợp lệ.")
    return seed_dir, data_dir, workspace_id, founder_email, password_hash, api_key, base_url


def _seed_databases(stage_dir: Path, workspace_id: str, founder_email: str, api_key: str, base_url: str) -> int:
    content_path = stage_dir / DATA_FILES[0]
    auth_path = stage_dir / DATA_FILES[1]
    os.environ["DATABASE_URL"] = _sqlite_url(content_path)
    os.environ["BAHA_AUTH_DATABASE_URL"] = _sqlite_url(auth_path)
    os.environ["BAHA_AUTH_APP_ENV"] = "production"
    os.environ["LLM_ENABLED"] = "false"
    os.environ["LLM_BASE_URL"] = base_url
    os.environ["LLM_MODEL"] = LLM_MODEL
    sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])]

    from src.migrations.runner import migration_up
    migration_up()

    from src.database import SessionLocal, engine as content_engine
    from src.models.entities import Membership as ContentMembership
    from src.models.entities import PlatformLLMConfig, User as ContentUser, Workspace as ContentWorkspace
    from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as auth_engine
    from baha_auth.src.models.entities import (
        ApprovalPolicy,
        GlobalUser,
        Membership,
        Role,
        RoleAssignment,
        Workspace as AuthWorkspace,
    )
    from baha_auth.src.policy.registry import registry
    from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event
    from src.modules.platform_config.crypto_vault import compute_key_fingerprint, encrypt_secret

    if bootstrap_mode() == "sach":
        # Schema Auth lấy từ mô hình hiện hành (không phụ thuộc DB cũ), cùng bốn vai trò mẫu.
        AuthBase.metadata.create_all(bind=auth_engine)
        with AuthSessionLocal() as role_db:
            for code, name in ROLE_TEMPLATES:
                if not role_db.query(Role).filter(Role.code == code, Role.workspace_id.is_(None)).first():
                    role_db.add(Role(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"baha-group:role-template:{code}")),
                        workspace_id=None, code=code, name=name,
                        is_template=True, is_custom=False, status="ACTIVE",
                    ))
            role_db.commit()

    for action in ("script.create", "script.approve_final", "ideas.create", "media.upload"):
        if registry.get_role_action_scope(ROLE_CODE, action) != "WORKSPACE":
            raise RuntimeError(f"Ma trận runtime thiếu quyền {action} trong WORKSPACE_OWNER.")

    content_db = SessionLocal()
    auth_db = AuthSessionLocal()
    fk_violations = 0
    try:
        if content_db.query(ContentWorkspace.id).filter(ContentWorkspace.id == workspace_id).first():
            raise RuntimeError("Workspace ID PRJ_069 đã tồn tại trong DB nguồn.")
        if auth_db.query(AuthWorkspace.id).filter(AuthWorkspace.id == workspace_id).first():
            raise RuntimeError("Workspace ID PRJ_069 đã tồn tại trong DB phân quyền nguồn.")

        user = auth_db.query(GlobalUser).filter(GlobalUser.email.ilike(founder_email)).first()
        if user and user.status != "ACTIVE":
            raise RuntimeError("Tài khoản Founder hiện có không ở trạng thái ACTIVE.")
        if not user:
            user = GlobalUser(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"baha-group:founder:{founder_email}")),
                email=founder_email,
                full_name="Founder PRJ_069",
                status="ACTIVE",
            )
            auth_db.add(user)
            auth_db.flush()

        auth_workspace = AuthWorkspace(
            id=workspace_id,
            name="SIN Creator OS PRJ_069",
            slug="prj069-sin-xay-kenh-local",
            type="ENTERPRISE",
            status="ACTIVE",
            created_by=user.id,
        )
        content_workspace = ContentWorkspace(
            id=workspace_id,
            name="SIN Creator OS PRJ_069",
            slug="prj069-sin-xay-kenh-local",
        )
        auth_db.add(auth_workspace)
        auth_db.flush()
        content_db.add(content_workspace)

        auth_membership = Membership(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"baha-group:{workspace_id}:{user.id}:membership")),
            workspace_id=workspace_id,
            user_id=user.id,
            status="ACTIVE",
            policy_revision=1,
        )
        auth_db.add(auth_membership)
        auth_db.flush()
        owner_role = auth_db.query(Role).filter(
            Role.code == ROLE_CODE,
            Role.status == "ACTIVE",
            Role.workspace_id.is_(None),
        ).first()
        if not owner_role:
            raise RuntimeError("Không tìm thấy role template WORKSPACE_OWNER đang hoạt động.")
        assignment = RoleAssignment(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"baha-group:{workspace_id}:{user.id}:{ROLE_CODE}")),
            workspace_id=workspace_id,
            membership_id=auth_membership.id,
            role_id=owner_role.id,
            scope_type="WORKSPACE",
            scope_id=workspace_id,
            granted_by=auth_membership.id,
            grant_reason="Founder đã yêu cầu cấp đầy đủ quyền trong workspace riêng PRJ_069.",
            status="ACTIVE",
            policy_version="1.0.0",
        )
        auth_db.add(assignment)
        policy = ApprovalPolicy(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"baha-group:{workspace_id}:founder-approval-policy")),
            workspace_id=workspace_id,
            version=1,
            stages_json=json.dumps([{"stage_key": "FINAL", "allowed_role": ROLE_CODE}], separators=(",", ":")),
            status="ACTIVE",
        )
        auth_db.add(policy)
        write_audit_event(
            auth_db,
            workspace_id=workspace_id,
            actor_id=user.id,
            actor_type="USER",
            action_key="roles.assign",
            decision="ALLOW",
            reason="FOUNDER_LOCAL_PRODUCTION_BOOTSTRAP",
            policy_version="1.0.0",
            resource_type="ROLE_ASSIGNMENT",
            resource_id=assignment.id,
            safe_metadata={"role_code": ROLE_CODE, "scope_type": "WORKSPACE"},
        )

        content_user = content_db.query(ContentUser).filter(ContentUser.email.ilike(founder_email)).first()
        if content_user and content_user.id != user.id:
            raise RuntimeError("Email Founder trong DB nội dung đã gắn với ID khác; dừng để đối soát.")
        if not content_user:
            content_user = ContentUser(id=user.id, email=founder_email, full_name=user.full_name, hashed_password=None)
            content_db.add(content_user)
            content_db.flush()
        content_membership = content_db.query(ContentMembership).filter(
            ContentMembership.workspace_id == workspace_id,
            ContentMembership.user_id == user.id,
        ).first()
        if not content_membership:
            content_db.add(ContentMembership(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"sin-content:{workspace_id}:{user.id}:membership")),
                workspace_id=workspace_id,
                user_id=user.id,
                role="owner",
            ))

        llm_config = content_db.query(PlatformLLMConfig).filter(
            PlatformLLMConfig.id == "default_platform_llm_config"
        ).first()
        if not llm_config:
            llm_config = PlatformLLMConfig(id="default_platform_llm_config")
            content_db.add(llm_config)
        llm_config.is_enabled = True
        llm_config.base_url = base_url
        llm_config.model = LLM_MODEL
        llm_config.api_key_ciphertext = encrypt_secret(api_key)
        llm_config.key_fingerprint = compute_key_fingerprint(api_key)
        llm_config.updated_by = "PRJ069_BOOTSTRAP"
        llm_config.updated_at = datetime.now(timezone.utc)
        content_db.commit()
        auth_db.commit()

        from src.modules.platform_config.crypto_vault import decrypt_secret

        if decrypt_secret(llm_config.api_key_ciphertext) != api_key:
            raise RuntimeError("Không xác minh được khóa LLM đã mã hóa.")
        db = sqlite3.connect(content_path)
        try:
            fk_violations = len(db.execute("PRAGMA foreign_key_check").fetchall())
        finally:
            db.close()
    except Exception:
        content_db.rollback()
        auth_db.rollback()
        raise
    finally:
        content_db.close()
        auth_db.close()
        content_engine.dispose()
        auth_engine.dispose()
    return fk_violations


def _set_runtime_permissions(path: Path) -> None:
    if os.name == "nt":
        return
    os.chown(path, 10001, 10001)
    os.chmod(path, 0o750 if path.is_dir() else 0o640)


def _prepare_runtime_directories(data_dir: Path, marker_path: Path) -> None:
    media_dir = data_dir / "media_assets"
    nle_dir = data_dir / "nle_bundles"
    cache_dir = data_dir / "cache"
    media_dir.mkdir(exist_ok=True)
    nle_dir.mkdir(exist_ok=True)
    cache_dir.mkdir(exist_ok=True)  # Bộ nhớ đệm model TTS (Hugging Face), tránh tải lại sau mỗi lần dựng container.
    for path in (data_dir, *(data_dir / name for name in DATA_FILES), marker_path, media_dir, nle_dir, cache_dir):
        _set_runtime_permissions(path)
    flow_dir = Path(os.getenv("PRJ069_FLOW_PROFILE_DIR", "/flow_profiles"))
    if flow_dir.is_dir():
        _set_runtime_permissions(flow_dir)
        if os.name != "nt":
            os.chmod(flow_dir, 0o700)


def main() -> None:
    seed_dir, data_dir, workspace_id, founder_email, password_hash, api_key, base_url = _validate_environment()
    mode = bootstrap_mode()
    source_files = {} if mode == "sach" else {
        "sin_content_offline.db": seed_dir / "sin_content_offline.db",
        "baha_auth_live.db": seed_dir / "baha_auth_live.db",
    }
    source_hashes = {name: _sha256(path) for name, path in source_files.items()}
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    marker_path = data_dir / ".prj069-production.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    expected = {
        "project_code": PROJECT_CODE,
        "workspace_id": workspace_id,
        "founder_email": founder_email,
        "role_code": ROLE_CODE,
        "llm_model": LLM_MODEL,
        "source_sha256": source_hashes,
        "llm_key_sha256": key_hash,
    }
    if mode == "sach":
        expected["mode"] = mode

    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if any(marker.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Dữ liệu đã khởi tạo với cấu hình khác; không ghi đè hoặc tự di chuyển.")
        if not all((data_dir / name).is_file() for name in DATA_FILES):
            raise RuntimeError("Marker tồn tại nhưng thiếu một DB bền vững; dừng để phục hồi.")
        _prepare_runtime_directories(data_dir, marker_path)
        print("bootstrap=already_initialized workspace_scope=PRJ_069 llm_model=cx/gpt-6-luna")
        return

    if any((data_dir / name).exists() for name in DATA_FILES):
        raise RuntimeError("Đã có DB trong vùng dữ liệu nhưng thiếu marker; không ghi đè.")
    if mode == "ke_thua" and not all(path.is_file() for path in source_files.values()):
        raise RuntimeError("Thiếu một trong hai DB nguồn đã kiểm kê.")

    stage_dir = Path(tempfile.mkdtemp(prefix=".prj069-init-", dir=data_dir))
    try:
        if mode == "ke_thua":
            _snapshot_database(source_files["sin_content_offline.db"], stage_dir / DATA_FILES[0])
            _snapshot_database(source_files["baha_auth_live.db"], stage_dir / DATA_FILES[1])
        else:
            for name in DATA_FILES[:2]:
                sqlite3.connect(stage_dir / name).close()
        with sqlite3.connect(stage_dir / DATA_FILES[2]):
            pass
        fk_violations = _seed_databases(stage_dir, workspace_id, founder_email, api_key, base_url)
        stage_urls = {
            "DATABASE_URL": _sqlite_url(stage_dir / DATA_FILES[0]),
            "BAHA_AUTH_DATABASE_URL": _sqlite_url(stage_dir / DATA_FILES[1]),
        }
        for name, path in zip(DATA_FILES, (stage_dir / DATA_FILES[0], stage_dir / DATA_FILES[1], stage_dir / DATA_FILES[2])):
            db = sqlite3.connect(path)
            try:
                if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError(f"DB khởi tạo không qua integrity_check: {name}.")
                db.execute("PRAGMA journal_mode=DELETE")
            finally:
                db.close()
            os.replace(path, data_dir / name)
        marker = {
            **expected,
            "content_fk_violations_preserved": fk_violations,
            "initialized_at": datetime.now(timezone.utc).isoformat(),
            "password_hash_configured": bool(password_hash),
        }
        marker_tmp = data_dir / ".prj069-production.json.tmp"
        marker_tmp.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(marker_tmp, marker_path)
        _prepare_runtime_directories(data_dir, marker_path)
        print(f"bootstrap=initialized workspace_scope=PRJ_069 content_fk_violations_preserved={fk_violations} llm_model={LLM_MODEL}")
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
