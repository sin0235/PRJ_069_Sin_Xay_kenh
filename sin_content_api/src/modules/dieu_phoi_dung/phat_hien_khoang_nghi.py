from __future__ import annotations

import re
import struct
import wave
from pathlib import Path

from src.media_process import run_media_command
from src.modules.media_studio.video_processor import video_processor


_SILENCE_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


def phat_hien_khoang_nghi(audio_path: Path) -> list[tuple[int, int]]:
    try:
        with wave.open(str(audio_path), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() <= 0:
                raise ValueError("SILENCE_AUDIO_FORMAT_UNSUPPORTED")
            duration_ms = round(audio.getnframes() * 1000 / audio.getframerate())
    except (EOFError, OSError, wave.Error) as exc:
        raise ValueError("SILENCE_AUDIO_INVALID") from exc

    result = run_media_command(
        [video_processor.ffmpeg_bin, "-hide_banner", "-i", str(audio_path), "-af", "silencedetect=noise=-35dB:d=1.2", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        raise ValueError("SILENCE_DETECTION_FAILED")

    intervals: list[tuple[int, int]] = []
    pending_start: int | None = None
    for line in result.stderr.splitlines():
        start_match = _SILENCE_START.search(line)
        end_match = _SILENCE_END.search(line)
        if start_match:
            pending_start = max(0, round(float(start_match.group(1)) * 1000))
        if end_match and pending_start is not None:
            end_ms = min(duration_ms, round(float(end_match.group(1)) * 1000))
            if end_ms - pending_start >= 1200:
                intervals.append((pending_start, end_ms))
            pending_start = None
    if pending_start is not None and duration_ms - pending_start >= 1200:
        intervals.append((pending_start, duration_ms))
    return intervals


def hop_nhat_khoang_nghi(
    words: list[dict], audio_silences: list[tuple[int, int]], source_duration_ms: int,
) -> list[tuple[int, int]]:
    if source_duration_ms <= 0:
        raise ValueError("SOURCE_DURATION_INVALID")
    intervals = []
    for start, end in audio_silences:
        start, end = max(0, start), min(source_duration_ms, end)
        if end - start >= 1200:
            intervals.append((start, end))
    ordered_words = sorted(words, key=lambda word: int(word["start_ms"]))
    for left, right in zip(ordered_words, ordered_words[1:]):
        start, end = int(left["end_ms"]), int(right["start_ms"])
        start, end = max(0, start), min(source_duration_ms, end)
        if end - start >= 1200:
            intervals.append((start, end))
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def tinh_muc_song(audio_path: Path) -> list[int]:
    try:
        with wave.open(str(audio_path), "rb") as audio:
            channels, width, rate = audio.getnchannels(), audio.getsampwidth(), audio.getframerate()
            if channels != 1 or width != 2 or rate <= 0:
                raise ValueError("WAVE_FORMAT_UNSUPPORTED")
            frames_per_peak = max(1, rate // 10)
            peaks = []
            while raw := audio.readframes(frames_per_peak):
                samples = struct.unpack(f"<{len(raw) // 2}h", raw)
                peaks.append(round(max(map(abs, samples), default=0) * 100 / 32767))
            return peaks
    except (OSError, wave.Error, struct.error) as exc:
        raise ValueError("WAVE_AUDIO_INVALID") from exc
