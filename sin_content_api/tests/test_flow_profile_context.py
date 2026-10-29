import importlib.util
import importlib
import sys
from pathlib import Path

import pytest


def _context_module():
    assert importlib.util.find_spec("src.modules") is not None
    module = importlib.util.find_spec("src.modules.flow_sessions")
    assert module is not None, "Flow profile context module must be exported"
    from src.modules.flow_sessions import context

    return context


def test_flow_profile_context_is_workspace_scoped_and_restores_nested_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOW_PROFILE_ROOT", str(tmp_path))
    context = _context_module()

    with context.use_flow_profile("workspace-1", "profile-a", "https://flow.google.com/project/abc") as selected:
        assert selected.workspace_id == "workspace-1"
        assert selected.profile_id == "profile-a"
        assert selected.project_url == "https://flow.google.com/project/abc"
        assert selected.profile_dir == tmp_path / "workspaces" / "workspace-1" / "profiles" / "profile-a"
        assert context.current_flow_profile() is selected
        assert context.flow_profile_metadata() == {
            "profile_id": "profile-a",
            "project_url": "https://flow.google.com/project/abc",
        }
        assert context.flow_profile_metadata("https://flow.google.com/project/attempt") == {
            "profile_id": "profile-a",
            "project_url": "https://flow.google.com/project/attempt",
        }
        assert callable(getattr(context, "assert_flow_profile_workspace", None))
        context.assert_flow_profile_workspace("workspace-1")
        with pytest.raises(ValueError, match="FLOW_PROFILE_WORKSPACE_MISMATCH"):
            context.assert_flow_profile_workspace("workspace-2")
        with context.use_flow_profile("workspace-2", "profile-a") as nested:
            assert nested.profile_dir == tmp_path / "workspaces" / "workspace-2" / "profiles" / "profile-a"
        assert context.current_flow_profile() is selected

    assert context.current_flow_profile() is None


@pytest.mark.parametrize("workspace_id,profile_id", [("../outside", "profile-1"), ("workspace-1", "../outside")])
def test_flow_profile_context_rejects_path_traversal(workspace_id, profile_id):
    context = _context_module()

    with pytest.raises(ValueError):
        with context.use_flow_profile(workspace_id, profile_id):
            pass


def test_flow_profile_context_rejects_project_urls_outside_google_flow():
    context = _context_module()

    with pytest.raises(ValueError):
        with context.use_flow_profile("workspace-1", "profile-1", "https://example.com/project/fake"):
            pass


@pytest.mark.parametrize(
    "project_url",
    [
        "https://flow.google.com/project/abc",
        "https://labs.google/fx/tools/flow/project/abc",
        "https://labs.google/fx/tools/flow/project/abc/edit/scene-1",
    ],
)
def test_flow_profile_context_accepts_canonical_flow_project_urls(project_url):
    context = _context_module()
    with context.use_flow_profile("workspace-1", "profile-1", project_url) as selected:
        assert selected.project_url == project_url


def test_bridge_uses_selected_persistent_profile_without_copying_cookies(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOW_PROFILE_ROOT", str(tmp_path / "volume"))
    monkeypatch.setenv("LOCAL_BROWSER_PROFILE_DIR", str(tmp_path / "local-home"))
    bridge = Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"
    sys.path.insert(0, str(bridge))
    sys.modules.pop("config", None)

    config = importlib.import_module("config")
    context = _context_module()

    with context.use_flow_profile("workspace-1", "profile-a") as selected:
        assert config.get_current_browser_profile_dir() == selected.profile_dir
        assert config.get_browser_profile_dirs() == (selected.profile_dir, selected.profile_dir)
        selected.profile_dir.mkdir(parents=True)
        cookies = selected.profile_dir / "Default" / "Network" / "Cookies"
        cookies.parent.mkdir(parents=True)
        cookies.write_text("browser profile", encoding="utf-8")

        assert config.sync_browser_profile() == selected.profile_dir
        assert not (tmp_path / "local-home").exists()
        assert cookies.read_text(encoding="utf-8") == "browser profile"

    sys.modules.pop("config", None)


def test_production_bridge_requires_explicit_workspace_profile_context(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FLOW_PROFILE_ROOT", str(tmp_path / "profiles"))
    bridge = Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"
    sys.path.insert(0, str(bridge))
    sys.modules.pop("config", None)

    config = importlib.import_module("config")
    context = _context_module()

    with pytest.raises(RuntimeError, match="FLOW_PROFILE_SELECTION_REQUIRED"):
        config.get_current_browser_profile_dir()

    with context.use_flow_profile("workspace-live", "profile-live") as selected:
        assert config.get_current_browser_profile_dir() == selected.profile_dir

    sys.modules.pop("config", None)


def test_linux_browser_launch_options_share_persistent_basic_password_store(monkeypatch):
    config = importlib.import_module("config")
    monkeypatch.setattr(config.sys, "platform", "linux")
    args = config.browser_launch_args("--start-maximized")
    assert args.count("--password-store=basic") == 1
    assert "--start-maximized" in args
    monkeypatch.setattr(config.sys, "platform", "win32")
    assert "--password-store=basic" not in config.browser_launch_args()
