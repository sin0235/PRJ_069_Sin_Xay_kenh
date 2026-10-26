# -*- coding: utf-8 -*-
"""Bộ xử lý và kiểm định Video Dọc 9:16 chuẩn TikTok bằng FFmpeg (P09 + GF02/GF03).
Hỗ trợ mở rộng video 16:9 sang 9:16 (Blurred Canvas Extension), kiểm tra tỷ lệ 9:16,
Safe Zone, ghép video phân cảnh, track âm thanh và tẩy sạch watermark Google Veo / Gemini AI.
"""

import logging
import json
import os
import pathlib
import subprocess
import sys
import threading
import uuid
import shutil
import textwrap
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)
VIETSUB_FONT_PATH = pathlib.Path(__file__).resolve().parent / "assets" / "fonts" / "be_vietnam_pro_semibold.ttf"

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

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi probe video: {res.stderr}")

        data = json.loads(res.stdout)
        v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)

        if not v_stream:
            raise ValueError("Tệp không chứa luồng video hợp lệ.")

        width = int(v_stream.get("width", 0))
        height = int(v_stream.get("height", 0))
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
            "codec_name": v_stream.get("codec_name"),
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
            result = veo_remover.remove_watermark(
                input_video_path=input_video_path,
                output_video_path=output_video_path,
                use_cpu=use_cpu,
                watermark_type=watermark_type,
                denoise_method=denoise_method,
                region=region,
                veo_alpha=veo_alpha
            )
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

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
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

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if concat_txt.exists():
            concat_txt.unlink()

        if res.returncode != 0:
            raise RuntimeError(f"Lỗi khi assemble video: {res.stderr}")

        return self.probe_video(output_path)

    def render_timeline_document(
        self,
        timeline: Any,
        asset_path_resolver: Any,
        output_path: pathlib.Path,
        temp_dir: Optional[pathlib.Path] = None,
        transition_seconds: float = 0.0,
        caption_style: str = "legacy",
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
            if caption_style not in {"legacy", "vietsub_v1"}:
                raise ValueError("CAPTION_STYLE_UNSUPPORTED")
            output_path.parent.mkdir(parents=True, exist_ok=True)

            clips = getattr(timeline, "clips", [])
            if not clips and isinstance(timeline, dict):
                clips = timeline.get("clips", [])
            if not clips:
                raise ValueError("Timeline không có phân cảnh (clips) nào để kết xuất.")

            width = getattr(timeline, "width", 1080) or 1080
            height = getattr(timeline, "height", 1920) or 1920
            fps = getattr(timeline, "fps", 30) or 30

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

                    asset_file = asset_path_resolver(asset_id)
                    if not asset_file.exists():
                        raise FileNotFoundError(f"Không tìm thấy file nguồn của asset {asset_id}: {asset_file}")

                    seg_out = work_dir / f"seg_{idx:03d}_{clip_id}.mp4"

                    if fit == "contain":
                        vf_scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
                    else:
                        vf_scale = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps={fps}"

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
                        res = subprocess.run(cmd, capture_output=True, text=True)
                        if res.returncode != 0:
                            raise RuntimeError(f"Lỗi render phân cảnh ảnh {clip_id}: {res.stderr}")
                        seg_files.append(seg_out)
                        seg_durations.append(dur_s)
                        native_audio_specs.append((asset_file, media_type, 0.0, dur_s))
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
                        res = subprocess.run(cmd, capture_output=True, text=True)
                        if res.returncode != 0:
                            raise RuntimeError(f"Lỗi render phân cảnh video {clip_id}: {res.stderr}")
                        seg_files.append(seg_out)
                        seg_durations.append(dur_s)
                        native_audio_specs.append((asset_file, media_type, in_s, dur_s))
                        total_duration_sec += dur_s

                # 2. Ghép các phân cảnh video; tail freeze keeps the timeline duration during crossfade.
                if transition_seconds > 0 and len(seg_files) > 1:
                    transition = min(transition_seconds, 0.5)
                    filter_parts = []
                    previous = "0:v"
                    offset = 0.0
                    for idx, duration in enumerate(seg_durations[:-1]):
                        padded = f"p{idx}"
                        filter_parts.append(
                            f"[{previous}]tpad=stop_mode=clone:stop_duration={transition:.3f}[{padded}]"
                        )
                        output = f"x{idx}"
                        filter_parts.append(
                            f"[{padded}][{idx + 1}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset + duration:.3f}[{output}]"
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
                    res_concat = subprocess.run(cmd_transition, capture_output=True, text=True)
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
                    res_concat = subprocess.run(cmd_concat, capture_output=True, text=True)
                    if res_concat.returncode != 0:
                        raise RuntimeError(f"Lỗi ghép phân cảnh: {res_concat.stderr}")

                # 3. Phụ đề Captions (Burn-in text vào Safe Zone)
                captions = getattr(timeline, "captions", [])
                if not captions and isinstance(timeline, dict):
                    captions = timeline.get("captions", [])

                current_video = concat_video
                if captions:
                    drawtext_filters = []
                    if caption_style == "vietsub_v1":
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
                    for c_idx, cap in enumerate(captions):
                        text = getattr(cap, "text", "") or (cap.get("text", "") if isinstance(cap, dict) else "")
                        if not text:
                            continue
                        c_start_s = (getattr(cap, "start_ms", 0) or (cap.get("start_ms", 0) if isinstance(cap, dict) else 0)) / 1000.0
                        c_dur_s = (getattr(cap, "duration_ms", 2000) or (cap.get("duration_ms", 2000) if isinstance(cap, dict) else 2000)) / 1000.0
                        c_end_s = c_start_s + c_dur_s
                        f_size = getattr(cap, "font_size", 26) or (cap.get("font_size", 26) if isinstance(cap, dict) else 26)
                        text = textwrap.fill(text, width=max(10, int(32 * 52 / max(1, f_size))), break_long_words=False, break_on_hyphens=False)

                        txt_filename = f"caption_{c_idx}.txt"
                        text_file = work_dir / txt_filename
                        text_file.write_text(text, encoding="utf-8")

                        # Safe Zone: x=(w-text_w)/2, y=h-480 (nằm trên mép bottom 320px)
                        if has_font:
                            filter_str = (
                                f"drawtext=fontfile='{font_file}':textfile='{txt_filename}':fontsize={f_size}:fontcolor={font_color}"
                                f":box=1:boxcolor={box_color}:boxborderw={box_border}"
                                f":x=(w-text_w)/2:y={caption_y}"
                                f":enable='between(t,{c_start_s:.3f},{c_end_s:.3f})'"
                            )
                        else:
                            filter_str = (
                                f"drawtext=textfile='{txt_filename}':fontsize={f_size}:fontcolor={font_color}"
                                f":box=1:boxcolor={box_color}:boxborderw={box_border}"
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
                        res_cap = subprocess.run(cmd_cap, cwd=str(work_dir), capture_output=True, text=True)
                        if res_cap.returncode != 0:
                            raise RuntimeError(f"Lỗi khắc phụ đề (caption burn-in) thất bại: {res_cap.stderr[-300:]}")
                        current_video = captioned_video


                # 4. Âm thanh (Voice, Music, Ducking, Loudness -14 LUFS)
                voice_tr = getattr(timeline, "voice_track", None) or (timeline.get("voice_track") if isinstance(timeline, dict) else None)
                music_tr = getattr(timeline, "music_track", None) or (timeline.get("music_track") if isinstance(timeline, dict) else None)

                voice_asset_id = getattr(voice_tr, "asset_id", None) or (voice_tr.get("asset_id") if isinstance(voice_tr, dict) else None) if voice_tr else None
                music_asset_id = getattr(music_tr, "asset_id", None) or (music_tr.get("asset_id") if isinstance(music_tr, dict) else None) if music_tr else None

                has_voice = bool(voice_asset_id)
                has_music = bool(music_asset_id)

                final_audio = work_dir / "final_audio.wav"

                if has_voice and has_music:
                    voice_file = asset_path_resolver(voice_asset_id)
                    music_file = asset_path_resolver(music_asset_id)
                    cmd_audio = [
                        self.ffmpeg_bin, "-y",
                        "-t", f"{total_duration_sec:.3f}",
                        "-i", str(voice_file),
                        "-i", str(music_file),
                        "-filter_complex",
                        "[1:a]volume=0dB[m_in];"
                        "[0:a]volume=0dB[v_in];"
                        "[m_in][v_in]sidechaincompress=threshold=0.1:ratio=4:attack=150:release=800[m_ducked];"
                        "[m_ducked][v_in]amix=inputs=2:duration=first:dropout_transition=2[mixed];"
                        "[mixed]loudnorm=I=-14:LRA=11:TP=-1.5[out_a]",
                        "-map", "[out_a]",
                        str(final_audio)
                    ]
                    res_a = subprocess.run(cmd_audio, capture_output=True, text=True)
                    if res_a.returncode != 0:
                        cmd_audio_simple = [
                            self.ffmpeg_bin, "-y",
                            "-t", f"{total_duration_sec:.3f}",
                            "-i", str(voice_file),
                            "-i", str(music_file),
                            "-filter_complex",
                            "[0:a][1:a]amix=inputs=2:duration=first[mixed];[mixed]loudnorm=I=-14:LRA=11:TP=-1.5[aout]",
                            "-map", "[aout]",
                            str(final_audio)
                        ]
                        subprocess.run(cmd_audio_simple, capture_output=True, check=True)

                elif has_voice:
                    voice_file = asset_path_resolver(voice_asset_id)
                    cmd_audio = [
                        self.ffmpeg_bin, "-y",
                        "-t", f"{total_duration_sec:.3f}",
                        "-i", str(voice_file),
                        "-af", "loudnorm=I=-14:LRA=11:TP=-1.5",
                        str(final_audio)
                    ]
                    subprocess.run(cmd_audio, capture_output=True, check=True)

                elif has_music:
                    music_file = asset_path_resolver(music_asset_id)
                    cmd_audio = [
                        self.ffmpeg_bin, "-y",
                        "-t", f"{total_duration_sec:.3f}",
                        "-i", str(music_file),
                        "-af", "loudnorm=I=-14:LRA=11:TP=-1.5",
                        str(final_audio)
                    ]
                    subprocess.run(cmd_audio, capture_output=True, check=True)

                # 5. Xuất silent MP4 nếu người dùng chưa chọn giọng đọc hoặc nhạc.
                cmd_final = [self.ffmpeg_bin, "-y", "-i", str(current_video)]
                if has_voice or has_music:
                    cmd_final.extend([
                        "-i", str(final_audio), "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                    ])
                else:
                    cmd_final.append("-an")
                cmd_final.extend([
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
                    "-t", f"{total_duration_sec:.3f}", str(output_path),
                ])
                res_final = subprocess.run(cmd_final, capture_output=True, text=True)
                if res_final.returncode != 0:
                    raise RuntimeError(f"Lỗi ghép hoàn chỉnh thành phẩm MP4: {res_final.stderr}")

                flow_audio_present = self._preserve_native_clip_audio(
                    output_path, native_audio_specs, work_dir, has_voice or has_music, total_duration_sec,
                )

                meta = self.probe_video(output_path)
                meta["flow_native_audio"] = flow_audio_present
                if has_voice or has_music:
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

                    if not (-15.0 <= measured_lufs <= -13.0):
                        raise RuntimeError(
                            f"Kiểm định chất lượng âm lượng EBU R128 không đạt chuẩn phát sóng TikTok (-14.0 ± 1.0 LUFS): "
                            f"Đo được {measured_lufs} LUFS."
                        )

                    meta["audio_loudness_lufs"] = measured_lufs
                    meta["audio_true_peak_dbtp"] = measured_tp
                    meta["audio_lra_lu"] = measured_lra

                return meta

            finally:
                if temp_dir is None and work_dir.exists():
                    shutil.rmtree(work_dir, ignore_errors=True)

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
            subprocess.run(cmd, capture_output=True, check=True)
            segment_paths.append(segment)

        concat_list = work_dir / "native_audio_concat.txt"
        concat_list.write_text("".join(f"file '{path.resolve().as_posix()}'\n" for path in segment_paths), encoding="utf-8")
        native_audio = work_dir / "native_flow_audio.wav"
        subprocess.run([
            self.ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-t", f"{duration_sec:.3f}", "-c:a", "pcm_s16le", str(native_audio),
        ], capture_output=True, check=True)

        mixed_video = work_dir / "flow_audio_video.mp4"
        cmd = [self.ffmpeg_bin, "-y", "-i", str(output_path), "-i", str(native_audio)]
        audio_input = "[0:a][1:a]amix=inputs=2:duration=first:normalize=0," if mix_existing else "[1:a]"
        # Giữ dải động nguồn và chừa 1,5 dB cho đỉnh phát sinh khi mã hóa AAC.
        normalization = "loudnorm=I=-14:LRA=50:TP=-3"
        analysis = subprocess.run(cmd + [
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
        subprocess.run(cmd, capture_output=True, check=True)
        mixed_video.replace(output_path)
        return True

video_processor = VideoProcessor()

