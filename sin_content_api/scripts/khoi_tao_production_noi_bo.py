#!/usr/bin/env python3
"""Provision or safely copy the production SQLite stores for PRJ_069."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


DATABASES = (
    "sin_content_production.db",
    "baha_auth_production.db",
    "sin_dieu_phoi_dung.db",
)
MEDIA_DIRECTORY = "media_assets"
MARKER_NAME = ".prj069-bootstrap.json"
MARKER_VERSION = 1
SCRIPT_PATH = Path(__file__).resolve()
api_root_candidates = (
    SCRIPT_PATH.parent.parent,
    SCRIPT_PATH.parent.parent / "sin_content_api",
)
API_ROOT = next((candidate for candidate in api_root_candidates if (candidate / "src").is_dir()), api_root_candidates[0])
PROJECT_ROOT = API_ROOT.parent
for import_root in (str(PROJECT_ROOT), str(API_ROOT)):
    if import_root not in sys.path:
        sys.path.insert(0, import_root)


class BootstrapError(RuntimeError):
    """A safe, actionable bootstrap error that contains no credential values."""


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BootstrapError(f"Thiếu biến môi trường bắt buộc: {name}.")
    return value


def _read_owner_password() -> str:
    path = Path(_required("AUTH_OWNER_PASSWORD_FILE"))
    try:
        if path.is_symlink() or not path.is_file():
            raise BootstrapError("AUTH_OWNER_PASSWORD_FILE phải trỏ tới tệp thường.")
        raw = path.read_bytes()
        password = raw.decode("utf-8")
    except BootstrapError:
        raise
    except (OSError, UnicodeDecodeError) as exc:
        raise BootstrapError("Không thể đọc AUTH_OWNER_PASSWORD_FILE.") from exc

    if password.endswith("\r\n"):
        password = password[:-2]
    elif password.endswith(("\n", "\r")):
        password = password[:-1]
    if "\n" in password or "\r" in password or not 12 <= len(password) <= 1024:
        raise BootstrapError("Mật khẩu owner phải là một dòng UTF-8 dài từ 12 đến 1024 ký tự.")
    return password


def _validate_environment() -> dict[str, str | set[str]]:
    if _required("APP_ENV").casefold() != "production":
        raise BootstrapError("Bootstrap chỉ chạy với APP_ENV=production.")
    for name in ("TESTING", "DEV_AUTH_BYPASS"):
        if os.environ.get(name, "0").strip().casefold() not in {"0", "false", "no", "off", ""}:
            raise BootstrapError(f"Bootstrap production từ chối {name} đang bật.")

    owner_email = _required("AUTH_OWNER_EMAIL").casefold()
    if "@" not in owner_email or any(char.isspace() for char in owner_email):
        raise BootstrapError("AUTH_OWNER_EMAIL không hợp lệ.")
    workspace_id = _required("SIN_WORKSPACE_ID")
    if len(workspace_id) > 36 or not all(char.isalnum() or char in "_-" for char in workspace_id):
        raise BootstrapError("SIN_WORKSPACE_ID chỉ nhận tối đa 36 ký tự chữ, số, gạch dưới hoặc gạch ngang.")
    workspace_name = _required("SIN_WORKSPACE_NAME")
    if len(workspace_name) > 255:
        raise BootstrapError("SIN_WORKSPACE_NAME không được vượt quá 255 ký tự.")

    origins_raw = _required("AUTH_ALLOWED_ORIGINS")
    origins: set[str] = set()
    for entry in origins_raw.split(","):
        origin = entry.strip()
        parsed = urlparse(origin)
        try:
            parsed.port
        except ValueError as exc:
            raise BootstrapError("AUTH_ALLOWED_ORIGINS chứa cổng không hợp lệ.") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise BootstrapError("AUTH_ALLOWED_ORIGINS phải là danh sách origin HTTP(S) hợp lệ.")
        origins.add(f"{parsed.scheme.lower()}://{parsed.netloc.lower()}")
    if not origins:
        raise BootstrapError("AUTH_ALLOWED_ORIGINS không được để trống.")

    jwt_secret = _required("BAHA_AUTH_JWT_SECRET")
    if len(jwt_secret.encode("utf-8")) < 32 or jwt_secret == "sin-dev-secret-do-not-use-in-production":
        raise BootstrapError("BAHA_AUTH_JWT_SECRET phải có ít nhất 32 byte và không dùng khóa phát triển.")
    _required("BAHA_AUTH_JWT_ISSUER")
    _required("BAHA_AUTH_JWT_AUDIENCE")
    encryption_key = _required("LLM_ENCRYPTION_MASTER_KEY")
    if len(encryption_key.encode("utf-8")) < 32:
        raise BootstrapError("LLM_ENCRYPTION_MASTER_KEY phải có ít nhất 32 byte.")
    if hmac.compare_digest(jwt_secret, encryption_key):
        raise BootstrapError("LLM_ENCRYPTION_MASTER_KEY phải độc lập với BAHA_AUTH_JWT_SECRET.")
    cookie_secure = os.environ.get("AUTH_COOKIE_SECURE", "true").strip().casefold()
    if cookie_secure not in {"true", "false"}:
        raise BootstrapError("AUTH_COOKIE_SECURE chỉ nhận true hoặc false.")
    if cookie_secure == "false" and any(origin.startswith("https://") for origin in origins):
        raise BootstrapError("AUTH_COOKIE_SECURE=false chỉ được phép khi mọi AUTH_ALLOWED_ORIGINS dùng HTTP.")
    password = _read_owner_password()

    return {
        "owner_email": owner_email,
        "owner_password": password,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "origins": origins,
    }


def _runtime_config(target: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{(target / DATABASES[0]).as_posix()}"
    os.environ["BAHA_AUTH_DATABASE_URL"] = f"sqlite:///{(target / DATABASES[1]).as_posix()}"
    os.environ["SIN_DUNG_DB_PATH"] = str(target / DATABASES[2])
    os.environ["MEDIA_ROOT_DIR"] = str(target / MEDIA_DIRECTORY)


def _source_files(source: Path) -> tuple[Path, Path, Path, Path]:
    if source.is_symlink() or not source.is_dir():
        raise BootstrapError("PRJ069_BOOTSTRAP_SOURCE_DIR phải là thư mục dữ liệu có thật.")
    paths = tuple(source / name for name in DATABASES) + (source / MEDIA_DIRECTORY,)
    for path in paths:
        if path.is_symlink() or not path.exists():
            raise BootstrapError("Thư mục nguồn phải có đủ ba SQLite database và media_assets.")
    if any(not (source / name).is_file() for name in DATABASES):
        raise BootstrapError("Ba database nguồn phải là tệp thường.")
    if not (source / MEDIA_DIRECTORY).is_dir():
        raise BootstrapError("media_assets nguồn phải là thư mục.")
    for root, dirs, files in os.walk(source / MEDIA_DIRECTORY, followlinks=False):
        for name in dirs + files:
            if (Path(root) / name).is_symlink():
                raise BootstrapError("media_assets nguồn không được chứa symbolic link.")
    return paths  # type: ignore[return-value]


def _copy_sqlite_snapshot(source: Path, destination: Path) -> None:
    source_uri = source.resolve().as_uri() + "?mode=ro"
    try:
        with sqlite3.connect(source_uri, uri=True, timeout=30) as source_db:
            with sqlite3.connect(destination, timeout=30) as destination_db:
                source_db.backup(destination_db)
                result = destination_db.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise BootstrapError("Một database nguồn không vượt qua kiểm tra toàn vẹn SQLite.")
    except BootstrapError:
        raise
    except sqlite3.Error as exc:
        raise BootstrapError("Không thể tạo snapshot SQLite từ dữ liệu nguồn.") from exc


def _copy_existing_data(source: Path, stage: Path) -> None:
    source_content, source_auth, source_harness, source_media = _source_files(source)
    for item in (source_content, source_auth, source_harness):
        _copy_sqlite_snapshot(item, stage / item.name)
    shutil.copytree(source_media, stage / MEDIA_DIRECTORY, copy_function=shutil.copy2)


def _hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for name in DATABASES:
        path = root / name
        digest.update(b"file\0" + name.encode("utf-8") + b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    media_root = root / MEDIA_DIRECTORY
    for path in sorted(media_root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        if path.is_dir():
            digest.update(b"dir\0" + relative + b"\0")
        elif path.is_file():
            digest.update(b"file\0" + relative + b"\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def _config_fingerprint(config: dict[str, str | set[str]]) -> str:
    safe_fields = {
        "owner_email": config["owner_email"],
        "workspace_id": config["workspace_id"],
        "workspace_name": config["workspace_name"],
        "origins": sorted(config["origins"]),
    }
    encoded = json.dumps(safe_fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _ensure_owner(config: dict[str, str | set[str]]) -> None:
    from sqlalchemy import func

    from baha_auth.src.database import Base as AuthBase
    from baha_auth.src.database import SessionLocal as AuthSessionLocal, engine as AuthEngine
    from baha_auth.src.models import (
        GlobalUser,
        LocalPasswordCredential,
        Membership as AuthMembership,
        Role as AuthRole,
        RoleAssignment,
        Workspace as AuthWorkspace,
    )
    from baha_auth.src.services.local_password import create_password_credential_if_missing
    from src.database import SessionLocal
    from src.migrations.runner import migration_up
    from src.models.entities import Membership, User, Workspace
    from src.auth.mat_khau_noi_bo import hash_password
    from src.modules.dieu_phoi_dung.kho_luu_tru import KhoLuuTruDung

    migration_up()
    AuthBase.metadata.create_all(bind=AuthEngine)
    # Ensure the durable local orchestration store exists at the configured path.
    KhoLuuTruDung.lay_duong_dan_db()

    owner_email = str(config["owner_email"])
    workspace_id = str(config["workspace_id"])
    workspace_name = str(config["workspace_name"])
    password = str(config["owner_password"])

    with AuthSessionLocal() as auth_db, SessionLocal() as content_db:
        auth_user = auth_db.query(GlobalUser).filter(func.lower(GlobalUser.email) == owner_email).first()
        content_user = content_db.query(User).filter(func.lower(User.email) == owner_email).first()
        if auth_user and content_user and auth_user.id != content_user.id:
            raise BootstrapError("Owner email đang gắn với hai user ID khác nhau trong hai database.")

        user_id = (auth_user.id if auth_user else None) or (content_user.id if content_user else None) or str(uuid.uuid4())
        auth_id_collision = auth_db.get(GlobalUser, user_id)
        content_id_collision = content_db.get(User, user_id)
        if auth_id_collision and auth_id_collision.email.casefold() != owner_email:
            raise BootstrapError("User ID owner bị trùng với danh tính khác trong BAHA Auth.")
        if content_id_collision and content_id_collision.email.casefold() != owner_email:
            raise BootstrapError("User ID owner bị trùng với danh tính khác trong content database.")

        if auth_user is None:
            auth_user = GlobalUser(id=user_id, email=owner_email, status="ACTIVE")
            auth_db.add(auth_user)
            auth_db.flush()
        if auth_user.status != "ACTIVE":
            raise BootstrapError("Tài khoản owner trong BAHA Auth không ở trạng thái ACTIVE.")
        if content_user is None:
            content_user = User(id=user_id, email=owner_email)
            content_db.add(content_user)

        auth_workspace = auth_db.get(AuthWorkspace, workspace_id)
        if auth_workspace is None:
            auth_workspace = AuthWorkspace(
                id=workspace_id,
                name=workspace_name,
                slug=f"ws-{workspace_id.lower()}",
                status="ACTIVE",
                created_by=user_id,
            )
            auth_db.add(auth_workspace)
            auth_db.flush()
        if auth_workspace.status != "ACTIVE":
            raise BootstrapError("Workspace cấu hình trong BAHA Auth không ở trạng thái ACTIVE.")

        content_workspace = content_db.get(Workspace, workspace_id)
        if content_workspace is None:
            content_db.add(Workspace(
                id=workspace_id,
                name=workspace_name,
                slug=f"ws-{workspace_id.lower()}",
            ))
            content_db.flush()

        auth_membership = auth_db.query(AuthMembership).filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
        ).first()
        if auth_membership is None:
            auth_membership = AuthMembership(
                workspace_id=workspace_id,
                user_id=user_id,
                status="ACTIVE",
            )
            auth_db.add(auth_membership)
            auth_db.flush()
        if auth_membership.status != "ACTIVE":
            raise BootstrapError("Membership owner trong BAHA Auth không ở trạng thái ACTIVE.")

        role = auth_db.query(AuthRole).filter_by(code="WORKSPACE_OWNER").first()
        if role is None:
            role = AuthRole(
                code="WORKSPACE_OWNER",
                name="Workspace Owner",
                workspace_id=None,
                is_template=True,
                status="ACTIVE",
            )
            auth_db.add(role)
            auth_db.flush()
        if role.workspace_id is not None or not role.is_template or role.status != "ACTIVE":
            raise BootstrapError("Role template WORKSPACE_OWNER hiện có không hợp lệ.")

        owner_assignments = [
            assignment
            for assignment in auth_db.query(RoleAssignment).filter_by(
                workspace_id=workspace_id,
                membership_id=auth_membership.id,
            ).all()
            if assignment.role and assignment.role.code == "WORKSPACE_OWNER"
        ]
        if len(owner_assignments) > 1:
            raise BootstrapError("Owner có nhiều hơn một assignment WORKSPACE_OWNER; cần kiểm tra thủ công.")
        if owner_assignments:
            assignment = owner_assignments[0]
            now = datetime.now(timezone.utc)
            valid_from = assignment.valid_from
            valid_until = assignment.valid_until
            if valid_from and valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=timezone.utc)
            if valid_until and valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            if (
                assignment.status != "ACTIVE"
                or assignment.scope_type != "WORKSPACE"
                or assignment.scope_id != workspace_id
                or (valid_from is not None and valid_from > now)
                or (valid_until is not None and valid_until <= now)
            ):
                raise BootstrapError("Owner có assignment WORKSPACE_OWNER không còn hiệu lực; cần kiểm tra thủ công.")
        else:
            auth_db.add(RoleAssignment(
                workspace_id=workspace_id,
                membership_id=auth_membership.id,
                role_id=role.id,
                scope_type="WORKSPACE",
                scope_id=workspace_id,
                status="ACTIVE",
                grant_reason="Configured production owner bootstrap",
            ))

        content_membership = content_db.query(Membership).filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
        ).first()
        if content_membership is None:
            content_db.add(Membership(workspace_id=workspace_id, user_id=user_id, role="owner"))
        elif content_membership.role.casefold() != "owner":
            raise BootstrapError("Membership owner hiện có trong content database không phải owner; không tự nâng quyền.")

        credential = auth_db.get(LocalPasswordCredential, user_id)
        if credential is None:
            create_password_credential_if_missing(auth_db, user_id, hash_password(password))

        auth_db.commit()
        content_db.commit()


def _initialize_staged_data(stage: Path, config: dict[str, str | set[str]]) -> None:
    _runtime_config(stage)
    _ensure_owner(config)
    _close_staged_databases(stage)


def _close_staged_databases(stage: Path) -> None:
    from baha_auth.src.database import engine as auth_engine
    from src.database import engine as content_engine

    content_engine.dispose()
    auth_engine.dispose()
    for name in DATABASES:
        database = stage / name
        try:
            connection = sqlite3.connect(database, timeout=30)
            try:
                checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                if checkpoint and checkpoint[0] != 0:
                    raise BootstrapError(f"Database {name} vẫn đang được sử dụng; không thể chốt WAL an toàn.")
            finally:
                connection.close()
        except BootstrapError:
            raise
        except sqlite3.Error as exc:
            raise BootstrapError(f"Không thể chốt WAL an toàn cho database {name}.") from exc

        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{database}{suffix}")
            if sidecar.exists():
                if sidecar.is_symlink() or not sidecar.is_file():
                    raise BootstrapError(f"SQLite sidecar không hợp lệ cho database {name}.")
                sidecar.unlink()


def _publish_staged_data(stage: Path, target: Path, *, adopt: bool) -> Path | None:
    names = (*DATABASES, MEDIA_DIRECTORY, MARKER_NAME)
    backup: Path | None = None
    moved_original: list[str] = []
    moved_new: list[str] = []

    if adopt:
        existing = [name for name in names if (target / name).exists()]
        if existing:
            backup = target / f".prj069-bootstrap-backup-{uuid.uuid4().hex}"
            backup.mkdir()

    try:
        if backup is not None:
            for name in names:
                original = target / name
                if original.exists():
                    os.replace(original, backup / name)
                    moved_original.append(name)

        for name in names:
            staged = stage / name
            if staged.exists():
                os.replace(staged, target / name)
                moved_new.append(name)
        stage.rmdir()
    except Exception:
        for name in reversed(moved_new):
            published = target / name
            if published.exists():
                os.replace(published, stage / name)
        if backup is not None:
            for name in reversed(moved_original):
                saved = backup / name
                if saved.exists():
                    os.replace(saved, target / name)
            if not any(backup.iterdir()):
                backup.rmdir()
        raise

    return backup


def _read_existing_marker(target: Path, mode: str, fingerprint: str) -> bool:
    if not target.exists():
        return False
    if target.is_symlink() or not target.is_dir():
        raise BootstrapError("PRJ069_BOOTSTRAP_DATA_DIR phải là thư mục thường.")
    entries = list(target.iterdir())
    marker_path = target / MARKER_NAME
    if not entries:
        return False
    if marker_path.is_symlink():
        raise BootstrapError("Bootstrap marker hiện có không hợp lệ; từ chối ghi đè.")
    if not marker_path.is_file():
        if mode == "adopt":
            return False
        raise BootstrapError("Data directory đã có dữ liệu nhưng thiếu marker; từ chối ghi đè.")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BootstrapError("Bootstrap marker hiện có không hợp lệ; từ chối ghi đè.") from exc
    if (
        marker.get("version") != MARKER_VERSION
        or marker.get("mode") != mode
        or marker.get("config_sha256") != fingerprint
    ):
        raise BootstrapError("Bootstrap marker không khớp mode hoặc cấu hình; từ chối thay đổi dữ liệu.")
    for name in DATABASES:
        path = target / name
        if path.is_symlink() or not path.is_file():
            raise BootstrapError("Bootstrap marker tồn tại nhưng thiếu database; cần khôi phục thủ công.")
    media = target / MEDIA_DIRECTORY
    if media.is_symlink() or not media.is_dir():
        raise BootstrapError("Bootstrap marker tồn tại nhưng thiếu media_assets; cần khôi phục thủ công.")
    return True


def run() -> int:
    mode = _required("PRJ069_BOOTSTRAP_MODE").casefold()
    if mode not in {"fresh", "adopt", "copy"}:
        raise BootstrapError("PRJ069_BOOTSTRAP_MODE chỉ nhận fresh, adopt hoặc copy.")
    target = Path(_required("PRJ069_BOOTSTRAP_DATA_DIR")).expanduser().resolve()
    if target == Path("/") or target == target.parent:
        raise BootstrapError("PRJ069_BOOTSTRAP_DATA_DIR không thể là thư mục gốc.")
    config = _validate_environment()
    fingerprint = _config_fingerprint(config)
    if _read_existing_marker(target, mode, fingerprint):
        print("Bootstrap đã hoàn tất; dữ liệu hiện có được giữ nguyên.")
        return 0

    source: Path | None = None
    if mode == "copy":
        source = Path(_required("PRJ069_BOOTSTRAP_SOURCE_DIR")).expanduser().resolve()
        if source == target or source in target.parents or target in source.parents:
            raise BootstrapError("Thư mục nguồn và đích phải độc lập.")
        _source_files(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    target_entries = list(target.iterdir())
    if mode == "adopt" and not target_entries:
        raise BootstrapError("adopt yêu cầu dữ liệu NAS hiện có; dùng fresh chỉ cho volume mới được xác nhận.")
    if mode != "adopt" and target_entries:
        raise BootstrapError("Data directory không rỗng và chưa được provision bởi script này; từ chối ghi đè.")
    if mode == "adopt":
        _source_files(target)

    stage = Path(tempfile.mkdtemp(prefix=".prj069-bootstrap-", dir=target))
    try:
        if mode == "copy":
            assert source is not None
            _copy_existing_data(source, stage)
        elif mode == "adopt":
            _copy_existing_data(target, stage)
        else:
            (stage / MEDIA_DIRECTORY).mkdir()

        source_fingerprint = _hash_tree(stage) if mode in {"copy", "adopt"} else None
        _initialize_staged_data(stage, config)
        marker = {
            "version": MARKER_VERSION,
            "mode": mode,
            "config_sha256": fingerprint,
            "source_sha256": source_fingerprint,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        marker_path = stage / MARKER_NAME
        with marker_path.open("x", encoding="utf-8") as handle:
            json.dump(marker, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _publish_staged_data(stage, target, adopt=mode == "adopt")
    except BootstrapError:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(stage, ignore_errors=True)
        raise BootstrapError(f"Provisioning không hoàn tất ({type(exc).__name__}); dữ liệu nguồn được giữ nguyên.") from exc

    print("Bootstrap production hoàn tất; dữ liệu hiện có được bảo toàn.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except BootstrapError as exc:
        print(f"Bootstrap thất bại: {exc}", file=sys.stderr)
        raise SystemExit(2)
