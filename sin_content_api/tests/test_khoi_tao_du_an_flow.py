import pathlib
import sys

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

BRIDGE_ROOT = pathlib.Path(__file__).resolve().parents[2] / "cong_cu_tu_dong" / "flow_bridge"
sys.path.insert(0, str(BRIDGE_ROOT))

from google_flow_client import GoogleFlowClient


class FakeButton:
    def __init__(self):
        self.click_count = 0
        self.click_timeouts = []

    def wait_for(self, **_kwargs):
        pass

    def click(self, **kwargs):
        self.click_count += 1
        self.click_timeouts.append(kwargs["timeout"])


class SlowFlowPage:
    def __init__(self):
        self.url = "about:blank"
        self.button = FakeButton()
        self.wait_timeouts = []

    def goto(self, url, **_kwargs):
        self.url = url

    def locator(self, _selector):
        return type("Locator", (), {"first": self.button})()

    def wait_for_url(self, _url, timeout):
        self.wait_timeouts.append(timeout)
        if len(self.wait_timeouts) == 1:
            raise PlaywrightTimeoutError("Flow project initialization is slow")
        self.url = "https://flow.google.com/project/test-project"


class SlowEditor:
    def __init__(self):
        self.wait_count = 0

    def wait_for(self, **_kwargs):
        self.wait_count += 1
        if self.wait_count == 1:
            raise PlaywrightTimeoutError("Flow editor is still initializing")


class SlowEditorPage:
    def __init__(self):
        self.url = "https://flow.google.com/project/test-project"
        self.editor = SlowEditor()
        self.reloaded_urls = []

    def locator(self, selector):
        if "data-slate-editor" in selector:
            return type("Locator", (), {"first": self.editor})()
        if "agent-action-button" in selector:
            return type("Locator", (), {"first": type("Settings", (), {"count": lambda _self: 1, "is_visible": lambda _self: True})()})()
        return type("Locator", (), {"first": type("Missing", (), {"count": lambda _self: 0})()})()

    def goto(self, url, **_kwargs):
        self.reloaded_urls.append(url)


class FlakyNavigationPage:
    def __init__(self):
        self.url = "about:blank"
        self.attempts = 0

    def goto(self, url, **kwargs):
        self.attempts += 1
        assert kwargs["timeout"] == 120_000
        if self.attempts == 1:
            raise PlaywrightTimeoutError("Flow is slow to load")
        self.url = url


def test_new_flow_project_retries_slow_navigation_without_creating_duplicate():
    page = SlowFlowPage()

    project_url = GoogleFlowClient._open_flow_project(page)

    assert project_url == "https://flow.google.com/project/test-project"
    assert page.button.click_count == 1
    assert page.button.click_timeouts == [120_000]
    assert len(page.wait_timeouts) == 2
    assert min(page.wait_timeouts) >= 90_000


def test_flow_navigation_retries_timeout_once():
    page = FlakyNavigationPage()

    GoogleFlowClient._goto_flow_page(page, "https://flow.google.com/")

    assert page.attempts == 2
    assert page.url == "https://flow.google.com/"


def test_flow_editor_initialization_reloads_same_project_once_before_failing():
    page = SlowEditorPage()

    GoogleFlowClient._ensure_video_mode(page)

    assert page.editor.wait_count == 2
    assert page.reloaded_urls == ["https://flow.google.com/project/test-project"]
