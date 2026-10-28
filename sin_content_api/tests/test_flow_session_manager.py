import sys
from pathlib import Path

import pytest

BRIDGE = Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"
sys.path.insert(0, str(BRIDGE))


def _classifier():
    import session_manager

    classifier = getattr(session_manager, "classify_provider_state", None)
    assert callable(classifier), "provider status must require explicit browser evidence"
    return classifier


def test_provider_status_never_treats_missing_login_prompt_as_success():
    classify = _classifier()

    assert classify("https://flow.google.com/about") == "UNKNOWN"
    assert classify("https://accounts.google.com/", login_required=True) == "LOGIN_REQUIRED"
    assert classify("https://flow.google.com/", authenticated=True) == "READY"
    assert classify("https://flow.google.com/", quota_limited=True) == "QUOTA_LIMITED"


def test_provider_quota_state_takes_priority_over_login_state():
    classify = _classifier()

    assert classify(
        "https://flow.google.com/",
        authenticated=False,
        login_required=True,
        quota_limited=True,
    ) == "QUOTA_LIMITED"


def test_flow_quota_exception_marks_submission_boundary_for_parent_runner():
    from session_manager import FlowQuotaExceeded

    before_submit = FlowQuotaExceeded("FLOW_QUOTA_LIMITED")
    after_submit = FlowQuotaExceeded("FLOW_QUOTA_LIMITED", submitted=True)

    assert before_submit.error_code == "FLOW_QUOTA_LIMITED"
    assert before_submit.submitted is False
    assert after_submit.submitted is True


def test_flow_client_preserves_pre_submit_quota_exception(monkeypatch, tmp_path):
    import google_flow_client
    from session_manager import FlowQuotaExceeded, FlowSubmissionNotSent
    from src.modules.flow_sessions.context import profile_context

    class Page:
        url = "about:blank"

        def goto(self, url, **_kwargs):
            self.url = url

        def wait_for_timeout(self, _milliseconds):
            pass

        def on(self, _event, _callback):
            pass

    page = Page()

    class BrowserContext:
        pages = [page]

        def close(self):
            pass

    class Chromium:
        def launch_persistent_context(self, **_kwargs):
            return BrowserContext()

    class Playwright:
        chromium = Chromium()

    class PlaywrightManager:
        def __enter__(self):
            return Playwright()

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(google_flow_client, "sync_playwright", PlaywrightManager)
    monkeypatch.setattr(
        google_flow_client.GoogleFlowClient,
        "_flow_page_state",
        staticmethod(lambda _page: "QUOTA_LIMITED"),
    )
    monkeypatch.setattr(google_flow_client, "MEDIA_ASSETS_DIR", tmp_path / "assets")

    with profile_context("workspace", "profile", profile_root=tmp_path):
        with pytest.raises(FlowQuotaExceeded) as error:
            google_flow_client.GoogleFlowClient().create_video("prompt", workspace_id="workspace")

    assert error.value.error_code == "FLOW_QUOTA_LIMITED"
    assert error.value.submitted is False
    assert not isinstance(error.value, FlowSubmissionNotSent)


def test_empty_profile_lock_file_does_not_count_as_a_persistent_login_profile(tmp_path, monkeypatch):
    from profile_guard import profile_lock
    import session_manager

    monkeypatch.setenv("FLOW_PROFILE_ROOT", str(tmp_path))
    profile_dir = tmp_path / "workspaces" / "default_ws" / "profiles" / "mac_dinh"
    with profile_lock(profile_dir):
        result = session_manager.check_login_status()

    assert result["profile_exists"] is False
    assert result["state"] == "LOGIN_REQUIRED"


def test_google_flow_client_requires_visible_authenticated_marker():
    import google_flow_client

    state = getattr(google_flow_client.GoogleFlowClient, "_flow_page_state", None)
    assert callable(state), "Flow generation must not infer login from the absence of a sign-in page"

    class Locator:
        def __init__(self, visible):
            self.visible = visible

        @property
        def first(self):
            return self

        def count(self):
            return int(self.visible)

        def is_visible(self):
            return self.visible

    class Page:
        url = "https://flow.google.com/about"

        def __init__(self, ready=False, login=False):
            self.ready = ready
            self.login = login

        def locator(self, selector):
            if "Sign in" in selector or "Log in" in selector or "Đăng nhập" in selector:
                return Locator(self.login)
            if "New project" in selector or "Dự án mới" in selector:
                return Locator(self.ready)
            if "role='textbox'" in selector:
                return Locator(False)
            return Locator(False)

    assert state(Page()) == "UNKNOWN"
    assert state(Page(login=True)) == "LOGIN_REQUIRED"
    assert state(Page(ready=True)) == "READY"


def test_google_flow_client_accepts_the_canonical_labs_flow_project_url():
    import google_flow_client

    class Page:
        url = ""

        def goto(self, url, **_kwargs):
            self.url = url

    page = Page()
    project_url = "https://labs.google/fx/tools/flow/project/project-123"
    assert google_flow_client.GoogleFlowClient._open_flow_project(page, project_url) == project_url
    assert page.url == project_url
