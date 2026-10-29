"""Shared profile and Flow client configuration."""

import os
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
API_ROOT = PROJECT_ROOT / "sin_content_api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from src.modules.flow_sessions.context import current_flow_profile, default_flow_profile_dir

FLOW_PROFILE_ROOT = os.environ.get("FLOW_PROFILE_ROOT")
FLOW_PROFILE_ID = os.environ.get("FLOW_PROFILE_ID", "mac_dinh")
BROWSER_PROFILE_DIR = default_flow_profile_dir()
LOCAL_BROWSER_PROFILE_DIR = BROWSER_PROFILE_DIR
MEDIA_ASSETS_DIR = Path(os.environ.get("MEDIA_ROOT_DIR", PROJECT_ROOT / "03_ban_lam_viec" / "media_assets"))

FLOW_MUSIC_URL = "https://www.flowmusic.app/"
GOOGLE_FLOW_URL = "https://flow.google.com/"
_DEFAULT_BROWSER_CHANNEL = "msedge" if sys.platform == "win32" else "chromium"
BROWSER_CHANNEL = os.environ.get("BROWSER_CHANNEL", _DEFAULT_BROWSER_CHANNEL)
DEFAULT_TIMEOUT_MS = 240000
POLL_INTERVAL_SEC = 3


def browser_launch_args(*extra: str) -> list[str]:
    args = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    if sys.platform.startswith("linux"):
        args.append("--password-store=basic")
    return args + list(extra)


def get_current_browser_profile_dir() -> Path:
    selected = current_flow_profile()
    if selected is not None:
        return selected.profile_dir
    if os.environ.get("APP_ENV", "").strip().lower() == "production":
        raise RuntimeError("FLOW_PROFILE_SELECTION_REQUIRED")
    return default_flow_profile_dir()


def get_browser_profile_dirs() -> tuple[Path, Path]:
    profile_dir = get_current_browser_profile_dir()
    return profile_dir, profile_dir


def sync_browser_profile(src_dir: str | Path | None = None, dst_dir: str | Path | None = None) -> Path:
    profile_dir = get_current_browser_profile_dir()
    if any(path is not None and Path(path).resolve() != profile_dir.resolve() for path in (src_dir, dst_dir)):
        raise ValueError("Flow profiles must use their persistent volume directly; profile copying is disabled.")
    profile_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    return profile_dir


def sync_local_to_nas(src_dir: str | Path | None = None, dst_dir: str | Path | None = None) -> None:
    sync_browser_profile(src_dir, dst_dir)
