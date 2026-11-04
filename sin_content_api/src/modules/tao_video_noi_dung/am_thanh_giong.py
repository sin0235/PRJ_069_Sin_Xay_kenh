"""Chỉnh giọng TTS trước khi ghép video: bớt ồm, tăng độ rõ chữ, nén nhẹ, chống chạm trần.

Giọng VieNeu đo được (video bài 10): 99,9% năng lượng dưới 4,5 kHz, dải 3 đến 6 kHz thấp hơn dải giọng chính khoảng 27 dB, dải trên 12 kHz gần như trống
(nguồn 24 kHz nâng lên 48 kHz) nên nghe nghẹt và dính chữ. Chuỗi lọc dưới đây giữ nguyên độ dài (mốc từ, mốc shot không lệch) và chỉ đổi âm sắc,
độ nén và âm lượng. Tắt bằng biến môi trường CONTENT_VIDEO_VOICE_POLISH=0; ffmpeg lỗi thì trả giọng gốc (không làm hỏng lượt dựng)."""
from __future__ import annotations

import logging
import os
import subprocess

import numpy as np

logger = logging.getLogger(__name__)

# Lọc ồm (100 Hz trở xuống, 180 và 320 Hz), tăng độ rõ 3,2 kHz và độ sáng trên 6,5 kHz, nén nhẹ, giới hạn đỉnh, rồi đưa về khoảng -16 LUFS.
VOICE_POLISH_FILTER = (
    "highpass=f=100,"
    "equalizer=f=180:t=q:w=0.9:g=-3.5,"
    "equalizer=f=320:t=q:w=1.0:g=-2,"
    "equalizer=f=3200:t=q:w=0.9:g=5,"
    "highshelf=f=6500:g=3,"
    "acompressor=threshold=0.07:ratio=2.5:attack=6:release=140:makeup=1,"
    "volume=4dB,"
    "alimiter=limit=0.89:level=disabled,"
    "loudnorm=I=-16:TP=-1.5:LRA=9"
)


def polish_enabled() -> bool:
    return os.getenv("CONTENT_VIDEO_VOICE_POLISH", "1") != "0"


def polish_voice(audio, sample_rate: int, ffmpeg_bin: str | None = None) -> np.ndarray:
    """Trả mảng float32 một kênh cùng độ dài và cùng tần số lấy mẫu với đầu vào."""
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not polish_enabled() or samples.size == 0 or sample_rate <= 0:
        return samples
    if ffmpeg_bin is None:
        from src.modules.media_studio.video_processor import video_processor
        ffmpeg_bin = video_processor.ffmpeg_bin
    command = [ffmpeg_bin, "-v", "error", "-f", "f32le", "-ar", str(int(sample_rate)), "-ac", "1", "-i", "pipe:0",
               "-af", VOICE_POLISH_FILTER, "-ar", str(int(sample_rate)), "-ac", "1", "-f", "f32le", "pipe:1"]
    try:
        result = subprocess.run(command, input=samples.astype("<f4").tobytes(), capture_output=True, timeout=600)
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError((result.stderr or b"").decode("utf-8", "replace")[-200:])
        out = np.frombuffer(result.stdout, dtype="<f4").astype(np.float32)
        if not np.isfinite(out).all():
            raise RuntimeError("VOICE_POLISH_NOT_FINITE")
    except Exception:
        logger.warning("VOICE_POLISH_FAILED_USING_RAW_TTS", exc_info=True)
        return samples
    if out.size < samples.size:
        out = np.pad(out, (0, samples.size - out.size))
    return np.clip(out[:samples.size], -1.0, 1.0)
