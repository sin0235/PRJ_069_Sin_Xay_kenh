"""render_scene: engine HyperFrames lỗi kiểu nào cũng phải lùi sang Playwright để ra clip (trừ nền trong suốt)."""
import pytest

from src.modules.tao_video_noi_dung import render_engines
from src.modules.tao_video_noi_dung.planner import UiScene
from src.modules.tao_video_noi_dung.service import _CONTENT_VIDEO_STYLE_SNAPSHOT

SCENE = UiScene.model_validate({"layout": "BEFORE_AFTER", "diagram": {
    "title": "Đơn hàng", "simulated": False,
    "docs": [{"title": "Trước", "label": "Đơn", "value": "100"}, {"title": "Sau", "label": "Đơn", "value": "60"}],
    "diff_label": "Giảm 40", "on": {"before": "trước", "after": "sau", "delta": "giảm 40"},
}})
STYLE = _CONTENT_VIDEO_STYLE_SNAPSHOT.model_dump(mode="json")


@pytest.mark.parametrize("error", [ValueError("bad"), KeyError("k"), RuntimeError("r"), TimeoutError("t"), render_engines.EngineUnavailable("HYPERFRAMES_NOT_INSTALLED")])
def test_any_hyperframes_error_falls_back_to_playwright(monkeypatch, tmp_path, error):
    def boom(*_args):
        raise error
    monkeypatch.setattr(render_engines, "BACKENDS", {"hyperframes": boom})
    monkeypatch.setattr(render_engines, "render_ui_scene", lambda *_a, **_k: {"width": 1080})
    monkeypatch.delenv("CONTENT_VIDEO_RENDER_FALLBACK", raising=False)
    result = render_engines.render_scene(SCENE, STYLE, 5, "9:16", tmp_path / "d.mp4")
    assert result["render_engine"] == "playwright"


def test_transparent_background_still_raises(monkeypatch, tmp_path):
    def boom(*_args):
        raise ValueError("bad")
    monkeypatch.setattr(render_engines, "BACKENDS", {"hyperframes": boom})
    with pytest.raises(ValueError):
        render_engines.render_scene(SCENE, STYLE, 5, "9:16", tmp_path / "d.mov", transparent_background=True)


def test_fallback_can_be_disabled(monkeypatch, tmp_path):
    def boom(*_args):
        raise ValueError("bad")
    monkeypatch.setattr(render_engines, "BACKENDS", {"hyperframes": boom})
    monkeypatch.setenv("CONTENT_VIDEO_RENDER_FALLBACK", "0")
    with pytest.raises(ValueError):
        render_engines.render_scene(SCENE, STYLE, 5, "9:16", tmp_path / "d.mp4")


PROCESS_SCENE = UiScene.model_validate({"layout": "PROCESS_RAIL", "diagram": {
    "title": "Luồng xử lý", "steps": ["Nhận", "Duyệt", "Giao"], "block_step": 1,
    "on": {"stations": "nhận đơn", "block": "chờ duyệt", "release": "giao hàng"},
}})


def test_landscape_only_layout_in_portrait_is_rendered_wide_then_expanded(monkeypatch, tmp_path):
    calls = []

    def fake_inner(scene, style, seconds, ratio, out_path, **kwargs):
        calls.append(("inner", ratio, style.get("aspect_ratio")))
        out_path.write_bytes(b"x" * 100)
        return {"render_engine": "playwright"}

    def fake_expand(src, dst):
        calls.append(("expand", src.name))
        dst.write_bytes(b"y" * 100)

    monkeypatch.setattr(render_engines, "render_scene", fake_inner)
    monkeypatch.setattr(render_engines, "expand_landscape_to_portrait", fake_expand)
    monkeypatch.setattr(render_engines.video_processor, "probe_video", lambda _p: {"width": 1080, "height": 1920})
    # gọi bản gốc không qua monkeypatch của render_scene
    original = render_engines.__dict__["_landscape_scene_in_portrait"]
    meta = original(PROCESS_SCENE, STYLE, 5, tmp_path / "d.mp4", "nhận đơn chờ duyệt giao hàng", None)
    assert calls == [("inner", "16:9", "16:9"), ("expand", "ngang.mp4")]
    assert meta["expanded_from"] == "16:9" and meta["render_engine"] == "playwright"
    assert (meta["width"], meta["height"]) == (1080, 1920)


def test_render_scene_routes_landscape_layouts_in_portrait_to_expansion(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(render_engines, "_landscape_scene_in_portrait", lambda *args: seen.setdefault("args", args) and {"render_engine": "x"})
    result = render_engines.render_scene(PROCESS_SCENE, STYLE, 5, "9:16", tmp_path / "d.mp4", narration="nhận đơn")
    assert result == {"render_engine": "x"} and seen["args"][0] is PROCESS_SCENE


def test_portrait_layouts_are_not_expanded(monkeypatch, tmp_path):
    monkeypatch.setattr(render_engines, "_landscape_scene_in_portrait", lambda *a: (_ for _ in ()).throw(AssertionError("không được gọi")))
    monkeypatch.setattr(render_engines, "BACKENDS", {"hyperframes": lambda *_a: {"width": 1080}})
    assert render_engines.render_scene(SCENE, STYLE, 5, "9:16", tmp_path / "d.mp4")["render_engine"] == "hyperframes"


def test_expand_landscape_to_portrait_with_real_ffmpeg(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        pytest.skip("không có ffmpeg")
    src = tmp_path / "ngang.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=1", "-pix_fmt", "yuv420p", str(src)], check=True)
    dst = tmp_path / "doc.mp4"
    render_engines.expand_landscape_to_portrait(src, dst)
    info = render_engines.video_processor.probe_video(dst)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert abs(float(info["duration_seconds"]) - 1.0) < 0.15


def test_expand_falls_back_to_blur_when_reflection_filter_fails(monkeypatch, tmp_path):
    calls = []

    def reflection_boom(src, dst):
        calls.append("reflection")
        dst.write_bytes(b"partial")
        raise RuntimeError("VIDEO_EXPAND_PORTRAIT_FAILED: gradients")

    def blur(input_video_path, output_video_path, remove_watermark=True, **_kwargs):
        calls.append(("blur", remove_watermark))
        output_video_path.write_bytes(b"ok")

    monkeypatch.setattr(render_engines, "expand_landscape_to_portrait", reflection_boom)
    monkeypatch.setattr(render_engines.video_processor, "expand_16_9_to_9_16", blur)
    src, dst = tmp_path / "a.mp4", tmp_path / "b.mp4"
    src.write_bytes(b"x")
    assert render_engines._expand_with_fallback(src, dst) == "blur"
    assert calls == ["reflection", ("blur", False)] and dst.read_bytes() == b"ok"


def test_unexpected_landscape_errors_get_a_short_readable_code(monkeypatch, tmp_path):
    def inner_boom(*_a, **_k):
        raise KeyError("thiếu trường x")

    monkeypatch.setattr(render_engines, "render_scene", inner_boom)
    with pytest.raises(RuntimeError, match=r"^VIDEO_LANDSCAPE_IN_PORTRAIT_FAILED: KeyError"):
        render_engines._landscape_scene_in_portrait(PROCESS_SCENE, STYLE, 5, tmp_path / "d.mp4", "nhận đơn", None)
