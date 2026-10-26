import pathlib
import subprocess
import sys
import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
API_ROOT = pathlib.Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, API_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import src.modules.media_studio.router as media_router
import src.modules.media_studio.music_provider as music_provider

flow_music_client = importlib.import_module("cong_cu_tu_dong.flow_bridge.flow_music_client")
google_flow_client = importlib.import_module("google_flow_client")
session_manager = importlib.import_module("session_manager")
video_provider = importlib.import_module("src.modules.media_studio.video_provider")
video_processor_module = importlib.import_module("src.modules.media_studio.video_processor")


def test_media_endpoints_require_a_flow_session(monkeypatch):
    class LoginRequired(RuntimeError):
        pass

    def missing_session(**kwargs):
        raise LoginRequired("FLOW_LOGIN_REQUIRED")

    monkeypatch.setattr(media_router, "FlowLoginRequired", LoginRequired, raising=False)
    monkeypatch.setattr(media_router.music_orchestrator, "generate_music_track", missing_session)
    monkeypatch.setattr(media_router.video_orchestrator, "generate_video_scene", missing_session)
    tenant = SimpleNamespace(workspace_id="workspace-test", user_id="user-test")

    for generate, args in (
        (media_router.generate_music_track, {"prompt": "nhạc", "genre": "Pop", "mood": "Upbeat", "lyrics": None, "use_official_lyria": False, "normalize_tiktok": True}),
        (media_router.generate_video_scene, {"prompt": "video", "aspect_ratio": "9:16", "use_official_omni": False}),
    ):
        with pytest.raises(HTTPException) as error:
            generate(**args, db=None, tenant=tenant)
        assert error.value.status_code == 401
        assert error.value.detail["error_code"] == "FLOW_LOGIN_REQUIRED"


def test_missing_flow_music_session_does_not_generate_fallback(monkeypatch, tmp_path):
    class LoginRequired(RuntimeError):
        pass

    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(session_manager, "FlowLoginRequired", LoginRequired, raising=False)
    monkeypatch.setattr(flow_music_client, "FlowLoginRequired", LoginRequired, raising=False)
    monkeypatch.setattr(music_provider, "FlowLoginRequired", LoginRequired, raising=False)
    monkeypatch.setattr(flow_music_client.FlowMusicClient, "create_track", lambda *args, **kwargs: (_ for _ in ()).throw(LoginRequired("FLOW_LOGIN_REQUIRED")))
    monkeypatch.setattr(music_provider, "MEDIA_ROOT_DIR", tmp_path)
    provider = music_provider.FlowMusicZeroCostProvider()
    monkeypatch.setattr(provider, "_generate_rich_melody", lambda *args, **kwargs: pytest.fail("Không được sinh nhạc dự phòng khi thiếu phiên Flow."))

    with pytest.raises(LoginRequired, match="FLOW_LOGIN_REQUIRED"):
        provider.generate("nhạc", workspace_id="workspace-test")


def test_missing_google_flow_session_keeps_login_error(monkeypatch, tmp_path):
    class LoginRequired(RuntimeError):
        pass

    monkeypatch.setattr(session_manager, "FlowLoginRequired", LoginRequired, raising=False)
    monkeypatch.setattr(google_flow_client, "FlowLoginRequired", LoginRequired, raising=False)
    monkeypatch.setattr(video_provider, "FlowLoginRequired", LoginRequired, raising=False)
    monkeypatch.setattr(google_flow_client.GoogleFlowClient, "create_video", lambda *args, **kwargs: (_ for _ in ()).throw(LoginRequired("FLOW_LOGIN_REQUIRED")))
    monkeypatch.setattr(video_provider, "MEDIA_ROOT_DIR", tmp_path)

    with pytest.raises(LoginRequired, match="FLOW_LOGIN_REQUIRED"):
        video_provider.GoogleFlowZeroCostProvider().generate("video", workspace_id="workspace-test")


def test_google_flow_media_redirect_encodes_trpc_input():
    media_name = "projects/project-1/media/clip 01"
    url = google_flow_client.GoogleFlowClient._media_redirect_url(media_name)

    assert url == (
        "https://labs.google/fx/api/trpc/media.getMediaUrlRedirect"
        "?input=%7B%22json%22%3A%7B%22name%22%3A%22projects%2Fproject-1%2Fmedia%2Fclip%2001%22%7D%7D"
    )


def test_google_flow_finds_button_element_used_as_start_frame(monkeypatch, tmp_path):
    image_path = tmp_path / "reference.jpg"
    image_path.write_bytes(b"image")

    class Locator:
        def __init__(self, selector):
            self.selector = selector
            self.first = self

        def count(self):
            return int(self.selector == "div[type='button'][aria-haspopup='dialog'], button[aria-haspopup='dialog'], [role='button'][aria-haspopup='dialog']")

        def click(self, **kwargs):
            if self.selector != "div[type='button'][aria-haspopup='dialog'], button[aria-haspopup='dialog'], [role='button'][aria-haspopup='dialog']":
                raise RuntimeError("no matching upload control")

    class Page:
        def locator(self, selector):
            return Locator(selector)

        def wait_for_timeout(self, timeout):
            pass

        def expect_file_chooser(self, **kwargs):
            class Expect:
                def __enter__(self):
                    return SimpleNamespace(value=None)

                def __exit__(self, *args):
                    return False

            return Expect()

    with pytest.raises(RuntimeError, match="Không mở được hộp thoại tải ảnh"):
        google_flow_client.GoogleFlowClient._attach_start_image(Page(), image_path, 1)


def test_google_flow_enters_video_mode_before_attaching_image():
    calls = []

    class Locator:
        def __init__(self, selector):
            self.selector = selector
            self.first = self

        def wait_for(self, **kwargs):
            calls.append(("ready", kwargs["state"]))

        def count(self):
            return 1

        def click(self, **kwargs):
            calls.append(("click", self.selector))

    class Page:
        url = "https://flow.google.com/project/test"

        def locator(self, selector):
            return Locator(selector)

        def wait_for_timeout(self, timeout):
            calls.append(("wait", timeout))

    google_flow_client.GoogleFlowClient._ensure_video_mode(Page())

    assert calls[0] == ("ready", "visible")
    assert calls[1][0] == "click"
    assert "crop_16_9" in calls[1][1]
    video_click = next(call for call in calls if call[0] == "click" and "role='tab'" in call[1])
    assert "trigger-VIDEO" in video_click[1]


def test_flow_download_timeout_does_not_recommend_removed_upload_button(monkeypatch, tmp_path):
    monkeypatch.setattr(video_provider, "MEDIA_ROOT_DIR", tmp_path)
    monkeypatch.setattr(
        google_flow_client.GoogleFlowClient,
        "create_video",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("FLOW_DOWNLOAD_TIMEOUT")),
    )

    with pytest.raises(RuntimeError) as error:
        video_provider.GoogleFlowZeroCostProvider().generate("video", workspace_id="workspace-test")

    assert "Tải Lên Video 16:9" not in str(error.value)
    assert "không tạo lại ngay" in str(error.value)


def test_flow_video_keeps_raw_source_for_next_scene(monkeypatch, tmp_path):
    monkeypatch.setattr(video_provider, "MEDIA_ROOT_DIR", tmp_path)
    source = tmp_path / "flow_source.mp4"
    subprocess.run(
        [video_processor_module.video_processor.ffmpeg_bin, "-y", "-f", "lavfi", "-i",
         "color=c=0x1E293B:s=1080x1920:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True, capture_output=True,
    )
    flow_call = {}

    class FakeFlowClient:
        def create_video(self, **kwargs):
            flow_call.update(kwargs)
            return {"storage_path": str(source)}

    monkeypatch.setattr(google_flow_client, "GoogleFlowClient", lambda **kwargs: FakeFlowClient())
    monkeypatch.setattr(video_provider.video_processor, "expand_16_9_to_9_16", lambda **_: pytest.fail("blur expansion should be skipped"))
    on_project_created = lambda _url: None
    project_url = "https://flow.google.com/project/run-test"
    result = video_provider.GoogleFlowZeroCostProvider().generate(
        "video",
        workspace_id="workspace-test",
        flow_project_url=project_url,
        on_flow_project_created=on_project_created,
    )

    raw_source = pathlib.Path(result["storage_path"]).with_name(
        result["filename"].replace("flow_native_9_16_", "flow_source_9_16_", 1)
    )
    assert raw_source.read_bytes() == source.read_bytes()
    assert video_processor_module.video_processor.probe_video(pathlib.Path(result["storage_path"]))["aspect_ratio"] == "9:16"
    assert flow_call["flow_project_url"] == project_url
    assert flow_call["on_flow_project_created"] is on_project_created


def test_image_video_flow_preserves_selected_aspect_ratio(monkeypatch, tmp_path):
    monkeypatch.setattr(video_provider, "MEDIA_ROOT_DIR", tmp_path)
    source = tmp_path / "flow_source.mp4"
    source.write_bytes(b"flow video")
    received = {}

    class FakeFlowClient:
        def create_video(self, **kwargs):
            received["flow"] = kwargs
            return {"storage_path": str(source)}

    def normalize(command, **kwargs):
        received["command"] = command
        pathlib.Path(command[-1]).write_bytes(b"normalized video")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(google_flow_client, "GoogleFlowClient", lambda **kwargs: FakeFlowClient())
    monkeypatch.setattr(video_provider.subprocess, "run", normalize)
    monkeypatch.setattr(video_provider.video_processor, "probe_video", lambda _path: {"duration_seconds": 10, "watermark_removed": False})

    result = video_provider.GoogleFlowZeroCostProvider().generate_from_image(
        "video", tmp_path / "reference.jpg", workspace_id="workspace-test", aspect_ratio="16:9"
    )

    assert received["flow"]["aspect_ratio"] == "16:9"
    assert any(argument.startswith("scale=1920:1080") for argument in received["command"])
    assert result["aspect_ratio"] == "16:9"
    assert result["watermark_removed"] is False
    raw_source = pathlib.Path(result["storage_path"]).with_name(
        result["filename"].replace("flow_i2v_16_9_", "flow_source_16_9_", 1)
    )
    assert raw_source.read_bytes() == source.read_bytes()


def test_expand_fails_closed_when_watermark_remover_is_unavailable(monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    import subprocess

    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(video_processor_module, "veo_remover", None)

    with pytest.raises(RuntimeError, match="WATERMARK_REMOVER_UNAVAILABLE"):
        video_provider.video_processor.expand_16_9_to_9_16(
            source,
            tmp_path / "expanded.mp4",
            remove_watermark=True,
        )
