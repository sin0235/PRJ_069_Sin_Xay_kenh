"""Phát hiện và che biểu tượng ngôi sao bán trong suốt còn sót sau khi công cụ khử logo báo thành công (đã gặp ở shot 7 bài 10)."""
import subprocess

import numpy as np
import pytest

from src.modules.media_studio.video_processor import video_processor

W, H, FPS, SECONDS = 960, 540, 10, 4


def _hinh_ngoi_sao(radius: float) -> np.ndarray:
    """Mặt nạ ngôi sao bốn cánh lõm (astroid): |x|^(2/3) + |y|^(2/3) <= r^(2/3)."""
    size = int(radius * 2 + 4)
    y, x = np.mgrid[:size, :size] - size / 2
    mask = (np.abs(x) ** (2 / 3) + np.abs(y) ** (2 / 3)) <= radius ** (2 / 3)
    full = np.zeros((H, W), dtype=bool)
    cx, cy = int(W * 0.905), int(H * 0.835)
    full[cy - size // 2:cy - size // 2 + size, cx - size // 2:cx - size // 2 + size] = mask
    return full


def _ghi_video(path, co_logo: bool):
    """Nền chuyển động (các mảng sáng tối trôi đi) và, khi co_logo, ngôi sao trắng alpha 0,25 đứng yên."""
    rng = np.random.default_rng(3)
    base = rng.uniform(60, 200, size=(H + 80, W + 400)).astype(np.float32)
    kernel = np.ones(25, dtype=np.float32) / 25
    base = np.apply_along_axis(lambda row: np.convolve(row, kernel, "same"), 1, base)
    base = np.apply_along_axis(lambda col: np.convolve(col, kernel, "same"), 0, base)
    star = _hinh_ngoi_sao(36)
    process = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "14", str(path)], stdin=subprocess.PIPE)
    for index in range(FPS * SECONDS):
        offset = index * 7
        frame = base[20:20 + H, offset % 380:offset % 380 + W].copy()
        if co_logo:
            frame[star] = frame[star] * 0.75 + 255 * 0.25
        process.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    process.stdin.close()
    assert process.wait() == 0


def test_phat_hien_logo_con_sot_o_goc_duoi_phai(tmp_path):
    clip = tmp_path / "co_logo.mp4"
    _ghi_video(clip, co_logo=True)
    box = video_processor.residual_watermark_box(clip)
    assert box is not None
    x, y, w, h = box
    assert x <= int(W * 0.905) <= x + w and y <= int(H * 0.835) <= y + h


def test_clip_sach_khong_bi_dong_cham(tmp_path):
    clip = tmp_path / "sach.mp4"
    _ghi_video(clip, co_logo=False)
    assert video_processor.residual_watermark_box(clip) is None
    before = clip.read_bytes()
    assert video_processor.clear_residual_watermark(clip) is None
    assert clip.read_bytes() == before


def test_che_logo_con_sot_giu_nguyen_do_dai_va_kich_thuoc(tmp_path):
    clip = tmp_path / "co_logo.mp4"
    _ghi_video(clip, co_logo=True)
    before = video_processor.probe_video(clip)
    assert video_processor.clear_residual_watermark(clip)
    after = video_processor.probe_video(clip)
    assert (after["width"], after["height"]) == (before["width"], before["height"])
    assert abs(after["duration_seconds"] - before["duration_seconds"]) < 0.3
