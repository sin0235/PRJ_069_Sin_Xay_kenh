import subprocess

from src.modules.tao_video_noi_dung.render_engines import _normalize
from src.modules.media_studio.video_processor import video_processor


def test_chuan_hoa_h264_full_range_thanh_yuv420p_tv(tmp_path):
    source, output = tmp_path / "nguon.mp4", tmp_path / "ket_qua.mp4"
    subprocess.run([
        video_processor.ffmpeg_bin, "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=c=blue:s=64x96:r=30:d=0.2", "-an", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-color_range", "pc", str(source),
    ], check=True, capture_output=True)
    assert video_processor.probe_video(source)["pixel_format"] == "yuvj420p"

    meta = _normalize(source, output, 0.2)

    assert meta["pixel_format"] == "yuv420p"
    assert meta["frame_rate"] == 30
    assert abs(meta["duration_seconds"] - 0.2) < 1 / 30
    decoded = subprocess.run([video_processor.ffmpeg_bin, "-v", "error", "-i", str(output),
                              "-f", "null", "-"], capture_output=True)
    assert decoded.returncode == 0 and not decoded.stderr
