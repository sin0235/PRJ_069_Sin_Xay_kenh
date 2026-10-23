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


def test_flow_agent_editor_is_accepted_when_legacy_video_mode_menu_is_absent():
    class Locator:
        def __init__(self, visible):
            self.visible = visible
            self.first = self

        def wait_for(self, **_kwargs):
            assert self.visible

        def count(self):
            return int(self.visible)

        def is_visible(self):
            return self.visible

    class Page:
        def locator(self, selector):
            if "data-slate-editor" in selector or "ProseMirror" in selector:
                return Locator(True)
            if "crop_16_9" in selector:
                return Locator(False)
            if "agent-action-button[aria-label='Settings']" in selector:
                return Locator(True)
            raise AssertionError(selector)

    flow_client.GoogleFlowClient._ensure_video_mode(Page())


def test_flow_agent_can_attach_start_frame_from_media_library(tmp_path):
    image_path = tmp_path / "continuity_shot_01.jpg"
    image_path.write_bytes(b"image")
    events = []
    uploaded = False
    chip_attached = False

    class Locator:
        first = property(lambda self: self)
        last = property(lambda self: self)

        def __init__(self, visible=True, on_click=None):
            self.visible = visible
            self.on_click = on_click

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

        def wait_for(self, **_kwargs):
            events.append("wait_image")

    class Page:
        def locator(self, selector):
            if "Thêm thành phần vào ô nhập câu lệnh" in selector or "Add content to prompt" in selector:
                return Locator()
            if selector.startswith("div[type='button']"):
                return Locator(False)
            if selector == "[role='option']":
                return Locator(uploaded)
            if "button.chip-container" in selector:
                return Locator(lambda: chip_attached)
            if selector == ".cdk-overlay-backdrop-showing":
                return Locator(False)
            raise AssertionError(selector)

        def get_by_role(self, role, name):
            if name == "Thêm vào câu lệnh":
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
    assert events.count("click") == 4
    assert ("press", "Escape") in events
    assert "wait_image" in events


def test_generate_from_image_preserves_pre_submit_flow_failure(monkeypatch, tmp_path):
    from session_manager import FlowSubmissionNotSent
    from src.modules.media_studio.video_provider import GoogleFlowZeroCostProvider

    def fail_before_submit(*_args, **_kwargs):
        raise FlowSubmissionNotSent("image reference unavailable before submit")

    monkeypatch.setattr(flow_client.GoogleFlowClient, "create_video", fail_before_submit)
    with pytest.raises(FlowSubmissionNotSent, match="before submit"):
        GoogleFlowZeroCostProvider().generate_from_image("prompt", tmp_path / "frame.jpg")
