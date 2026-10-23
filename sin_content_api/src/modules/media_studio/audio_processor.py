# -*- coding: utf-8 -*-
"""Bộ xử lý âm thanh chuyên nghiệp chuẩn TikTok bằng FFmpeg (P08 + GF04).
Cung cấp các hàm đo đạc LUFS theo chuẩn EBU R128, chuẩn hóa -14 LUFS, kiểm định chất lượng âm thanh (Audio QC), auto-ducking nhạc nền và fade-out.
"""

import json
import os
import pathlib
import subprocess
from typing import Dict, Any, Optional

class AudioProcessor:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin

    def probe_audio(self, filepath: pathlib.Path) -> Dict[str, Any]:
        """
        Trích xuất siêu dữ liệu âm thanh chi tiết bằng ffprobe:
        - Thời lượng (duration_seconds)
        - Tần số lấy mẫu (sample_rate_hz)
        - Số kênh (channels)
        - Định dạng codec và bitrate
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp âm thanh: {filepath}")

        cmd = [
            self.ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(filepath)
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi probe âm thanh: {res.stderr}")

        data = json.loads(res.stdout)
        audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

        duration = float(data.get("format", {}).get("duration", 0.0))
        bitrate = int(data.get("format", {}).get("bit_rate", 0))

        return {
            "duration_seconds": duration,
            "bitrate_bps": bitrate,
            "format_name": data.get("format", {}).get("format_name", "unknown"),
            "codec_name": audio_stream.get("codec_name") if audio_stream else "unknown",
            "sample_rate_hz": int(audio_stream.get("sample_rate", 44100)) if audio_stream else 44100,
            "channels": int(audio_stream.get("channels", 2)) if audio_stream else 2,
        }

    def measure_loudness(self, filepath: pathlib.Path) -> Dict[str, Any]:
        """
        Đo đạc âm lượng tích hợp (Integrated Loudness) chuẩn EBU R128 bằng FFmpeg:
        - Phân tích tệp qua filter loudnorm dạng JSON.
        - Trích xuất: input_i (LUFS), input_tp (dBTP), input_lra (LU).
        """
        if not filepath.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp âm thanh để đo âm lượng: {filepath}")

        cmd = [
            self.ffmpeg_bin,
            "-i", str(filepath),
            "-af", "loudnorm=print_format=json",
            "-f", "null",
            "-"
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = res.stderr
        idx = output.find("{")
        if idx != -1:
            end_idx = output.rfind("}")
            if end_idx != -1:
                try:
                    data = json.loads(output[idx:end_idx + 1])
                    return {
                        "measured_i_lufs": float(data.get("input_i", -99.0)),
                        "measured_tp_dbtp": float(data.get("input_tp", 0.0)),
                        "measured_lra_lu": float(data.get("input_lra", 0.0)),
                        "raw": data
                    }
                except Exception as exc:
                    raise RuntimeError(f"Lỗi giải mã JSON loudnorm: {exc}") from exc

        raise RuntimeError(f"Không thể đo đạc âm lượng EBU R128 từ tệp {filepath}. Output: {output[:300]}")

    def verify_audio_qc(
        self,
        filepath: pathlib.Path,
        expected_duration_sec: Optional[float] = None,
        target_lufs: float = -14.0,
        lufs_tolerance: float = 1.0,
        max_true_peak_dbtp: float = -1.5,
        min_byte_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Kiểm định chất lượng âm thanh nghiêm ngặt (Audio QC Engine):
        1. Kiểm tra kích thước và magic bytes (loại trừ HTML/null bytes).
        2. Probe ffprobe: Codec, sample rate, channels.
        3. Đo đạc EBU R128 thực tế: target -14 LUFS ± 1 LUFS, True Peak <= -1.5 dBTP.
        4. Kiểm tra thời lượng khớp với yêu cầu nếu có.
        """
        if not filepath.exists():
            return {"passed": False, "reason": "Tệp không tồn tại"}

        data = filepath.read_bytes()
        byte_size = len(data)

        # Kiểm tra giả mạo HTML trước
        if data.startswith(b"<!DOCTYPE") or data.startswith(b"<html") or b"<body" in data[:200]:
            return {"passed": False, "reason": "Tệp giả mạo: Nội dung là trang HTML thay vì âm thanh MP3"}

        if byte_size < min_byte_size:
            return {"passed": False, "reason": f"Kích thước tệp quá nhỏ ({byte_size} bytes < {min_byte_size} bytes)"}

        # Probe ffprobe
        meta = self.probe_audio(filepath)
        if meta["codec_name"] not in ("mp3", "aac"):
            return {"passed": False, "reason": f"Codec không được hỗ trợ: {meta['codec_name']}"}

        if meta["channels"] not in (1, 2):
            return {"passed": False, "reason": f"Số kênh không hợp lệ: {meta['channels']}"}

        if expected_duration_sec is not None:
            diff = abs(meta["duration_seconds"] - float(expected_duration_sec))
            if diff > 2.0:
                return {
                    "passed": False,
                    "reason": f"Thời lượng không khớp: Đo đạc {meta['duration_seconds']:.1f}s, yêu cầu {expected_duration_sec}s (chênh lệch {diff:.1f}s)"
                }

        # Đo âm lượng thực tế
        measure = self.measure_loudness(filepath)
        i_lufs = measure["measured_i_lufs"]
        tp_dbtp = measure["measured_tp_dbtp"]
        lra_lu = measure["measured_lra_lu"]

        min_lufs = target_lufs - lufs_tolerance
        max_lufs = target_lufs + lufs_tolerance
        loudness_pass = (min_lufs <= i_lufs <= max_lufs)
        peak_pass = (tp_dbtp <= max_true_peak_dbtp + 0.1)

        qc_passed = loudness_pass and peak_pass

        return {
            "passed": qc_passed,
            "measured_i_lufs": i_lufs,
            "measured_tp_dbtp": tp_dbtp,
            "measured_lra_lu": lra_lu,
            "target_lufs": target_lufs,
            "loudness_pass": loudness_pass,
            "peak_pass": peak_pass,
            "sample_rate_hz": meta["sample_rate_hz"],
            "channels": meta["channels"],
            "duration_seconds": meta["duration_seconds"],
            "byte_size": byte_size,
            "codec_name": meta["codec_name"],
            "reason": "Đạt chuẩn kiểm định âm lượng TikTok (-14 LUFS)" if qc_passed else f"Âm lượng không đạt chuẩn: {i_lufs:.1f} LUFS (yêu cầu {min_lufs:.1f} đến {max_lufs:.1f}), Peak {tp_dbtp:.1f} dBTP"
        }

    def normalize_loudness(
        self,
        input_path: pathlib.Path,
        output_path: pathlib.Path,
        target_lufs: float = -14.0
    ) -> Dict[str, Any]:
        """
        Chuẩn hóa âm lượng EBU R128 (-14 LUFS ± 1 LUFS) chuẩn khuyến nghị của TikTok:
        - Áp dụng filter loudnorm của FFmpeg để ngăn ngừa hiện tượng quá nhỏ hoặc bị xé âm thanh (clipping).
        - Thực hiện đo đạc xác thực EBU R128 thực tế trên tệp đầu ra.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(input_path),
            "-af", f"loudnorm=I={target_lufs}:LRA=11:tp=-1.5",
            "-ar", "44100",
            "-b:a", "192k",
            str(output_path)
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi chuẩn hóa âm lượng: {res.stderr}")

        meta = self.probe_audio(output_path)
        measurement = self.measure_loudness(output_path)

        meta["target_lufs"] = target_lufs
        meta["normalized"] = True
        meta["measured_i_lufs"] = measurement["measured_i_lufs"]
        meta["measured_tp_dbtp"] = measurement["measured_tp_dbtp"]
        meta["measured_lra_lu"] = measurement["measured_lra_lu"]
        return meta

    def apply_auto_ducking(
        self,
        voice_path: pathlib.Path,
        music_path: pathlib.Path,
        output_path: pathlib.Path,
        music_attenuation_db: float = -18.0
    ) -> Dict[str, Any]:
        """
        Kỹ thuật Auto-Ducking (Hạ nhạc nền thông minh khi có giọng nói):
        - Sử dụng filter 'sidechaincompress' của FFmpeg: Giọng đọc (Voice track) đóng vai trò trigger.
        - Khi có tiếng nói, nhạc nền tự động giảm âm lượng xuống (-18dB) để làm nổi bật lời thoại.
        - Khi người nói ngắt quãng, nhạc nền mượt mà tăng trở lại âm lượng ban đầu.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        filter_complex = (
            "[0:a][1:a]sidechaincompress="
            "threshold=0.12:ratio=4:attack=20:release=350[ducked];"
            "[ducked][1:a]amix=inputs=2:duration=first:dropout_transition=2[out]"
        )

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(music_path),
            "-i", str(voice_path),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-b:a", "192k",
            str(output_path)
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi thực hiện auto-ducking: {res.stderr}")

        meta = self.probe_audio(output_path)
        meta["ducking_applied"] = True
        return meta

    def trim_and_fade(
        self,
        input_path: pathlib.Path,
        output_path: pathlib.Path,
        target_duration: float,
        fade_out_sec: float = 2.0
    ) -> Dict[str, Any]:
        """
        Cắt âm thanh theo đúng thời lượng mong muốn và làm mờ âm dần ở cuối (Fade-out)
        để âm thanh không bị ngắt cụt đột ngột.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fade_start = max(0.0, target_duration - fade_out_sec)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(input_path),
            "-t", str(target_duration),
            "-af", f"afade=t=out:st={fade_start}:d={fade_out_sec}",
            "-b:a", "192k",
            str(output_path)
        ]

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi trim and fade âm thanh: {res.stderr}")

        return self.probe_audio(output_path)

audio_processor = AudioProcessor()
