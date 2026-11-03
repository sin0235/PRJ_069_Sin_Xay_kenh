import shutil
import subprocess

import pytest

from src.modules.media_studio.video_processor import video_processor


def test_corner_mask_runs_with_real_ffmpeg_and_keeps_size_and_duration(tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("không có ffmpeg")
    src, dst = tmp_path / "flow.mp4", tmp_path / "sach.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=720x1280:r=24:d=1", "-pix_fmt", "yuv420p", str(src)], check=True)
    result = video_processor.mask_corner_watermark(src, dst)
    assert result["status"] == "SUCCEEDED" and result["watermark_removed"] is True and result["technique"] == "DELOGO_CORNER"
    assert (result["width"], result["height"]) == (720, 1280) and abs(float(result["duration_seconds"]) - 1.0) < 0.2


def test_remove_veo_watermark_falls_back_to_corner_mask_when_tool_does_not_confirm(monkeypatch, tmp_path):
    from src.modules.media_studio import video_processor as vp

    class Remover:
        def is_available(self):
            return True

        def remove_watermark(self, **_kwargs):
            return {"status": "FALLBACK_ORIGINAL", "watermark_removed": False, "message": "malloc(): corrupted top size"}

    calls = []
    monkeypatch.setattr(vp, "veo_remover", Remover())
    monkeypatch.setattr(vp.video_processor, "mask_corner_watermark",
                        lambda src, dst: calls.append((src.name, dst.name)) or {"status": "SUCCEEDED", "watermark_removed": True, "technique": "DELOGO_CORNER"})
    src, dst = tmp_path / "a.mp4", tmp_path / "b.mp4"
    src.write_bytes(b"x")
    result = vp.video_processor.remove_veo_watermark(src, dst, use_cpu=True)
    assert result["technique"] == "DELOGO_CORNER" and calls == [("a.mp4", "b.mp4")]


def test_remove_veo_watermark_falls_back_when_tool_raises(monkeypatch, tmp_path):
    from src.modules.media_studio import video_processor as vp

    class Remover:
        def is_available(self):
            return True

        def remove_watermark(self, **_kwargs):
            raise OSError("crash")

    monkeypatch.setattr(vp, "veo_remover", Remover())
    monkeypatch.setattr(vp.video_processor, "mask_corner_watermark", lambda src, dst: {"status": "SUCCEEDED", "watermark_removed": True})
    src, dst = tmp_path / "a.mp4", tmp_path / "b.mp4"
    src.write_bytes(b"x")
    assert vp.video_processor.remove_veo_watermark(src, dst)["watermark_removed"] is True
