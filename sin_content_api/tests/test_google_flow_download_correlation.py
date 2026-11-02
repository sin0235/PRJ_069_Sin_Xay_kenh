import importlib
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

importlib.import_module("cong_cu_tu_dong.flow_bridge")
flow_client = importlib.import_module("google_flow_client")
_has_successful_generation = flow_client._has_successful_generation
_new_flow_prompt_bubble_index = flow_client._new_flow_prompt_bubble_index


def test_only_completion_for_submitted_media_is_accepted():
    old = {
        "name": "old-media",
        "mediaMetadata": {"mediaStatus": {"mediaGenerationStatus": "SUCCESSFUL"}},
    }
    new = {
        "name": "new-media",
        "mediaMetadata": {"mediaStatus": {"mediaGenerationStatus": "SUCCESSFUL"}},
    }

    assert not _has_successful_generation([old], "new-media")
    assert _has_successful_generation([old, new], "new-media")


def test_prompt_must_appear_in_a_new_flow_chat_bubble():
    prompt = "A unique blue hummingbird prompt"
    bubbles = [prompt, "old response", "A unique\nblue hummingbird prompt"]

    assert _new_flow_prompt_bubble_index(bubbles, 2, prompt) == 2
    assert _new_flow_prompt_bubble_index(bubbles[:2], 2, prompt) is None


def test_new_video_run_creates_a_fresh_flow_project():
    events = []

    class Button:
        first = property(lambda self: self)

        def count(self):
            return 1

        def is_visible(self):
            return True

        def wait_for(self, **_kwargs):
            pass

        def click(self, **_kwargs):
            events.append("new_project")
            page.url = "https://flow.google.com/project/run-123"

    class MissingButton:
        first = property(lambda self: self)

        def count(self):
            return 0

        def is_visible(self):
            return False

    class Page:
        url = "about:blank"

        def goto(self, url, **_kwargs):
            events.append(("goto", url))
            self.url = url

        def get_by_role(self, role, name):
            assert role == "button"
            return Button() if name == "Dự án mới" else MissingButton()

        def locator(self, selector):
            assert selector == "button:has-text('New project'), button:has-text('Dự án mới')"
            return Button()

        def wait_for_url(self, pattern, **_kwargs):
            assert pattern == "**/project/**"
            assert "/project/" in self.url

    page = Page()
    project_url = flow_client.GoogleFlowClient._open_flow_project(page)

    assert project_url == "https://flow.google.com/project/run-123"
    assert "new_project" in events
    assert not any(isinstance(event, tuple) and "/project/" in event[1] for event in events)


def test_new_project_button_falls_back_to_visible_localized_button_text():
    events = []

    class Button:
        first = property(lambda self: self)
        visible = False

        def count(self):
            return int(self.visible)

        def is_visible(self):
            return self.visible

        def wait_for(self, **_kwargs):
            self.visible = True

        def click(self, **_kwargs):
            events.append("new_project")
            page.url = "https://flow.google.com/project/run-456"

    class MissingButton:
        first = property(lambda self: self)

        def count(self):
            return 0

        def is_visible(self):
            return False

    class Page:
        url = "about:blank"

        def goto(self, url, **_kwargs):
            self.url = url

        def get_by_role(self, role, name):
            assert role == "button"
            return MissingButton()

        def locator(self, selector):
            assert selector == "button:has-text('New project'), button:has-text('Dự án mới')"
            return Button()

        def wait_for_url(self, pattern, **_kwargs):
            assert pattern == "**/project/**"

    page = Page()

    assert flow_client.GoogleFlowClient._open_flow_project(page) == "https://flow.google.com/project/run-456"
    assert events == ["new_project"]


def test_later_shots_reopen_the_saved_flow_project_without_creating_another():
    events = []
    project_url = "https://flow.google.com/project/run-123"

    class Page:
        url = "about:blank"

        def goto(self, url, **_kwargs):
            events.append(("goto", url))
            self.url = f"{url}/edit/scene-1" if len(events) == 1 else url

        def get_by_role(self, *_args, **_kwargs):
            raise AssertionError("Shot sau phải mở project của run, không tạo project khác")

    page = Page()
    actual_url = flow_client.GoogleFlowClient._open_flow_project(page, project_url)

    assert actual_url == project_url
    assert events == [("goto", project_url), ("goto", project_url)]


def test_flow_project_url_rejects_external_hosts():
    class Page:
        def goto(self, *_args, **_kwargs):
            raise AssertionError("KhÃ´ng Ä‘Æ°á»£c Ä‘iá»u hÆ°á»›ng Ä‘áº¿n URL khÃ´ng pháº£i Google Flow")

    with pytest.raises(RuntimeError, match="FLOW_PROJECT_URL_INVALID"):
        flow_client.GoogleFlowClient._open_flow_project(Page(), "https://example.com/project/fake")


def test_localized_flow_agent_editor_is_accepted_without_legacy_video_mode_menu():
    class Locator:
        def __init__(self, visible):
            self.visible = visible
            self.first = self

        def wait_for(self, **_kwargs):
            pass

        def count(self):
            return int(self.visible)

        def get_attribute(self, _name):
            return "false"

        def is_visible(self):
            return self.visible

        def click(self, **_kwargs):
            pass

        def locator(self, _selector):
            return Locator(True)

        def filter(self, **_kwargs):
            return Locator(True)

    class Page:
        def locator(self, selector):
            if selector == "button.agent-mode-chip":
                return Locator(False)
            if "settings-trigger-button" in selector or "aria-label*='settings'" in selector:
                return Locator(False)
            if "Nano Banana" in selector or "button:has-text('Video')" in selector or "button:has-text('Veo')" in selector:
                return Locator(False)
            if selector == '[role="textbox"]':
                return Locator(False)
            if "data-slate-editor" in selector or "ProseMirror" in selector:
                return Locator(True)
            if "crop_16_9" in selector:
                return Locator(False)
            if selector == "button.agent-action-button[aria-label='Settings'], button.agent-action-button:has-text('tune')":
                return Locator(True)
            if selector in ("div.settings-section", "button.video-model-picker-button", "button.settings-save-button"):
                return Locator(True)
            raise AssertionError(selector)

    flow_client.GoogleFlowClient._ensure_video_mode(Page())


def test_flow_agent_settings_selects_portrait_video_ratio():
    clicks = []

    class Locator:
        first = property(lambda self: self)

        def __init__(self, name, found=False):
            self.name = name
            self.found = found

        def count(self):
            return int(self.found)

        def is_visible(self):
            return self.found

        def wait_for(self, **_kwargs):
            pass

        def get_attribute(self, _name):
            return None

        def click(self, **_kwargs):
            clicks.append(self.name)

        def filter(self, *, has=None, has_text=None):
            if has is not None:
                return Locator("video-section", True)
            return Locator("video-9:16", self.found)

        def locator(self, selector):
            return Locator("video-radios", self.found)

    class Page:
        def locator(self, selector):
            if selector == "button.agent-mode-chip":
                return Locator("agent-mode", False)
            if selector == "button.agent-action-button[aria-label='Settings'], button.agent-action-button:has-text('tune')":
                return Locator("agent-settings", True)
            if selector.startswith("button.settings-trigger-button") or "aria-label*='settings'" in selector:
                return Locator("settings-trigger", False)
            if "Nano Banana" in selector or "button:has-text('Video')" in selector or "button:has-text('Veo')" in selector:
                return Locator("legacy-model", False)
            if selector == '[role="textbox"]':
                return Locator("legacy-textbox", False)
            if "data-slate-editor" in selector or "ProseMirror" in selector:
                return Locator("editor", True)
            if "crop_16_9" in selector or "crop_9_16" in selector or "crop_square" in selector:
                return Locator("legacy-ratio-menu", False)
            if selector == "div.settings-section":
                return Locator("settings-section", True)
            if selector == "button.video-model-picker-button":
                return Locator("video-model", True)
            if selector == "button.settings-save-button":
                return Locator("save", True)
            raise AssertionError(selector)

    flow_client.GoogleFlowClient._ensure_video_mode(Page(), "9:16")

    assert clicks == ["agent-settings", "video-9:16", "save"]


def test_flow_video_mode_selects_requested_portrait_ratio():
    clicks = []

    class Locator:
        first = property(lambda self: self)

        def __init__(self, name, found=True):
            self.name = name
            self.found = found

        def wait_for(self, **_kwargs):
            if not self.found:
                raise flow_client.PlaywrightTimeoutError("Locator is not visible")

        def get_attribute(self, _name):
            return "false"

        def count(self):
            return int(self.found)

        def click(self, **_kwargs):
            clicks.append(self.name)

    class Page:
        url = "https://flow.google.com/project/test/edit/abc"

        def locator(self, selector):
            if selector == "button.agent-mode-chip":
                return Locator("agent-mode", found=False)
            if "settings-trigger-button" in selector or "aria-label*='settings'" in selector:
                return Locator("generation-settings", found=False)
            if "Nano Banana" in selector or "button:has-text('Video')" in selector or "button:has-text('Veo')" in selector:
                return Locator("model-button", found=False)
            if selector == '[role="textbox"]':
                return Locator("textbox", found=False)
            if "data-slate-editor" in selector or "ProseMirror" in selector:
                return Locator("editor")
            if "trigger-VIDEO" in selector:
                return Locator("video-mode")
            if "trigger-PORTRAIT" in selector:
                return Locator("portrait")
            if "button[aria-haspopup='menu']" in selector:
                return Locator("aspect-menu")
            return Locator("missing", found=False)

        def wait_for_timeout(self, _milliseconds):
            pass

    flow_client.GoogleFlowClient._ensure_video_mode(Page(), "9:16")

    assert clicks == ["aspect-menu", "video-mode", "aspect-menu", "portrait"]


@pytest.mark.parametrize("attach_on_wait", [False, True])
def test_flow_agent_can_attach_start_frame_from_media_library(tmp_path, attach_on_wait):
    image_path = tmp_path / "continuity_shot_01.jpg"
    image_path.write_bytes(b"image")
    events = []
    uploaded = False
    chip_attached = False

    def set_chip_on_wait():
        nonlocal chip_attached
        if attach_on_wait:
            chip_attached = True

    class Locator:
        first = property(lambda self: self)
        last = property(lambda self: self)

        def __init__(self, visible=True, on_click=None, on_wait=None):
            self.visible = visible
            self.on_click = on_click
            self.on_wait = on_wait

        def press(self, key):
            events.append(("press", key))

        def count(self):
            return int(self.visible() if callable(self.visible) else self.visible)

        def click(self, **_kwargs):
            events.append("click")
            if self.on_click:
                self.on_click()

        def filter(self, **_kwargs):
            return self

        def wait_for(self, **kwargs):
            events.append(("wait_image", kwargs.get("timeout")))
            if kwargs.get("state") == "visible" and not (self.visible() if callable(self.visible) else self.visible):
                if self.on_wait:
                    self.on_wait()
                if not (self.visible() if callable(self.visible) else self.visible):
                    raise TimeoutError("not visible")

    class Page:
        def locator(self, selector):
            if selector == "button.sidebar-upload-btn":
                events.append(("upload_button", selector))
                return Locator()
            if "Thêm thành phần vào ô nhập câu lệnh" in selector or "Add content to prompt" in selector:
                return Locator()
            if selector.startswith("div[type='button']"):
                return Locator(False)
            if selector == "[role='option']":
                return Locator(lambda: uploaded)
            if "flow-base-prompt-box button.chip-container" in selector:
                return Locator(lambda: chip_attached, on_wait=set_chip_on_wait)
            if "button.chip-container" in selector:
                raise AssertionError("Ảnh đã có trong các tin nhắn cũ, selector phải giới hạn trong composer")
            if selector == ".cdk-overlay-backdrop-showing":
                return Locator(False)
            raise AssertionError(selector)

        def get_by_role(self, role, name=None):
            if role == "dialog":
                class HiddenConsent:
                    first = property(lambda self: self)
                    def wait_for(self, **_kwargs):
                        raise flow_client.PlaywrightTimeoutError("consent dialog not shown")
                return SimpleNamespace(get_by_role=lambda *_args, **_kwargs: HiddenConsent())
            if name == "Thêm vào câu lệnh":
                events.append(("role_button", name))
                def attach_chip():
                    nonlocal chip_attached
                    chip_attached = True
                return Locator(True, attach_chip)
            return Locator(role == "button" and name in {
                "Tải nội dung nghe nhìn lên"
            })

        def wait_for_timeout(self, _timeout):
            pass

        keyboard = SimpleNamespace(press=lambda key: events.append(("press", key)))

        @contextmanager
        def expect_file_chooser(self, **_kwargs):
            def set_files(path):
                nonlocal uploaded
                uploaded = True
                events.append(("set_files", path))
            chooser = SimpleNamespace(set_files=set_files)
            yield SimpleNamespace(value=chooser)

    flow_client.GoogleFlowClient._attach_start_image(Page(), image_path, 10)
    assert ("set_files", str(image_path)) in events
    assert events.count("click") == (3 if attach_on_wait else 4)
    assert ("press", "Escape") in events
    assert ("wait_image", 15000) in events
    assert ("upload_button", "button.sidebar-upload-btn") in events
    assert (("role_button", "Thêm vào câu lệnh") in events) is (not attach_on_wait)


def test_flow_agent_accepts_new_composer_media_indicator(tmp_path):
    image_path = tmp_path / "continuity_shot_02.jpg"
    image_path.write_bytes(b"image")
    events = []
    components_attached = False

    class Locator:
        first = property(lambda self: self)
        last = property(lambda self: self)

        def __init__(self, visible=True, on_click=None):
            self.visible = visible
            self.on_click = on_click

        def count(self):
            return int(self.visible() if callable(self.visible) else self.visible)

        def click(self, **_kwargs):
            events.append("click")
            if self.on_click:
                self.on_click()

        def wait_for(self, **kwargs):
            if kwargs.get("state") == "visible" and not self.count():
                raise TimeoutError("not visible")

        def filter(self, **_kwargs):
            return self

    class Page:
        def locator(self, selector):
            if selector.startswith("div[type='button']"):
                return Locator(False)
            if "button:has-text('Thành phần')" in selector:
                return Locator(lambda: components_attached)
            if "flow-base-prompt-box button.chip-container" in selector:
                return Locator(False)
            if "Thêm thành phần vào ô nhập câu lệnh" in selector:
                return Locator()
            if selector == "[role='option']":
                return Locator(True)
            if selector == ".cdk-overlay-backdrop-showing":
                return Locator(False)
            raise AssertionError(selector)

        def get_by_role(self, role, name):
            assert role == "button"
            assert name == "Thêm vào câu lệnh"

            def attach_component():
                nonlocal components_attached
                components_attached = True

            return Locator(True, attach_component)

        def wait_for_timeout(self, _timeout):
            pass

        keyboard = SimpleNamespace(press=lambda key: events.append(("press", key)))

    flow_client.GoogleFlowClient._attach_start_image(Page(), image_path, 10)
    assert components_attached


def test_generate_from_image_preserves_pre_submit_flow_failure(monkeypatch, tmp_path):
    from session_manager import FlowSubmissionNotSent
    from src.modules.media_studio.video_provider import GoogleFlowZeroCostProvider

    def fail_before_submit(*_args, **_kwargs):
        raise FlowSubmissionNotSent("image reference unavailable before submit")

    monkeypatch.setattr(flow_client.GoogleFlowClient, "create_video", fail_before_submit)
    with pytest.raises(FlowSubmissionNotSent, match="before submit"):
        GoogleFlowZeroCostProvider().generate_from_image("prompt", tmp_path / "frame.jpg")


def test_unusual_activity_error_after_new_prompt_is_detected():
    # Chuỗi bong bóng thực tế từ log NAS ngày 30-10-2026: phản hồi cũ, prompt mới, rồi bong bóng lỗi.
    bubbles = [
        "play_circleTôi đang tạo video 10 giây tỷ lệ 16:9",
        "Tạo video 16:9, thời lượng 10 giây",
        "errorChúng tôi nhận thấy có hoạt động bất thường nào đó. Xin lưu ý rằng các tiện ích trình duyệt",
    ]

    assert flow_client._flow_unusual_activity_after_prompt(bubbles, 1)
    # Phản hồi cũ nằm trước prompt mới không được tính.
    assert not flow_client._flow_unusual_activity_after_prompt(bubbles[:2], 1)
    assert not flow_client._flow_unusual_activity_after_prompt(bubbles[:2] + ["Video đã được lên lịch"], 1)


def test_unusual_activity_is_not_auto_retried_but_is_blocked_as_not_sent():
    exc = flow_client.FlowUnusualActivity("FLOW_UNUSUAL_ACTIVITY: Google từ chối phiên Flow tự động")

    assert isinstance(exc, flow_client.FlowSubmissionNotSent)
    assert "FLOW_SUBMIT_NOT_SENT" not in str(exc)


def test_agent_reply_after_prompt_ignores_error_bubbles():
    bubbles = ["Tạo video 16:9", "errorChúng tôi nhận thấy có hoạt động bất thường"]
    assert not flow_client._flow_agent_replied_after_prompt(bubbles, 0)
    assert flow_client._flow_agent_replied_after_prompt(bubbles + ["Video đã được lên lịch và đang chờ trong hàng đợi"], 0)
    assert not flow_client._flow_agent_replied_after_prompt(bubbles[:1], 0)


def test_unusual_activity_cooldown_marker_roundtrip(tmp_path, monkeypatch):
    assert flow_client._unusual_cooldown_remaining(tmp_path) == 0
    flow_client._mark_unusual_activity(tmp_path)
    assert 0 < flow_client._unusual_cooldown_remaining(tmp_path) <= flow_client._UNUSUAL_COOLDOWN_SEC
    monkeypatch.setattr(flow_client, "_UNUSUAL_COOLDOWN_SEC", 0)
    assert flow_client._unusual_cooldown_remaining(tmp_path) == 0
    flow_client._clear_unusual_activity(tmp_path)
    assert not (tmp_path / flow_client._UNUSUAL_MARKER).exists()


def test_browser_display_falls_back_to_headless_without_xvfb(monkeypatch):
    config = importlib.import_module("config")
    monkeypatch.setattr(config.shutil, "which", lambda name: None)
    with config.browser_display(True) as (headless, env):
        assert headless is True and env is None
    with config.browser_display(False) as (headless, env):
        assert headless is False and env is None
