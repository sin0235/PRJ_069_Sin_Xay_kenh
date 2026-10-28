"""Trạng thái worker nhỏ, không tải model trong API."""
import json
import os
from pathlib import Path
import time


def heartbeat_path() -> Path:
    return Path(os.getenv("WORKER_HEARTBEAT_PATH", "/tmp/prj069-worker.json"))


def write_worker_heartbeat() -> None:
    path = heartbeat_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"updated_at": time.time(), "pid": os.getpid()}))
    temporary.replace(path)


def worker_status() -> dict:
    try:
        updated = float(json.loads(heartbeat_path().read_text())["updated_at"])
        if not 0 <= time.time() - updated < 30:
            raise ValueError("stale")
        return {"state": "READY", "updated_at": updated}
    except (OSError, ValueError, TypeError, KeyError):
        return {"state": "NOT_READY", "error_code": "WORKER_UNAVAILABLE"}


def validate_production_runtime() -> None:
    if os.getenv("APP_ENV", "").lower() != "production":
        return
    for flag in ("TESTING", "DEV_AUTH_BYPASS", "CONTENT_VIDEO_TEST_WORKER", "BAHA_AUTH_ALLOW_SELF_APPROVAL_IN_TEST", "SYNTHETIC_DATA_ALLOWED", "ALLOW_LOCAL_TEST_SYNTH"):
        if os.getenv(flag, "0").lower() in {"1", "true", "yes"}:
            raise RuntimeError(f"PRODUCTION_UNSAFE_FLAG:{flag}")
