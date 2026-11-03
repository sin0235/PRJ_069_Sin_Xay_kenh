# -*- coding: utf-8 -*-
"""Bộ xử lý và kiểm định Video Dọc 9:16 chuẩn TikTok bằng FFmpeg (P09 + GF02/GF03).
Hỗ trợ mở rộng video 16:9 sang 9:16 (Blurred Canvas Extension), kiểm tra tỷ lệ 9:16,
Safe Zone, ghép video phân cảnh, track âm thanh và tẩy sạch watermark Google Veo / Gemini AI.
"""

from src.modules.tac_vu_tu_xa.client import offload, pipeline
import logging
import json
import math
import os
import pathlib
import subprocess
from src.media_process import run_media_command
import sys
import threading
import uuid
import shutil
import textwrap
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)
from .ass_captions import build_karaoke_ass

VIETSUB_FONT_PATH = pathlib.Path(__file__).resolve().parent / "assets" / "fonts" / "be_vietnam_pro_semibold.ttf"

# Hình được co giãn tốc độ để dài đúng bằng giọng; ngoài khoảng này chuyển động hết tự nhiên nên chỉ kẹp tới biên và QC báo lệch.
VOICE_SPEED_MIN = 0.85
VOICE_SPEED_MAX = 1.35


def fit_voice_speed(video_seconds: float, voice_seconds: float) -> float:
    """Tốc độ phát hình để dài bằng giọng; dùng chung cho renderer và mốc phụ đề để hai nơi không lệch nhau."""
    return min(VOICE_SPEED_MAX, max(VOICE_SPEED_MIN, video_seconds / voice_seconds))

# Nạp công cụ tẩy watermark Veo từ cong_cu_tu_dong
BAN_LAM_VIEC = pathlib.Path(__file__).resolve().parents[4]
CONG_CU_TU_DONG = BAN_LAM_VIEC / "cong_cu_tu_dong"
if str(CONG_CU_TU_DONG) not in sys.path:
    sys.path.insert(0, str(CONG_CU_TU_DONG))

try:
    from veo_watermark_remover import veo_remover
except (ImportError, FileNotFoundError):
    veo_remover = None

class VideoProcessor:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self._render_lock = threading.Lock()


    def probe_video(self, filepath: pathlib.Path) -> Dict[str, Any]:
        """Trích xuất thông số kỹ thuật của video bằng ffprobe."""
        if not filepath.exists():
            raise FileNotFoundError(f"Không tìm thấy video: {filepath}")

        cmd = [
            self.ffprobe_bin,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(filepath)
        ]

        res = run_media_command(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi probe video: {res.stderr}")

        data = json.loads(res.stdout)
        v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)

        if not v_stream:
            raise ValueError("Tệp không chứa luồng video hợp lệ.")

        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))
        pixel_format = v_stream.get("pix_fmt") or ""
        has_alpha = "a" in pixel_format or any(
            key.casefold() == "alpha_mode" and str(value) == "1"
            for key, value in (v_stream.get("tags") or {}).items()
        )
        duration = float(data.get("format", {}).get("duration", 0.0))
        rate = v_stream.get("avg_frame_rate") or v_stream.get("r_frame_rate") or "0/1"
        try:
            rate_num, rate_den = rate.split("/", 1)
            frame_rate = int(rate_num) / int(rate_den) if int(rate_den) else 0.0
        except (ValueError, ZeroDivisionError):
            frame_rate = 0.0

        # Tính tỷ lệ khung hình
        aspect_ratio = f"{width}:{height}"
        is_vertical_9_16 = False
        if height > 0:
            ratio = width / height
            # 9:16 = 0.5625 (cho phép sai số 5%)
            if 0.53 <= ratio <= 0.60:
                is_vertical_9_16 = True

        return {
            "width": width,
            "height": height,
            "duration_seconds": duration,
            "video_stream_duration_seconds": float(v_stream.get("duration") or duration),
            "codec_name": v_stream.get("codec_name"),
            "pixel_format": v_stream.get("pix_fmt"),
            "has_alpha": has_alpha,
            "frame_rate": frame_rate,
            "aspect_ratio": "9:16" if is_vertical_9_16 else aspect_ratio,
            "is_vertical_9_16": is_vertical_9_16,
            "bitrate_bps": int(data.get("format", {}).get("bit_rate", 0)),
            "safe_zone_tiktok": {
                "top_margin_px": 150,
                "bottom_margin_px": 320,
                "right_margin_px": 120,
                "is_compliant": is_vertical_9_16
            }
        }

    @offload("mask_corner_watermark", "PREPARE_FLOW_ASSET", output="output_video_path")
    def mask_corner_watermark(self, input_video_path: pathlib.Path, output_video_path: pathlib.Path) -> Dict[str, Any]:
        """Đường lùi khi công cụ khử logo lỗi: xóa biểu tượng ở góc dưới phải bằng bộ lọc delogo của ffmpeg (nội suy từ vùng xung quanh)."""
        info = self.probe_video(input_video_path)
        width, height = int(info["width"]), int(info["height"])
        box_x, box_y = int(width * 0.79), int(height * 0.88)
        box_w, box_h = min(int(width * 0.10), width - box_x - 2), min(int(height * 0.07), height - box_y - 2)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        result = run_media_command([
            self.ffmpeg_bin, "-y", "-v", "error", "-i", str(input_video_path),
            "-vf", f"delogo=x={box_x}:y={box_y}:w={box_w}:h={box_h}",
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "copy", str(output_video_path),
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("VIDEO_DELOGO_FAILED: " + " ".join((result.stderr or "").split())[-100:])
        meta = self.probe_video(output_video_path)
        return {**meta, "status": "SUCCEEDED", "watermark_removed": True, "technique": "DELOGO_CORNER"}

    @offload("remove_watermark", "PREPARE_FLOW_ASSET", output="output_video_path")
    def remove_veo_watermark(
        self,
        input_video_path: pathlib.Path,
        output_video_path: pathlib.Path,
        use_cpu: bool = True,
        watermark_type: str = "auto",
        denoise_method: Optional[str] = None,
        region: Optional[str] = None,
        veo_alpha: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Khử sạch logo / watermark Google Veo & Gemini AI khỏi video bằng công cụ chuyên dụng.
        """
        if veo_remover and veo_remover.is_available():
            try:
                result = veo_remover.remove_watermark(
                    input_video_path=input_video_path,
                    output_video_path=output_video_path,
                    use_cpu=use_cpu,
                    watermark_type=watermark_type,
                    denoise_method=denoise_method,
                    region=region,
                    veo_alpha=veo_alpha
                )
            except Exception as exc:
                print(f"[VIDEO PROCESSOR] Công cụ khử logo lỗi ({type(exc).__name__}); dùng delogo che góc.", flush=True)
                result = {}
            if result.get("status") != "SUCCEEDED" or not result.get("watermark_removed"):
                # Công cụ khử logo lỗi hoặc không xác nhận (vd. crash trên clip dọc 720x1280): che góc bằng delogo thay vì làm hỏng cả run.
                print(f"[VIDEO PROCESSOR] Khử logo không xác nhận ({str(result.get('message') or result.get('status'))[:120]}); dùng delogo che góc.", flush=True)
                output_video_path.unlink(missing_ok=True)
                return self.mask_corner_watermark(input_video_path, output_video_path)
            if result.get("status") == "SUCCEEDED" and result.get("watermark_removed"):
                input_duration = self.probe_video(input_video_path)["duration_seconds"]
                output_duration = self.probe_video(output_video_path)["duration_seconds"]
                if abs(input_duration - output_duration) > 0.5:
                    raise RuntimeError(
                        "WATERMARK_OUTPUT_DURATION_MISMATCH: "
                        f"source={input_duration:.3f}s output={output_duration:.3f}s"
                    )
            return result
        else:
            raise RuntimeError("Công cụ VeoWatermarkRemover chưa sẵn sàng trên hệ thống.")

    @offload("expand_canvas", "PREPARE_FLOW_ASSET", output="output_video_path")
    def expand_16_9_to_9_16(
        self,
        input_video_path: pathlib.Path,
        output_video_path: pathlib.Path,
        blur_strength: int = 25,
        remove_watermark: bool = True
    ) -> Dict[str, Any]:
        """
        Mở rộng video gốc 16:9 thành video dọc 9:16 (1080x1920) chuẩn TikTok:
        - Tự động khử sạch watermark / logo Veo trước khi mở rộng nếu remove_watermark=True.
        - Layer nền: Phóng to video 16:9 để phủ kín 1080x1920, áp dụng Gaussian Blur mềm mại và hạ độ sáng nhẹ.
        - Layer chính: Đặt trọn vẹn video 16:9 sắc nét ở trung tâm (1080x608), không bị méo, không bị crop mất nội dung.
        - Giữ trọn âm thanh gốc nếu có.
        """
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        if not input_video_path.exists():
            raise FileNotFoundError(f"Không tìm thấy video 16:9 nguồn: {input_video_path}")
        if remove_watermark and (not veo_remover or not veo_remover.is_available()):
            raise RuntimeError("WATERMARK_REMOVER_UNAVAILABLE: Không thể xuất video khi chưa có công cụ xử lý watermark.")

        effective_input = input_video_path
        clean_temp_path = None
        watermark_removed = False

        # Tự động tẩy watermark Veo khỏi video nguồn trước khi áp dụng hiệu ứng mở rộng
        if remove_watermark and veo_remover and veo_remover.is_available():
            clean_temp_path = output_video_path.parent / f"clean_source_{output_video_path.stem}.mp4"
            try:
                print(f"[VIDEO PROCESSOR] Tự động khử logo Veo khỏi nguồn 16:9 trước khi mở rộng...", flush=True)
                clean_res = self.remove_veo_watermark(
                    input_video_path=input_video_path,
                    output_video_path=clean_temp_path,
                    use_cpu=True
                )
                if clean_res.get("status") != "SUCCEEDED" or not clean_res.get("watermark_removed"):
                    raise RuntimeError("WATERMARK_REMOVAL_FAILED: Công cụ không xác nhận đã loại bỏ watermark.")
                if not clean_temp_path.exists() or clean_temp_path.stat().st_size == 0:
                    raise RuntimeError("WATERMARK_OUTPUT_MISSING: Công cụ không tạo video đã xử lý.")
                effective_input = clean_temp_path
                watermark_removed = True
                print("[VIDEO PROCESSOR] Đã tẩy logo Veo thành công.", flush=True)
            except Exception as w_err:
                if remove_watermark:
                    raise RuntimeError(f"WATERMARK_REMOVAL_FAILED: {w_err}") from w_err
                print(f"[VIDEO PROCESSOR CẢNH BÁO] Không thể khử watermark: {w_err}", flush=True)

        filter_complex = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur={blur_strength}:5,eq=brightness=-0.08:contrast=1.05[bg];"
            f"[0:v]scale=1080:-1[fg];"
            f"[bg][fg]overlay=0:(H-h)/2[v]"
        )

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(effective_input),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            str(output_video_path)
        ]

        res = run_media_command(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi mở rộng video 16:9 sang 9:16: {res.stderr}")

        # Dọn dẹp tệp tạm sạch sau khi render xong nếu có
        if clean_temp_path and clean_temp_path.exists() and clean_temp_path != input_video_path:
            try:
                clean_temp_path.unlink()
            except Exception:
                pass

        probed = self.probe_video(output_video_path)
        probed["watermark_removed"] = watermark_removed
        return probed

    def assemble_scenes_with_audio(
        self,
        scene_video_paths: List[pathlib.Path],
        audio_path: pathlib.Path,
        output_path: pathlib.Path
    ) -> Dict[str, Any]:
        """
        Ghép chuỗi video phân cảnh cùng với bản âm thanh lồng tiếng vào tệp MP4 dọc 9:16 hoàn chỉnh.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not scene_video_paths:
            raise ValueError("Danh sách video phân cảnh không được rỗng.")

        concat_txt = output_path.parent / f"concat_{output_path.stem}.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in scene_video_paths:
                clean_p = str(p.resolve()).replace("\\", "/")
                f.write(f"file '{clean_p}'\n")

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(output_path)
        ]

        res = run_media_command(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if concat_txt.exists():
            concat_txt.unlink()

        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi assemble video: {res.stderr}")

        return self.probe_video(output_path)

    @offload("render_timeline", "RENDER_FINAL", output="output_path")
    def render_timeline_document(
        self,
        timeline: Any,
        asset_path_resolver: Any,
        output_path: pathlib.Path,
        temp_dir: Optional[pathlib.Path] = None,
        transition_seconds: float = 0.0,
        caption_style: str = "legacy",
        preserve_voice_audio: bool = False,
        sfx_cues: list[dict] | None = None,
    ) -> Dict[str, Any]:
        """
        Render toàn diện video MP4 từ timeline document (M-P5):
        - Concurrency = 1 (quản lý bằng threading.Lock).
        - Chuẩn hóa ảnh tĩnh thành clip đúng duration.
        - Chuẩn hóa video: trim in/out, fit (cover/contain), 1080x1920, 30fps.
        - Ghép chuỗi phân cảnh không gián đoạn.
        - Burn-in caption tiếng Việt vào TikTok Safe Zone.
        - Trộn voice và music với auto-ducking.
        - Chuẩn hóa âm lượng đầu ra -14 LUFS ± 1 LUFS theo EBU R128.
        - Không sử dụng -shortest gây cắt cụt video.
        """
        with self._render_lock:
            if caption_style not in {"legacy", "vietsub_v1", "vietsub_karaoke_v2"}:
                raise ValueError("CAPTION_STYLE_UNSUPPORTED")
            sfx_cues = list(sfx_cues or [])
            for cue in sfx_cues:
                if (not pathlib.Path(cue["path"]).is_file()
                        or not math.isfinite(float(cue["start_seconds"])) or float(cue["start_seconds"]) < 0
                        or not math.isfinite(float(cue["volume"])) or not 0 <= float(cue["volume"]) <= 1):
                    raise ValueError("SFX_CUE_INVALID")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            clips = getattr(timeline, "clips", [])
            if not clips and isinstance(timeline, dict):
                clips = timeline.get("clips", [])
            if not clips:
                raise ValueError("Timeline không có phân cảnh (clips) nào để kết xuất.")

            width = getattr(timeline, "width", None) or (timeline.get("width") if isinstance(timeline, dict) else None) or 1080
            height = getattr(timeline, "height", None) or (timeline.get("height") if isinstance(timeline, dict) else None) or 1920
            fps = getattr(timeline, "fps", None) or (timeline.get("fps") if isinstance(timeline, dict) else None) or 30

            work_dir = temp_dir or (output_path.parent / f"render_tmp_{uuid.uuid4().hex[:8]}")
            work_dir.mkdir(parents=True, exist_ok=True)

            try:
                # 1. Render từng phân cảnh thành clip tạm chuẩn hóa
                seg_files = []
                seg_durations = []
                native_audio_specs = []
                total_duration_sec = 0.0

                for idx, clip in enumerate(clips):
                    clip_id = getattr(clip, "clip_id", None) or (clip.get("clip_id") if isinstance(clip, dict) else f"c{idx}")
                    asset_id = getattr(clip, "asset_id", None) or (clip.get("asset_id") if isinstance(clip, dict) else "")
                    media_type = getattr(clip, "media_type", "video")
                    if hasattr(media_type, "value"):
                        media_type = media_type.value
                    elif isinstance(clip, dict):
                        media_type = clip.get("media_type", "video")

                    duration_ms = getattr(clip, "duration_ms", 3000) or (clip.get("duration_ms", 3000) if isinstance(clip, dict) else 3000)
                    trim_in_ms = getattr(clip, "trim_in_ms", 0) or (clip.get("trim_in_ms", 0) if isinstance(clip, dict) else 0)
                    trim_out_ms = getattr(clip, "trim_out_ms", 0) or (clip.get("trim_out_ms", 0) if isinstance(clip, dict) else 0)
                    fit = getattr(clip, "fit", "cover")
                    if hasattr(fit, "value"):
                        fit = fit.value
                    elif isinstance(clip, dict):
                        fit = clip.get("fit", "cover")
                    effect = clip.get("effect", "none") if isinstance(clip, dict) else getattr(clip, "effect", "none")
                    if effect not in {None, "none", "punch_in"}:
                        raise ValueError("VIDEO_EFFECT_UNSUPPORTED")

                    asset_file = asset_path_resolver(asset_id)
                    if not asset_file.exists():
                        raise FileNotFoundError(f"Không tìm thấy file nguồn của asset {asset_id}: {asset_file}")

                    seg_out = work_dir / f"seg_{idx:03d}_{clip_id}.mp4"
                    audio_asset_id = clip.get("audio_asset_id", asset_id) if isinstance(clip, dict) else asset_id
                    audio_file = asset_path_resolver(audio_asset_id)
                    audio_trim_ms = clip.get("audio_trim_in_ms", trim_in_ms) if isinstance(clip, dict) else trim_in_ms

                    if fit == "contain":
                        vf_scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
                    else:
                        vf_scale = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}"
                    if effect == "punch_in":
                        zoom_width, zoom_height = round(width * 1.06), round(height * 1.06)
                        vf_scale += f",scale={zoom_width}:{zoom_height},crop={width}:{height}"

                    if media_type == "image":
                        dur_s = max(0.1, duration_ms / 1000.0)
                        cmd = [
                            self.ffmpeg_bin, "-y",
                            "-loop", "1",
                            "-t", f"{dur_s:.3f}",
                            "-i", str(asset_file),
                            "-vf", vf_scale,
                            "-c:v", "libx264",
                            "-pix_fmt", "yuv420p",
                            "-r", str(fps),
                            str(seg_out)
                        ]
                        res = run_media_command(cmd, capture_output=True, text=True)
                        if res.returncode != 0:
                            raise RuntimeError(f"Lỗi render phân cảnh ảnh {clip_id}: {res.stderr}")
                        seg_files.append(seg_out)
                        seg_durations.append(dur_s)
                        native_audio_specs.append((audio_file, "video" if audio_asset_id != asset_id else media_type,
                                                   audio_trim_ms / 1000.0, dur_s))
                        total_duration_sec += dur_s
                    else:
                        in_s = trim_in_ms / 1000.0
                        if trim_out_ms and trim_out_ms > trim_in_ms:
                            dur_s = (trim_out_ms - trim_in_ms) / 1000.0
                        else:
                            dur_s = duration_ms / 1000.0

                        # Kiểm tra nguồn video không bị trim out vượt thời lượng thực
                        try:
                            src_probe = self.probe_video(asset_file)
                            src_dur_s = src_probe.get("duration_seconds")
                            if src_dur_s and src_dur_s > 0 and trim_out_ms:
                                if (trim_out_ms / 1000.0) > (src_dur_s + 0.05):
                                    raise RuntimeError(
                                        f"Clip {clip_id}: Điểm ra trim_out_ms ({trim_out_ms}ms) vượt quá thời lượng thực tế của video nguồn ({int(src_dur_s * 1000)}ms)."
                                    )
                        except Exception as probe_err:
                            if "Điểm ra trim_out_ms" in str(probe_err):
                                raise
                            logger.warning(f"Không thể thăm dò video nguồn {asset_file}: {probe_err}")
                        cmd = [
                            self.ffmpeg_bin, "-y",
                            "-ss", f"{in_s:.3f}",
                            "-t", f"{dur_s:.3f}",
                            "-i", str(asset_file),
                            "-vf", vf_scale,
                            "-an",
                            "-c:v", "libx264",
                            "-pix_fmt", "yuv420p",
                            "-r", str(fps),
                            str(seg_out)
                        ]
                        res = run_media_command(cmd, capture_output=True, text=True)
                        if res.returncode != 0:
                            raise RuntimeError(f"Lỗi render phân cảnh video {clip_id}: {res.stderr}")
                        seg_files.append(seg_out)
                        seg_durations.append(dur_s)
                        native_audio_specs.append((audio_file, "video" if audio_asset_id != asset_id else media_type,
                                                   audio_trim_ms / 1000.0, dur_s))
                        total_duration_sec += dur_s

                # 2. Ghép các phân cảnh video. Mỗi đoạn (trừ đoạn cuối) được tpad ngay trên đầu vào để xfade
                # còn đủ hình; tpad đặt sau xfade không kéo dài luồng nên các đoạn sau bị cắt mất.
                if transition_seconds > 0 and len(seg_files) > 1:
                    transition = min(transition_seconds, 0.5)
                    # Offset phải theo độ dài thực của đoạn (có thể ngắn hơn danh nghĩa vài frame), nếu không xfade bị cắt.
                    measured = [float(self.probe_video(seg)["duration_seconds"]) for seg in seg_files]
                    last = len(seg_files) - 1
                    filter_parts = [
                        f"[{idx}:v]tpad=stop_mode=clone:stop_duration={transition:.3f}[p{idx}]"
                        for idx in range(last)
                    ]
                    previous = "p0"
                    offset = 0.0
                    for idx, duration in enumerate(measured[:-1]):
                        nxt = f"p{idx + 1}" if idx + 1 < last else f"{last}:v"
                        output = f"x{idx}"
                        filter_parts.append(
                            f"[{previous}][{nxt}]xfade=transition=fade:duration={transition:.3f}:offset={offset + duration:.3f}[{output}]"
                        )
                        previous = output
                        offset += duration
                    concat_video = work_dir / "concat_video.mp4"
                    cmd_transition = [self.ffmpeg_bin, "-y"]
                    for seg_file in seg_files:
                        cmd_transition.extend(["-i", str(seg_file)])
                    cmd_transition.extend([
                        "-filter_complex", ";".join(filter_parts), "-map", f"[{previous}]",
                        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(concat_video),
                    ])
                    res_concat = run_media_command(cmd_transition, capture_output=True, text=True)
                    if res_concat.returncode != 0:
                        raise RuntimeError(f"Lỗi chuyển cảnh mềm: {res_concat.stderr}")
                else:
                    concat_list = work_dir / "concat_list.txt"
                    with open(concat_list, "w", encoding="utf-8") as f:
                        for s in seg_files:
                            p_str = str(s.resolve()).replace("\\", "/")
                            f.write(f"file '{p_str}'\n")

                    concat_video = work_dir / "concat_video.mp4"
                    cmd_concat = [
                        self.ffmpeg_bin, "-y",
                        "-f", "concat",
                        "-safe", "0",
                        "-i", str(concat_list),
                        "-c", "copy",
                        str(concat_video)
                    ]
                    res_concat = run_media_command(cmd_concat, capture_output=True, text=True)
                    if res_concat.returncode != 0:
                        raise RuntimeError(f"Lỗi ghép phân cảnh: {res_concat.stderr}")

                # 3. Phụ đề Captions (Burn-in text vào Safe Zone)
                captions = getattr(timeline, "captions", [])
                if not captions and isinstance(timeline, dict):
                    captions = timeline.get("captions", [])
                karaoke_captions, static_captions = [], []
                for caption in captions:
                    words = caption.get("words") if isinstance(caption, dict) else getattr(caption, "words", None)
                    animated_label = caption.get("animated_label", False) if isinstance(caption, dict) else getattr(caption, "animated_label", False)
                    (karaoke_captions if words or animated_label else static_captions).append(caption)

                current_video = concat_video
                overlays = getattr(timeline, "overlays", [])
                if isinstance(timeline, dict):
                    overlays = timeline.get("overlays", [])
                if overlays:
                    overlay_inputs = []
                    filters = ["[0:v]null[base]"]
                    previous = "base"
                    for index, overlay in enumerate(overlays):
                        overlay_file = asset_path_resolver(overlay["asset_id"])
                        overlay_inputs.extend(["-i", str(overlay_file)])
                        width_px, height_px = int(overlay.get("width", 320)), int(overlay.get("height", 480))
                        start_s = int(overlay["start_ms"]) / 1000
                        end_s = start_s + int(overlay["duration_ms"]) / 1000
                        trim_s = int(overlay.get("trim_in_ms", 0)) / 1000
                        next_label = f"ov{index}"
                        filters.append(
                            f"[{index + 1}:v]trim=start={trim_s:.3f}:duration={end_s - start_s:.3f},"
                            f"setpts=PTS-STARTPTS+{start_s:.3f}/TB,"
                            f"scale={width_px}:{height_px}:force_original_aspect_ratio=decrease[scaled{index}];"
                            f"[{previous}][scaled{index}]overlay=x={int(overlay.get('x', width - width_px - 120))}:"
                            f"y={int(overlay.get('y', 260))}:eof_action=pass:repeatlast=0:"
                            f"enable='gte(t,{start_s:.3f})*lt(t,{end_s:.3f})'[${next_label}]".replace("[$", "[")
                        )
                        previous = next_label
                    overlay_video = work_dir / "overlay_video.mp4"
                    res_overlay = run_media_command([
                        self.ffmpeg_bin, "-y", "-i", str(current_video), *overlay_inputs,
                        "-filter_complex", ";".join(filters), "-map", f"[{previous}]", "-an",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), str(overlay_video),
                    ], capture_output=True, text=True)
                    if res_overlay.returncode != 0:
                        raise RuntimeError(f"Lỗi ghép lớp phủ diễn hoạ: {res_overlay.stderr[-300:]}")
                    current_video = overlay_video
                if captions:
                    drawtext_filters = []
                    if caption_style == "vietsub_karaoke_v2":
                        if not VIETSUB_FONT_PATH.is_file():
                            raise RuntimeError("CAPTION_FONT_NOT_FOUND")
                        fonts_dir = work_dir / "fonts"
                        fonts_dir.mkdir(exist_ok=True)
                        shutil.copyfile(VIETSUB_FONT_PATH, fonts_dir / VIETSUB_FONT_PATH.name)
                        karaoke_settings = (
                            timeline.get("karaoke_settings")
                            if isinstance(timeline, dict)
                            else getattr(timeline, "karaoke_settings", None)
                        )
                        (work_dir / "captions.ass").write_text(
                            build_karaoke_ass(karaoke_captions, width, height, settings=karaoke_settings),
                            encoding="utf-8",
                        )
                        drawtext_filters.append("ass=captions.ass:fontsdir=fonts")
                        font_file = f"fonts/{VIETSUB_FONT_PATH.name}"
                        has_font = True
                        font_color = "white"
                        box_color = "0x000000@0.72"
                        box_border = 16
                        caption_y = "h*0.73" if height > width else "h-90"
                    elif caption_style == "vietsub_v1":
                        if not VIETSUB_FONT_PATH.is_file():
                            raise RuntimeError("CAPTION_FONT_NOT_FOUND")
                        font_file = VIETSUB_FONT_PATH.name
                        shutil.copyfile(VIETSUB_FONT_PATH, work_dir / font_file)
                        has_font = True
                        font_color = "white"
                        box_color = "0x000000@0.72"
                        box_border = 16
                        caption_y = "h*0.73" if height > width else "h-90"
                    else:
                        font_file = "/Windows/Fonts/arial.ttf"
                        has_font = os.path.exists("C:/Windows/Fonts/arial.ttf") or os.path.exists("/Windows/Fonts/arial.ttf")
                        font_color = "0xFFE600"
                        box_color = "0x000000@0.7"
                        box_border = 8
                        caption_y = "h-480" if height > width else "h-160"
                    for c_idx, cap in enumerate(static_captions if caption_style == "vietsub_karaoke_v2" else captions):
                        text = getattr(cap, "text", "") or (cap.get("text", "") if isinstance(cap, dict) else "")
                        if not text:
                            continue
                        c_start_s = (getattr(cap, "start_ms", 0) or (cap.get("start_ms", 0) if isinstance(cap, dict) else 0)) / 1000.0
                        c_dur_s = (getattr(cap, "duration_ms", 2000) or (cap.get("duration_ms", 2000) if isinstance(cap, dict) else 2000)) / 1000.0
                        c_end_s = c_start_s + c_dur_s
                        f_size = getattr(cap, "font_size", 26) or (cap.get("font_size", 26) if isinstance(cap, dict) else 26)
                        requested_y = getattr(cap, "position_y_px", None) or (cap.get("position_y_px") if isinstance(cap, dict) else None)
                        visual_type = cap.get("visual_type", "") if isinstance(cap, dict) else getattr(cap, "visual_type", "")
                        cap_font_color = font_color
                        cap_box_color = box_color
                        cap_box_border = box_border
                        if visual_type == "callout":
                            cap_box_color = "0x0F766E@0.96"
                            cap_box_border = 24
                        caption_y = max(150, min(height - 320, int(requested_y))) if requested_y is not None else ("h*0.73" if height > width else "h-90")
                        text = textwrap.fill(text, width=max(10, int(32 * 52 / max(1, f_size))), break_long_words=False, break_on_hyphens=False)

                        txt_filename = f"caption_{c_idx}.txt"
                        text_file = work_dir / txt_filename
                        text_file.write_text(text, encoding="utf-8")

                        # Safe Zone: x=(w-text_w)/2, y=h-480 (nằm trên mép bottom 320px)
                        if has_font:
                            filter_str = (
                                f"drawtext=fontfile='{font_file}':textfile='{txt_filename}':fontsize={f_size}:fontcolor={cap_font_color}"
                                f":box=1:boxcolor={cap_box_color}:boxborderw={cap_box_border}"
                                f":x=(w-text_w)/2:y={caption_y}"
                                f":enable='between(t,{c_start_s:.3f},{c_end_s:.3f})'"
                            )
                        else:
                            filter_str = (
                                f"drawtext=textfile='{txt_filename}':fontsize={f_size}:fontcolor={cap_font_color}"
                                f":box=1:boxcolor={cap_box_color}:boxborderw={cap_box_border}"
                                f":x=(w-text_w)/2:y={caption_y}"
                                f":enable='between(t,{c_start_s:.3f},{c_end_s:.3f})'"
                            )
                        drawtext_filters.append(filter_str)

                    if drawtext_filters:
                        captioned_video = work_dir / "captioned_video.mp4"
                        cmd_cap = [
                            self.ffmpeg_bin, "-y",
                            "-i", str(current_video),
                            "-vf", ",".join(drawtext_filters),
                            "-c:v", "libx264",
                            "-pix_fmt", "yuv420p",
                            str(captioned_video)
                        ]
                        res_cap = run_media_command(cmd_cap, cwd=str(work_dir), capture_output=True, text=True)
                        if res_cap.returncode != 0:
                            raise RuntimeError(f"Lỗi khắc phụ đề (caption burn-in) thất bại: {res_cap.stderr[-300:]}")
                        current_video = captioned_video


                # 4. Âm thanh (Voice, Music, Ducking, Loudness -14 LUFS)
                voice_tr = getattr(timeline, "voice_track", None) or (timeline.get("voice_track") if isinstance(timeline, dict) else None)
                music_tr = getattr(timeline, "music_track", None) or (timeline.get("music_track") if isinstance(timeline, dict) else None)

                voice_asset_id = getattr(voice_tr, "asset_id", None) or (voice_tr.get("asset_id") if isinstance(voice_tr, dict) else None) if voice_tr else None
                music_asset_id = getattr(music_tr, "asset_id", None) or (music_tr.get("asset_id") if isinstance(music_tr, dict) else None) if music_tr else None
                music_gain_db = getattr(music_tr, "gain_db", 0.0) if music_tr else 0.0
                if isinstance(music_tr, dict):
                    music_gain_db = music_tr.get("gain_db", 0.0)

                has_voice = bool(voice_asset_id)
                has_music = bool(music_asset_id)

                final_audio = work_dir / "final_audio.wav"
                final_duration_sec = total_duration_sec
                video_playback_speed = 1.0
                video_content_duration_sec = total_duration_sec
                voice_duration = 0.0

                if preserve_voice_audio:
                    if not has_voice:
                        raise ValueError("RAW_TTS_REQUIRES_VOICE")
                    from .audio_processor import audio_processor
                    voice_file = asset_path_resolver(voice_asset_id)
                    voice_duration = float(audio_processor.probe_audio(voice_file)["duration_seconds"])
                    if voice_duration <= 0:
                        raise ValueError("RAW_TTS_DURATION_INVALID")
                    video_playback_speed = fit_voice_speed(total_duration_sec, voice_duration)
                    video_content_duration_sec = total_duration_sec / video_playback_speed
                    final_duration_sec = max(video_content_duration_sec, voice_duration)
                    if has_music:
                        music_file = asset_path_resolver(music_asset_id)
                        run_media_command([
                            self.ffmpeg_bin, "-y", "-t", f"{final_duration_sec:.3f}",
                            "-i", str(voice_file), "-i", str(music_file),
                            "-filter_complex",
                             f"[1:a]volume={music_gain_db:.2f}dB,apad=whole_dur={final_duration_sec:.3f}[m];"
                             f"[m][0:a]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=350[d];"
                            "[d][0:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
                            "-map", "[a]", "-ar", "44100", "-ac", "2", "-t", f"{final_duration_sec:.3f}", str(final_audio),
                        ], capture_output=True, check=True)
                    else:
                        final_audio = voice_file

                elif has_voice and has_music:
                    voice_file = asset_path_resolver(voice_asset_id)
                    music_file = asset_path_resolver(music_asset_id)
                    cmd_audio = [
                        self.ffmpeg_bin, "-y",
                        "-t", f"{total_duration_sec:.3f}",
                        "-i", str(voice_file),
                        "-i", str(music_file),
                        "-filter_complex",
                        f"[1:a]volume={music_gain_db:.2f}dB,apad=whole_dur={total_duration_sec:.3f}[m_in];"
                        f"[0:a]apad=whole_dur={total_duration_sec:.3f},atrim=duration={total_duration_sec:.3f},acompressor=threshold=0.1:ratio=4:attack=10:release=150,volume=0dB[v_in];"
                        "[m_in][v_in]sidechaincompress=threshold=0.1:ratio=4:attack=150:release=800[m_ducked];"
                        "[m_ducked][v_in]amix=inputs=2:duration=first:dropout_transition=2[mixed];"
                        "[mixed]loudnorm=I=-14:LRA=11:TP=-1.5[out_a]",
                        "-map", "[out_a]",
                        str(final_audio)
                    ]
                    res_a = run_media_command(cmd_audio, capture_output=True, text=True)
                    if res_a.returncode != 0:
                        cmd_audio_simple = [
                            self.ffmpeg_bin, "-y",
                            "-t", f"{total_duration_sec:.3f}",
                            "-i", str(voice_file),
                            "-i", str(music_file),
                            "-filter_complex",
                            f"[1:a]volume={music_gain_db:.2f}dB,apad=whole_dur={total_duration_sec:.3f}[music];"
                            f"[0:a]apad=whole_dur={total_duration_sec:.3f},atrim=duration={total_duration_sec:.3f}[voice];"
                            "[voice][music]amix=inputs=2:duration=first[mixed];[mixed]loudnorm=I=-14:LRA=11:TP=-1.5[aout]",
                            "-map", "[aout]",
                            str(final_audio)
                        ]
                        run_media_command(cmd_audio_simple, capture_output=True, check=True)

                elif has_voice:
                    voice_file = asset_path_resolver(voice_asset_id)
                    cmd_audio = [
                        self.ffmpeg_bin, "-y",
                        "-t", f"{total_duration_sec:.3f}",
                        "-i", str(voice_file),
                        "-af", f"apad=whole_dur={total_duration_sec:.3f},atrim=duration={total_duration_sec:.3f},acompressor=threshold=0.1:ratio=4:attack=10:release=150,loudnorm=I=-14:LRA=11:TP=-1.5",
                        str(final_audio)
                    ]
                    run_media_command(cmd_audio, capture_output=True, check=True)

                elif has_music:
                    music_file = asset_path_resolver(music_asset_id)
                    cmd_audio = [
                        self.ffmpeg_bin, "-y",
                        "-t", f"{total_duration_sec:.3f}",
                        "-i", str(music_file),
                        "-af", f"volume={music_gain_db:.2f}dB,apad=whole_dur={total_duration_sec:.3f},atrim=duration={total_duration_sec:.3f},loudnorm=I=-14:LRA=11:TP=-1.5",
                        str(final_audio)
                    ]
                    run_media_command(cmd_audio, capture_output=True, check=True)

                # 5. Xuất silent MP4 nếu người dùng chưa chọn giọng đọc hoặc nhạc.
                active_sfx = [cue for cue in sfx_cues if float(cue["start_seconds"]) < final_duration_sec]
                has_sfx = bool(active_sfx)
                if has_sfx:
                    cues = [
                        {**cue, "start_seconds": float(cue["start_seconds"]) / video_playback_speed if preserve_voice_audio else cue["start_seconds"]}
                        for cue in active_sfx
                    ]
                    final_audio = self._mix_sfx_cues(
                        final_audio if has_voice or has_music else None,
                        cues,
                        final_duration_sec,
                        work_dir,
                        preserve_voice_audio,
                    )

                cmd_final = [self.ffmpeg_bin, "-y", "-i", str(current_video)]
                if has_voice or has_music or has_sfx:
                    cmd_final.extend([
                        "-i", str(final_audio), "-c:a", "aac", "-b:a", "192k",
                    ])
                    if not preserve_voice_audio:
                        cmd_final.extend(["-ar", "44100"])
                else:
                    cmd_final.append("-an")
                if preserve_voice_audio:
                    video_filter = f"setpts={1 / video_playback_speed:.8f}*PTS"
                    frozen_tail_sec = max(0.0, final_duration_sec - video_content_duration_sec)
                    if frozen_tail_sec > 0.01:
                        video_filter += f",tpad=stop_mode=clone:stop_duration={frozen_tail_sec:.3f}"
                    cmd_final.extend(["-vf", video_filter])
                cmd_final.extend([
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                    "-t", f"{final_duration_sec:.3f}", str(output_path),
                ])
                res_final = run_media_command(cmd_final, capture_output=True, text=True)
                if res_final.returncode != 0:
                    raise RuntimeError(f"Lỗi ghép hoàn chỉnh thành phẩm MP4: {res_final.stderr}")

                flow_audio_present = False if preserve_voice_audio else self._preserve_native_clip_audio(
                    output_path, native_audio_specs, work_dir, has_voice or has_music or has_sfx, total_duration_sec,
                )

                meta = self.probe_video(output_path)
                meta["flow_native_audio"] = flow_audio_present
                if has_voice or has_music or has_sfx:
                    try:
                        from .audio_processor import audio_processor
                        l_meas = audio_processor.measure_loudness(output_path)
                        measured_lufs = l_meas.get("measured_i_lufs")
                        measured_tp = l_meas.get("measured_tp_dbtp")
                        measured_lra = l_meas.get("measured_lra_lu")
                    except Exception as exc:
                        raise RuntimeError(f"Kiểm định âm thanh thất bại: Không thể đo đạc EBU R128 từ tệp kết xuất: {exc}")

                    if measured_lufs is None:
                        raise RuntimeError("Kiểm định âm thanh thất bại: Không nhận được chỉ số measured_i_lufs từ bộ đo.")

                    sfx_only = has_sfx and not has_voice and not has_music and not flow_audio_present
                    if sfx_only and (measured_tp is None or measured_tp > -1.5):
                        raise RuntimeError("Kiểm định true peak cho video chỉ có SFX không đạt -1,5 dBTP.")
                    if not preserve_voice_audio and not sfx_only and not (-15.0 <= measured_lufs <= -13.0):
                        raise RuntimeError(
                            f"Kiểm định chất lượng âm lượng EBU R128 không đạt chuẩn phát sóng TikTok (-14.0 ± 1.0 LUFS): "
                            f"Đo được {measured_lufs} LUFS."
                        )

                    meta["audio_loudness_lufs"] = measured_lufs
                    meta["audio_true_peak_dbtp"] = measured_tp
                    meta["audio_lra_lu"] = measured_lra
                    # shortcut: sparse SFX-only audio has no reliable integrated LUFS, upgrade when adding a continuous audio bed.
                    meta["audio_normalization"] = "SKIPPED_RAW_TTS" if preserve_voice_audio else "SFX_ONLY_PEAK_LIMITED" if sfx_only else "EBU_R128"
                    if preserve_voice_audio:
                        meta["video_playback_speed"] = round(video_playback_speed, 4)
                        meta["video_content_duration_seconds"] = round(video_content_duration_sec, 3)
                        meta["voice_audio_duration_seconds"] = round(voice_duration, 3)
                        meta["silent_tail_seconds"] = round(max(0.0, video_content_duration_sec - voice_duration), 3)
                        meta["frozen_tail_seconds"] = round(max(0.0, voice_duration - video_content_duration_sec), 3)

                return meta

            finally:
                if temp_dir is None and work_dir.exists():
                    shutil.rmtree(work_dir, ignore_errors=True)

    def _mix_sfx_cues(self, base_audio_path, cues, duration_sec, work_dir, preserve_voice_audio):
        output = work_dir / "sfx_mixed_audio.wav"
        if base_audio_path:
            command = [self.ffmpeg_bin, "-y", "-i", str(base_audio_path)]
            filters = [f"[0:a]aresample=44100,aformat=channel_layouts=stereo,apad=whole_dur={duration_sec:.3f},atrim=duration={duration_sec:.3f},asetpts=PTS-STARTPTS[base]"]
        else:
            command = [self.ffmpeg_bin, "-y", "-f", "lavfi", "-t", f"{duration_sec:.3f}", "-i", "anullsrc=r=44100:cl=stereo"]
            filters = [f"[0:a]atrim=duration={duration_sec:.3f},asetpts=PTS-STARTPTS[base]"]

        labels = ["[base]"]
        for index, cue in enumerate(cues):
            command.extend(["-i", str(cue["path"])])
            input_index = index + 1
            delay_ms = round(float(cue["start_seconds"]) * 1000)
            label = f"sfx{index}"
            filters.append(
                f"[{input_index}:a]aresample=44100,aformat=channel_layouts=stereo,volume={float(cue['volume']):.4f},"
                f"adelay={delay_ms}|{delay_ms},apad,atrim=duration={duration_sec:.3f},asetpts=PTS-STARTPTS[{label}]"
            )
            labels.append(f"[{label}]")

        filters.append(
            f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0:dropout_transition=0[mixed]"
        )
        finish = "alimiter=limit=0.95" if preserve_voice_audio else "loudnorm=I=-14:LRA=11:TP=-1.5"
        filters.append(f"[mixed]{finish}[out]")
        command.extend([
            "-filter_complex", ";".join(filters), "-map", "[out]", "-t", f"{duration_sec:.3f}",
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(output),
        ])
        run_media_command(command, capture_output=True, check=True)
        return output

    def _preserve_native_clip_audio(self, output_path, audio_specs, work_dir, mix_existing, duration_sec):
        from .audio_processor import audio_processor

        probed_specs = [
            (path, media_type, trim_in, duration,
             media_type == "video" and audio_processor.probe_audio(path).get("codec_name") != "unknown")
            for path, media_type, trim_in, duration in audio_specs
        ]
        has_native_audio = any(has_audio for *_, has_audio in probed_specs)
        if not has_native_audio:
            return False

        segment_paths = []
        for index, (path, media_type, trim_in, duration, has_audio) in enumerate(probed_specs):
            segment = work_dir / f"native_audio_{index:03d}.wav"
            if has_audio:
                cmd = [self.ffmpeg_bin, "-y", "-ss", f"{trim_in:.3f}", "-t", f"{duration:.3f}", "-i", str(path),
                       "-map", "0:a:0", "-vn", "-af", f"aresample=44100,apad,atrim=duration={duration:.3f}",
                       "-ac", "2", "-c:a", "pcm_s16le", str(segment)]
            else:
                cmd = [self.ffmpeg_bin, "-y", "-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=r=44100:cl=stereo",
                       "-c:a", "pcm_s16le", str(segment)]
            run_media_command(cmd, capture_output=True, check=True)
            segment_paths.append(segment)

        concat_list = work_dir / "native_audio_concat.txt"
        concat_list.write_text("".join(f"file '{path.resolve().as_posix()}'\n" for path in segment_paths), encoding="utf-8")
        native_audio = work_dir / "native_flow_audio.wav"
        run_media_command([
            self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-t", f"{duration_sec:.3f}", "-c:a", "pcm_s16le", str(native_audio),
        ], capture_output=True, check=True)

        mixed_video = work_dir / "flow_audio_video.mp4"
        cmd = [self.ffmpeg_bin, "-y", "-i", str(output_path), "-i", str(native_audio)]
        audio_input = "[0:a][1:a]amix=inputs=2:duration=first:normalize=0," if mix_existing else "[1:a]"
        # Giữ dải động nguồn và chừa 1,5 dB cho đỉnh phát sinh khi mã hóa AAC.
        normalization = "loudnorm=I=-14:LRA=50:TP=-3"
        analysis = run_media_command(cmd + [
            "-filter_complex", f"{audio_input}{normalization}:print_format=json[aout]",
            "-map", "[aout]", "-t", f"{duration_sec:.3f}", "-f", "null", "-",
        ], capture_output=True, check=True, text=True, encoding="utf-8", errors="replace")
        measured = json.loads(analysis.stderr[analysis.stderr.rfind("{"):analysis.stderr.rfind("}") + 1])
        if measured["input_i"] == "-inf":
            normalization = "anull"
        else:
            normalization += (
                f":measured_I={measured['input_i']}:measured_LRA={measured['input_lra']}"
                f":measured_TP={measured['input_tp']}:measured_thresh={measured['input_thresh']}"
                f":offset={measured['target_offset']}:linear=true"
            )
        cmd.extend(["-filter_complex", f"{audio_input}{normalization}[aout]", "-map", "0:v:0", "-map", "[aout]"])
        cmd.extend(["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                    "-t", f"{duration_sec:.3f}", str(mixed_video)])
        run_media_command(cmd, capture_output=True, check=True)
        mixed_video.replace(output_path)
        return True

video_processor = VideoProcessor()

