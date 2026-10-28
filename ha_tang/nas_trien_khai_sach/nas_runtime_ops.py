#!/usr/bin/env python3
"""Fail-closed local Compose preflight, backup, restore, and image export."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPOSE = Path(__file__).with_name("compose.yaml")
DEFAULT_ENV = Path(__file__).with_name("deploy.env")
REQUIRED_ARCHIVES = ("data.tar", "profiles.tar")


class OpsError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_copy_file(source: Path, destination: Path, mode: int = 0o600) -> None:
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or not source.is_file():
        raise ValueError("secret source must be a regular file")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("destination already exists")
    temporary = destination.with_name(f".{destination.name}.partial-{uuid.uuid4().hex}")
    try:
        with source.open("rb") as reader, temporary.open("xb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(temporary, mode)
        os.link(temporary, destination, follow_symlinks=False)
        temporary.unlink()
        _fsync_directory(destination.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def validate_owner_password_file(path: Path) -> None:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("owner password secret must be a regular file")
    try:
        value = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("owner password secret must be UTF-8") from exc
    if value.endswith("\n"):
        value = value[:-1]
    if not value or "\n" in value or "\r" in value or "\x00" in value or not 12 <= len(value) <= 1024:
        raise ValueError("owner password secret must be one UTF-8 line of 12 to 1024 characters")


def create_manifest(backup_dir: Path, metadata: dict) -> dict:
    backup_dir = Path(backup_dir)
    payloads: dict[str, dict] = {}
    for path in sorted(backup_dir.rglob("*")):
        if path.name == "manifest.json":
            continue
        if path.is_symlink():
            raise ValueError("backup payload cannot contain symlinks")
        if path.is_file():
            payloads[path.relative_to(backup_dir).as_posix()] = {
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "files": payloads,
    }
    temporary = backup_dir / f".manifest.partial-{uuid.uuid4().hex}"
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, backup_dir / "manifest.json")
    _fsync_directory(backup_dir)
    return manifest


def verify_backup(backup_dir: Path) -> dict:
    backup_input = Path(backup_dir)
    if backup_input.is_symlink():
        raise ValueError("backup path cannot be a symlink")
    backup_dir = backup_input.resolve(strict=True)
    if not backup_dir.is_dir():
        raise ValueError("backup path must be a regular directory")
    try:
        manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("backup manifest is missing or invalid") from exc
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("backup manifest version is unsupported")
    listed: set[str] = set()
    for relative, record in manifest["files"].items():
        rel = PurePosixPath(relative)
        if rel.is_absolute() or not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
            raise ValueError("backup manifest contains an unsafe path")
        candidate = backup_dir / Path(*rel.parts)
        if candidate.is_symlink():
            raise ValueError("backup payload cannot be a symlink")
        path = candidate.resolve(strict=True)
        if not path.is_relative_to(backup_dir) or not path.is_file():
            raise ValueError("backup payload path is invalid")
        if path.stat().st_size != int(record["size_bytes"]) or sha256_file(path) != record["sha256"]:
            raise ValueError("backup checksum verification failed")
        listed.add(relative)
    actual: set[str] = set()
    for path in backup_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError("backup payload cannot contain symlinks")
        if path.is_file() and path.name != "manifest.json":
            actual.add(path.relative_to(backup_dir).as_posix())
    if actual != listed:
        raise ValueError("backup payload list does not match the manifest")
    return manifest


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _run_capture(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise OpsError("required local command could not be started") from exc


def _compose_prefix(args) -> list[str]:
    compose_file = Path(args.compose_file).resolve(strict=True)
    env_file = Path(args.env_file).resolve(strict=True)
    return [
        "docker", "compose",
        "--project-directory", str(compose_file.parent),
        "--env-file", str(env_file),
        "-f", str(compose_file),
    ]


def _compose_config(args) -> dict:
    result = _run_capture(_compose_prefix(args) + ["config", "--format", "json"])
    if result.returncode:
        raise OpsError(f"docker compose config failed (exit {result.returncode})")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise OpsError("docker compose config returned invalid JSON") from exc


def _validate_origin_list(value: str) -> int:
    origins = [origin.strip() for origin in value.split(",")]
    if not origins or any(not origin for origin in origins):
        raise OpsError("AUTH_ALLOWED_ORIGINS must contain comma-separated exact origins")
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise OpsError("AUTH_ALLOWED_ORIGINS must contain exact origins with no path")
    return len(origins)


def preflight(args) -> tuple[dict, dict]:
    config = _compose_config(args)
    services = config.get("services", {})
    if not {"init", "api", "flow-session-worker", "web", "gateway"}.issubset(services):
        raise OpsError("Compose is missing a required production service")
    api = services["api"].get("environment", {})
    init_env = services["init"].get("environment", {})
    worker = services["flow-session-worker"]
    required = (
        "AUTH_OWNER_EMAIL", "SIN_WORKSPACE_ID", "SIN_WORKSPACE_NAME", "AUTH_ALLOWED_ORIGINS",
        "BAHA_AUTH_JWT_SECRET", "BAHA_AUTH_JWT_ISSUER", "BAHA_AUTH_JWT_AUDIENCE",
        "LLM_ENCRYPTION_MASTER_KEY",
    )
    values = {key: str(init_env.get(key, "")) for key in required}
    missing = [key for key, value in values.items() if not value.strip()]
    if missing:
        raise OpsError("deployment environment is missing required values: " + ", ".join(missing))
    if api.get("APP_ENV") != "production" or api.get("TESTING") != "0" or api.get("DEV_AUTH_BYPASS") != "0":
        raise OpsError("API must use production mode with TESTING and DEV_AUTH_BYPASS disabled")
    if api.get("CONTENT_VIDEO_WORKER_ENABLED") != "0" or api.get("SYNTHETIC_DATA_ALLOWED") != "false":
        raise OpsError("production inline workers and synthetic data must be disabled")
    exact_api_values = {
        "DATABASE_URL": "sqlite:////data/sin_content_production.db",
        "BAHA_AUTH_DATABASE_URL": "sqlite:////data/baha_auth_production.db",
        "SIN_DUNG_DB_PATH": "/data/sin_dieu_phoi_dung.db",
        "MEDIA_ROOT_DIR": "/data/media_assets",
        "PRJ069_VIENU_HF_HOME": "/models/vieneu",
        "WORKER_HEARTBEAT_PATH": "/data/runtime/worker.json",
        "BROWSER_CHANNEL": "chromium",
        "FLOW_CONTROL_URL": "http://flow-session-worker:8090",
        "FLOW_DESKTOP_URL": "http://flow-session-worker:6080",
    }
    for key, expected in exact_api_values.items():
        if api.get(key) != expected:
            raise OpsError(f"API runtime setting {key} does not match the production contract")
    worker_env = worker.get("environment", {})
    if float(worker.get("cpus", 0)) != 2.0 or any(
        worker_env.get(name) != "2" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
    ):
        raise OpsError("Flow worker must use two CPUs and two native threads")
    if worker_env.get("FLOW_PROFILE_ROOT") != "/data/flow-profiles" or worker_env.get("WORKER_HEARTBEAT_PATH") != "/data/runtime/worker.json":
        raise OpsError("Flow worker persistent paths do not match the production contract")
    if worker_env.get("FLOW_DESKTOP_ALLOWED_ORIGINS") != values["AUTH_ALLOWED_ORIGINS"]:
        raise OpsError("Flow desktop origin allowlist differs from the API allowlist")
    expected_memory = {"api": 512, "flow-session-worker": 3584, "web": 512}
    for name, mebibytes in expected_memory.items():
        if int(services[name].get("mem_limit", 0)) != mebibytes * 1024 * 1024:
            raise OpsError(f"{name} memory limit does not match the production contract")
    if str(init_env.get("AUTH_COOKIE_SECURE", "true")).lower() not in {"true", "false"}:
        raise OpsError("AUTH_COOKIE_SECURE must be true or false")
    if services["web"].get("environment", {}).get("AUTH_COOKIE_SECURE") != str(init_env.get("AUTH_COOKIE_SECURE", "true")).lower():
        raise OpsError("web and API cookie security settings must match")
    try:
        import uuid as uuid_module
        uuid_module.UUID(values["SIN_WORKSPACE_ID"])
    except ValueError as exc:
        raise OpsError("SIN_WORKSPACE_ID must be a UUID") from exc
    if len(values["BAHA_AUTH_JWT_SECRET"].encode("utf-8")) < 32:
        raise OpsError("BAHA_AUTH_JWT_SECRET must contain at least 32 bytes")
    if len(values["LLM_ENCRYPTION_MASTER_KEY"].encode("utf-8")) < 32:
        raise OpsError("LLM_ENCRYPTION_MASTER_KEY must contain at least 32 bytes")
    origin_count = _validate_origin_list(values["AUTH_ALLOWED_ORIGINS"])
    if init_env.get("FLOW_DESKTOP_ALLOWED_ORIGINS") != values["AUTH_ALLOWED_ORIGINS"]:
        raise OpsError("FLOW_DESKTOP_ALLOWED_ORIGINS must exactly match AUTH_ALLOWED_ORIGINS")
    secret = config.get("secrets", {}).get("owner-password", {}).get("file")
    if not secret:
        raise OpsError("owner-password Compose secret source is missing")
    secret_path = Path(secret)
    validate_owner_password_file(secret_path)
    env_path = Path(args.env_file).resolve(strict=True)
    if stat.S_IMODE(env_path.stat().st_mode) & 0o077:
        raise OpsError("deployment env file must not be readable by group or other users")
    if "AUTH_OWNER_PASSWORD_FILE" not in init_env or "AUTH_OWNER_PASSWORD_FILE" in api:
        raise OpsError("owner password must be available to init only")
    if services["init"].get("user") != "0:0" or services["api"].get("user") != "10001:10001" or worker.get("user") != "10001:10001":
        raise OpsError("init and runtime service UIDs do not match the production contract")
    if services["api"].get("ports") or worker.get("ports"):
        raise OpsError("API and Flow worker must not publish host ports")
    api_networks = set(services["api"].get("networks", {}))
    worker_networks = set(worker.get("networks", {}))
    web_networks = set(services["web"].get("networks", {}))
    gateway_networks = set(services["gateway"].get("networks", {}))
    if (
        "api-worker" not in api_networks
        or "api-worker" not in worker_networks
        or "api-worker" in web_networks
        or "api-worker" in gateway_networks
        or "worker-egress" in api_networks
        or "worker-egress" in gateway_networks
    ):
        raise OpsError("Flow worker network must be reachable by API only and egress must remain internal to worker")
    if {str(port).split("/", 1)[0] for port in worker.get("expose", [])} != {"6080", "8090"}:
        raise OpsError("Flow worker must expose only internal VNC and control ports")
    volumes = config.get("volumes", {})
    volume_names = {key: value.get("name", key) for key, value in volumes.items()}
    for key in ("app-data", "flow-profiles", "models"):
        if key not in volume_names:
            raise OpsError("Compose persistent volume definition is missing")
    disk_path = Path(args.backup_dir).resolve().parent if getattr(args, "backup_dir", None) else ROOT
    while not disk_path.exists() and disk_path != disk_path.parent:
        disk_path = disk_path.parent
    free = shutil.disk_usage(disk_path).free
    summary = {
        "state": "READY",
        "project": config.get("name", "prj069-nas"),
        "allowed_origin_count": origin_count,
        "cookie_secure": str(init_env.get("AUTH_COOKIE_SECURE", "true")).lower(),
        "owner_password_secret_readable": True,
        "owner_password_secret_mode": oct(stat.S_IMODE(secret_path.stat().st_mode)),
        "runtime_uids": {"init": "0:0", "api": "10001:10001", "worker": "10001:10001"},
        "worker_cpus": 2.0,
        "volumes": volume_names,
        "free_bytes": free,
        "nas_live": "NOT_VERIFIED",
    }
    return config, summary


def _run_docker_checked(command: list[str], message: str) -> None:
    result = _run_capture(command)
    if result.returncode:
        raise OpsError(f"{message} (exit {result.returncode})")


_ARCHIVE_HELPER = (
    "import os,sys,tarfile; from pathlib import Path; "
    "source=Path('/source'); destination=Path('/backup')/sys.argv[1]; "
    "destination.parent.mkdir(parents=True,exist_ok=True); "
    "archive=tarfile.open(destination,'w'); archive.add(source,arcname='.',recursive=True); archive.close(); os.chmod(destination,0o644)"
)

_RESTORE_HELPER = r'''import json, os, posixpath, shutil, sys, tarfile, uuid
from pathlib import Path, PurePosixPath
archive_path=Path('/backup')/sys.argv[1]
archive_digest=sys.argv[2]
volume_kind=sys.argv[3]
target=Path('/target')
if any(target.iterdir()):
    raise SystemExit('RESTORE_TARGET_NOT_EMPTY')
stage=target/('.prj069-stage-'+uuid.uuid4().hex)
stage.mkdir(mode=0o700)
with tarfile.open(archive_path,'r') as archive:
    members=archive.getmembers()
    names=set()
    def safe_parts(raw):
        path=PurePosixPath(raw)
        if path.is_absolute() or any(part=='..' for part in path.parts):
            raise ValueError('unsafe archive path')
        return tuple(part for part in path.parts if part not in ('','.'))
    for member in members:
        parts=safe_parts(member.name)
        if not parts:
            continue
        key='/'.join(parts)
        if key in names or not (member.isdir() or member.isfile() or member.issym() or member.islnk()):
            raise ValueError('unsupported archive member')
        names.add(key)
        if member.issym():
            link=PurePosixPath(member.linkname)
            if link.is_absolute():
                raise ValueError('absolute symlink in archive')
            resolved=posixpath.normpath(posixpath.join(str(PurePosixPath(*parts).parent),member.linkname))
            if resolved=='..' or resolved.startswith('../'):
                raise ValueError('escaping symlink in archive')
    for member in sorted(members,key=lambda item:(len(safe_parts(item.name)),item.name)):
        parts=safe_parts(member.name)
        if not parts:
            continue
        destination=stage.joinpath(*parts)
        if member.isdir():
            destination.mkdir(parents=True,exist_ok=True)
            os.chmod(destination,member.mode & 0o777)
    for member in members:
        parts=safe_parts(member.name)
        if not parts or not member.isfile():
            continue
        destination=stage.joinpath(*parts)
        destination.parent.mkdir(parents=True,exist_ok=True)
        source=archive.extractfile(member)
        if source is None:
            raise ValueError('missing archive member content')
        with source,destination.open('xb') as output:
            shutil.copyfileobj(source,output,1024*1024)
        os.chmod(destination,member.mode & 0o777)
    for member in members:
        parts=safe_parts(member.name)
        if not parts or not member.islnk():
            continue
        link_parts=safe_parts(member.linkname)
        source=stage.joinpath(*link_parts)
        if not source.is_file():
            raise ValueError('invalid hardlink in archive')
        destination=stage.joinpath(*parts)
        destination.parent.mkdir(parents=True,exist_ok=True)
        os.link(source,destination)
    for member in members:
        parts=safe_parts(member.name)
        if not parts or not member.issym():
            continue
        destination=stage.joinpath(*parts)
        destination.parent.mkdir(parents=True,exist_ok=True)
        os.symlink(member.linkname,destination)
for child in list(stage.iterdir()):
    os.replace(child,target/child.name)
stage.rmdir()
for base,dirs,files in os.walk(target,topdown=True,followlinks=False):
    os.chown(base,10001,10001,follow_symlinks=False)
    for name in dirs+files:
        path=os.path.join(base,name)
        os.chown(path,10001,10001,follow_symlinks=False)
marker=target/'.prj069-restore-complete.json'
temporary=target/'.restore-marker.tmp'
temporary.write_text(json.dumps({'volume':volume_kind,'archive_sha256':archive_digest},sort_keys=True)+'\n')
os.chmod(temporary,0o644)
os.chown(temporary,10001,10001)
os.replace(temporary,marker)
'''


def _docker_run_volume_helper(image: str, volume: str, host_dir: Path, helper: str, *args: str) -> None:
    if not volume or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for char in volume):
        raise OpsError("Docker volume name is invalid")
    command = [
        "docker", "run", "--rm", "--network", "none", "--user", "0:0",
        "--mount", f"type=volume,src={volume},dst=/source,readonly",
        "--mount", f"type=bind,src={host_dir.resolve()},dst=/backup",
        image, "python", "-c", helper, *args,
    ]
    result = _run_capture(command)
    if result.returncode:
        raise OpsError(f"isolated Docker volume operation failed (exit {result.returncode})")


def _compose_running_services(args) -> list[str]:
    result = _run_capture(_compose_prefix(args) + ["ps", "--services", "--status", "running"])
    if result.returncode:
        raise OpsError("could not inspect running Compose services")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def backup(args) -> dict:
    config, summary = preflight(args)
    destination = Path(args.backup_dir).resolve()
    if destination.exists() or destination.is_symlink():
        raise OpsError("backup destination already exists; choose a new path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < 1024 * 1024 * 1024:
        raise OpsError("less than 1 GiB is free at the backup destination")
    temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}.partial-", dir=destination.parent))
    os.chmod(temp, 0o700)
    compose = _compose_prefix(args)
    running = [name for name in _compose_running_services(args) if name in {"api", "flow-session-worker", "web"}]
    try:
        if running:
            _run_docker_checked(compose + ["stop", *running], "could not quiesce the production writers")
        backend_image = config["services"]["api"]["image"]
        volume_map = {
            "data": config["volumes"]["app-data"]["name"],
            "profiles": config["volumes"]["flow-profiles"]["name"],
        }
        _docker_run_volume_helper(backend_image, volume_map["data"], temp, _ARCHIVE_HELPER, "data.tar")
        _docker_run_volume_helper(backend_image, volume_map["profiles"], temp, _ARCHIVE_HELPER, "profiles.tar")
        secret_source = Path(config["secrets"]["owner-password"]["file"])
        validate_owner_password_file(secret_source)
        secret_dir = temp / "secrets"
        secret_dir.mkdir(mode=0o700)
        atomic_copy_file(Path(args.env_file).resolve(strict=True), secret_dir / "deployment.env")
        atomic_copy_file(secret_source, secret_dir / "owner-password")
        git = _run_capture(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
        dirty = _run_capture(["git", "-C", str(ROOT), "status", "--porcelain"])
        metadata = {
            "project": config.get("name"),
            "volumes": volume_map,
            "model_cache_included": False,
            "model_volume": config["volumes"]["models"]["name"],
            "source_commit": git.stdout.strip() if git.returncode == 0 else None,
            "source_tree_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
            "nas_live": "NOT_VERIFIED",
        }
        manifest = create_manifest(temp, metadata)
        _fsync_directory(temp)
        if destination.exists():
            raise OpsError("backup destination appeared during the operation")
        os.rename(temp, destination)
        _fsync_directory(destination.parent)
        return {"state": "BACKUP_READY", "path": str(destination), "payload_count": len(manifest["files"]), "nas_live": "NOT_VERIFIED"}
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    finally:
        if running:
            _run_docker_checked(compose + ["start", *running], "backup completed but services did not restart")


def _ensure_volume(name: str) -> None:
    inspect = _run_capture(["docker", "volume", "inspect", name])
    if inspect.returncode == 0:
        return
    _run_docker_checked(["docker", "volume", "create", name], "could not create restore target volume")


def restore(args) -> dict:
    manifest = verify_backup(Path(args.backup_dir))
    files = manifest["files"]
    if not set(REQUIRED_ARCHIVES).issubset(files) or "secrets/deployment.env" not in files or "secrets/owner-password" not in files:
        raise OpsError("backup is missing a required archive or separate secret file")
    secrets_out = Path(args.secrets_output).resolve()
    if secrets_out.exists() or secrets_out.is_symlink():
        raise OpsError("secrets output path already exists; choose a new path")
    image = args.image
    if not image:
        raise OpsError("restore requires the pinned backend image that created this release")
    targets = {"data": args.data_volume, "profiles": args.profile_volume}
    if len(set(targets.values())) != 2:
        raise OpsError("restore requires two distinct new volume names")
    _ensure_volume(targets["data"])
    _ensure_volume(targets["profiles"])
    backup_dir = Path(args.backup_dir).resolve(strict=True)
    for kind, archive_name in (("data", "data.tar"), ("profiles", "profiles.tar")):
        _docker_restore_volume(image, targets[kind], backup_dir, archive_name, files[archive_name]["sha256"], kind)
    secrets_out.parent.mkdir(parents=True, exist_ok=True)
    staged_secrets = Path(tempfile.mkdtemp(prefix=f".{secrets_out.name}.partial-", dir=secrets_out.parent))
    os.chmod(staged_secrets, 0o700)
    try:
        atomic_copy_file(backup_dir / "secrets/deployment.env", staged_secrets / "deployment.env")
        atomic_copy_file(backup_dir / "secrets/owner-password", staged_secrets / "owner-password")
        if secrets_out.exists():
            raise OpsError("secrets output path appeared during restore")
        os.rename(staged_secrets, secrets_out)
        _fsync_directory(secrets_out.parent)
    except Exception:
        shutil.rmtree(staged_secrets, ignore_errors=True)
        raise
    return {
        "state": "RESTORE_READY",
        "volumes": targets,
        "secrets_directory": str(secrets_out),
        "instruction": "verify both .prj069-restore-complete.json markers before pointing Compose at these new volumes",
    }


def _docker_restore_volume(image: str, volume: str, backup_dir: Path, archive_name: str, digest: str, kind: str) -> None:
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for char in volume):
        raise OpsError("Docker volume name is invalid")
    command = [
        "docker", "run", "--rm", "--network", "none", "--user", "0:0",
        "--mount", f"type=volume,src={volume},dst=/target",
        "--mount", f"type=bind,src={backup_dir.resolve()},dst=/backup,readonly",
        image, "python", "-c", _RESTORE_HELPER, archive_name, digest, kind,
    ]
    result = _run_capture(command)
    if result.returncode:
        raise OpsError(f"restore to new {kind} volume failed (exit {result.returncode}); do not activate that volume")


def export_images(args) -> dict:
    config = _compose_config(args)
    images = sorted({
        config["services"][name]["image"]
        for name in ("api", "web", "gateway")
    })
    image_info = []
    for image in images:
        result = _run_capture(["docker", "image", "inspect", image])
        if result.returncode:
            raise OpsError("a release image is not available locally")
        record = json.loads(result.stdout)[0]
        image_info.append({"reference": image, "id": record["Id"], "repo_digests": record.get("RepoDigests", [])})
    destination = Path(args.output_dir).resolve()
    if destination.exists() or destination.is_symlink():
        raise OpsError("release destination already exists; choose a new path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}.partial-", dir=destination.parent))
    os.chmod(temp, 0o700)
    archive = temp / "images.tar"
    result = _run_capture(["docker", "save", "--output", str(archive), *images])
    if result.returncode:
        shutil.rmtree(temp, ignore_errors=True)
        raise OpsError("Docker image export failed")
    archive.chmod(0o600)
    git = _run_capture(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    dirty = _run_capture(["git", "-C", str(ROOT), "status", "--porcelain"])
    config_paths = (
        ".dockerignore",
        "ha_tang/nas_runtime/Dockerfile.backend",
        "ha_tang/nas_runtime/Dockerfile.gateway",
        "ha_tang/nas_runtime/nginx.conf",
        "ha_tang/nas_runtime/init-entrypoint.sh",
        "ha_tang/nas_trien_khai_sach/compose.yaml",
        "ha_tang/nas_trien_khai_sach/compose.bootstrap-copy.yaml",
        "sin_content_api/requirements.nas.in",
        "sin_content_api/requirements.nas.lock",
        "sin_content_api/src/model_runtime.py",
        "sin_creator_os/Dockerfile",
        "sin_creator_os/next.config.mjs",
        "sin_creator_os/package-lock.json",
        "sin_creator_os/src/lib/api/base-url.ts",
    )
    manifest = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": git.stdout.strip() if git.returncode == 0 else None,
        "source_tree_dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
        "images": image_info,
        "image_archive": {"file": "images.tar", "sha256": sha256_file(archive), "size_bytes": archive.stat().st_size},
        "requirements_lock_sha256": sha256_file(ROOT / "sin_content_api/requirements.nas.lock"),
        "compose_sha256": sha256_file(Path(args.compose_file).resolve(strict=True)),
        "configuration_sha256": {path: sha256_file(ROOT / path) for path in config_paths},
        "nas_live": "NOT_VERIFIED",
    }
    manifest_path = temp / "release-manifest.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    manifest_path.chmod(0o600)
    _fsync_directory(temp)
    if destination.exists():
        shutil.rmtree(temp, ignore_errors=True)
        raise OpsError("release destination appeared during export")
    os.rename(temp, destination)
    _fsync_directory(destination.parent)
    return {"state": "RELEASE_READY", "path": str(destination), "image_count": len(images), "nas_live": "NOT_VERIFIED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", default=str(DEFAULT_COMPOSE))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("backup_dir")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("backup_dir")
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("backup_dir")
    restore_parser.add_argument("--data-volume", required=True)
    restore_parser.add_argument("--profile-volume", required=True)
    restore_parser.add_argument("--secrets-output", required=True)
    restore_parser.add_argument("--image", required=True)
    export_parser = commands.add_parser("export-images")
    export_parser.add_argument("output_dir")
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            _, result = preflight(args)
        elif args.command == "backup":
            args.backup_dir = args.backup_dir
            result = backup(args)
        elif args.command == "verify":
            manifest = verify_backup(Path(args.backup_dir))
            result = {"state": "BACKUP_VERIFIED", "payload_count": len(manifest["files"]), "nas_live": manifest.get("metadata", {}).get("nas_live", "NOT_VERIFIED")}
        elif args.command == "restore":
            result = restore(args)
        else:
            args.output_dir = args.output_dir
            result = export_images(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OpsError, ValueError, OSError, KeyError, TypeError, json.JSONDecodeError):
        print("NAS runtime operation failed; no secret values were emitted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
