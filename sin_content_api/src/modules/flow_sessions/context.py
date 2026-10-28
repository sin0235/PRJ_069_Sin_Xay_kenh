"""Per-job Flow profile selection shared by the API worker and browser clients."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_FLOW_PROFILE: ContextVar["FlowProfileSnapshot | None"] = ContextVar("flow_profile", default=None)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_LEGACY_PROFILE_DIR = _PROJECT_ROOT / "cong_cu_tu_dong" / "flow_bridge" / "browser_profile"


@dataclass(frozen=True)
class FlowProfileSnapshot:
    workspace_id: str
    profile_id: str
    profile_dir: Path
    project_url: str | None = None


def _validate_id(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Invalid Flow workspace or profile id.")
    return value


def flow_profile_dir(workspace_id: str, profile_id: str, root: str | Path | None = None) -> Path:
    root_path = Path(root or os.environ.get("FLOW_PROFILE_ROOT") or _LEGACY_PROFILE_DIR)
    return root_path / "workspaces" / _validate_id(workspace_id) / "profiles" / _validate_id(profile_id)


def default_flow_profile_dir() -> Path:
    root = os.environ.get("FLOW_PROFILE_ROOT")
    if root:
        return flow_profile_dir(
            os.environ.get("FLOW_WORKSPACE_ID", "default_ws"),
            os.environ.get("FLOW_PROFILE_ID", "mac_dinh"),
            root,
        )
    return Path(os.environ.get("BROWSER_PROFILE_DIR") or _LEGACY_PROFILE_DIR)


def validate_flow_project_url(project_url: str | None) -> str | None:
    if project_url is None:
        return None
    try:
        parsed = urlsplit(project_url)
        hostname = parsed.hostname
        has_port = parsed.port is not None
    except ValueError as exc:
        raise ValueError("Invalid Google Flow project URL.") from exc
    path_parts = parsed.path.strip("/").split("/")
    canonical_project_path = (
        hostname == "flow.google.com"
        and len(path_parts) >= 2
        and path_parts[0] == "project"
        and bool(path_parts[1])
    ) or (
        hostname == "labs.google"
        and len(path_parts) >= 5
        and path_parts[:4] == ["fx", "tools", "flow", "project"]
        and bool(path_parts[4])
    )
    if (
        parsed.scheme != "https"
        or hostname not in {"flow.google.com", "labs.google"}
        or has_port
        or parsed.username is not None
        or parsed.password is not None
        or not canonical_project_path
    ):
        raise ValueError("Invalid Google Flow project URL.")
    return project_url


@contextmanager
def profile_context(
    workspace_id: str,
    profile_id: str,
    project_url: str | None = None,
    *,
    profile_root: str | Path | None = None,
):
    selected = FlowProfileSnapshot(
        workspace_id=_validate_id(workspace_id),
        profile_id=_validate_id(profile_id),
        profile_dir=flow_profile_dir(workspace_id, profile_id, profile_root),
        project_url=validate_flow_project_url(project_url),
    )
    token = _FLOW_PROFILE.set(selected)
    try:
        yield selected
    finally:
        _FLOW_PROFILE.reset(token)


def current_flow_profile() -> FlowProfileSnapshot | None:
    return _FLOW_PROFILE.get()


def assert_flow_profile_workspace(workspace_id: str) -> None:
    selected = current_flow_profile()
    if selected and selected.workspace_id != _validate_id(workspace_id):
        raise ValueError("FLOW_PROFILE_WORKSPACE_MISMATCH")


def flow_profile_metadata(project_url: str | None = None) -> dict[str, str | None]:
    selected = current_flow_profile()
    return {
        "profile_id": selected.profile_id if selected else None,
        "project_url": project_url or (selected.project_url if selected else None),
    }


use_flow_profile = profile_context
