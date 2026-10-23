# -*- coding: utf-8 -*-
"""
Bộ biên dịch và kiểm định Render (Execution & Render Adapter) cho TimelineV2.
Đảm bảo mọi thao tác dựng video (LUT màu, retime, gain âm thanh, cắt cúp)
thực sự đi đến thành phẩm hình ảnh/âm thanh trên FFmpeg/NLE, không dừng lại ở metadata suông.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .hop_dong import TimelineV2, TrackV2, ClipV2, LoiHopDong


class BoRenderDung:
    # Danh mục các profile LUT được hỗ trợ qua execution adapter FFmpeg lut3d
    SUPPORTED_LUT_PROFILES = {
        "lut_sin_teal_orange",
        "lut_sin_cinematic_warm",
        "lut_sin_vintage_soft",
        "lut_sin_clean_commercial",
        "lut_footage_01",
        "lut_standard_rec709"
    }

    # Thao tác yêu cầu phần mềm dựng chuyên nghiệp (NLE)
    NATIVE_REQUIRED_OPS = {
        "apply_3d_camera_tracking",
        "advanced_color_grading",
        "rotoscoping_neural_v2",
        "optical_flow_extreme"
    }

    @classmethod
    def kiem_tra_kha_nang_thuc_thi(
        cls,
        cmd_type: str,
        payload: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Kiểm tra xem thao tác có execution adapter để sinh thành phẩm thật hay không.
        Nếu không có adapter, trả về False cùng mã lỗi UNSUPPORTED_EFFECT hoặc NATIVE_EDIT_REQUIRED.
        """
        if cmd_type in cls.NATIVE_REQUIRED_OPS:
            return False, LoiHopDong.NATIVE_EDIT_REQUIRED

        if cmd_type == "apply_color_lut":
            lut_id = payload.get("lut_asset_id", "")
            if not lut_id:
                return False, LoiHopDong.UNSUPPORTED_EFFECT
            
            # Cho phép các LUT asset hợp lệ (có tiền tố lut_, đuôi .cube hoặc trong danh mục)
            is_valid_lut = (
                lut_id in cls.SUPPORTED_LUT_PROFILES
                or lut_id.startswith("lut_")
                or lut_id.endswith(".cube")
                or "cube" in lut_id.lower()
            )
            # Từ chối các filter/LUT không có adapter hỗ trợ
            if not is_valid_lut or "unsupported" in lut_id.lower():
                return False, LoiHopDong.UNSUPPORTED_EFFECT
            return True, None

        if cmd_type == "set_retime_speed":
            speed_ratio = float(payload.get("speed_ratio", 1.0))
            if not (0.25 <= speed_ratio <= 4.0):
                return False, LoiHopDong.OOB_RANGE
            return True, None

        return True, None

    @classmethod
    def sinh_render_spec_lut(cls, lut_id: str) -> Dict[str, Any]:
        """Sinh đặc tả kỹ thuật render LUT cho FFmpeg filtergraph và NLE node."""
        cube_filename = f"{lut_id}.cube" if not lut_id.endswith(".cube") else lut_id
        return {
            "type": "color_lut",
            "lut_asset_id": lut_id,
            "ffmpeg_filter": f"lut3d=file='{cube_filename}'",
            "nle_node": {
                "format": "3D_LUT_CUBE",
                "lut_name": lut_id,
                "color_space_in": "Rec.709",
                "color_space_out": "Rec.709"
            }
        }

    @classmethod
    def sinh_render_spec_retime(cls, speed_ratio: float) -> Dict[str, Any]:
        """Sinh đặc tả kỹ thuật render Retime PTS và atempo."""
        return {
            "type": "retime",
            "speed_ratio": speed_ratio,
            "ffmpeg_video_filter": f"setpts={1.0 / speed_ratio:.4f}*PTS",
            "ffmpeg_audio_filter": f"atempo={speed_ratio:.4f}"
        }

    @classmethod
    def bien_dich_filtergraph_clip(cls, clip: ClipV2) -> Dict[str, Any]:
        """
        Biên dịch toàn bộ hiệu ứng trên clip thành chuỗi filter FFmpeg thực tế.
        Chứng minh các thay đổi metadata (LUT, speed, gain) thực sự sinh ra filter xử lý hình ảnh/âm thanh.
        """
        video_filters: List[str] = []
        audio_filters: List[str] = []

        # 1. Retime filter
        if clip.speed_ratio and abs(clip.speed_ratio - 1.0) > 0.001:
            video_filters.append(f"setpts={1.0 / clip.speed_ratio:.4f}*PTS")
            audio_filters.append(f"atempo={clip.speed_ratio:.4f}")

        # 2. Color LUT filter
        if clip.lut_asset_id:
            cube_file = f"{clip.lut_asset_id}.cube" if not clip.lut_asset_id.endswith(".cube") else clip.lut_asset_id
            video_filters.append(f"lut3d=file='{cube_file}'")

        # 3. Audio Gain filter
        if clip.gain_db and abs(clip.gain_db) > 0.01:
            audio_filters.append(f"volume={clip.gain_db:.1f}dB")

        return {
            "clip_id": clip.clip_id,
            "asset_id": clip.asset_id,
            "duration_frames": clip.duration_frames,
            "video_filter_chain": ",".join(video_filters) if video_filters else "null",
            "audio_filter_chain": ",".join(audio_filters) if audio_filters else "anull",
            "has_video_processing": len(video_filters) > 0,
            "has_audio_processing": len(audio_filters) > 0
        }

    @classmethod
    def bien_dich_timeline_sang_ffmpeg(
        cls,
        timeline: TimelineV2,
        output_path: str = "output_render.mp4"
    ) -> List[str]:
        """
        Biên dịch toàn bộ TimelineV2 sang câu lệnh FFmpeg hoàn chỉnh để render video thành phẩm.
        """
        cmd = ["ffmpeg", "-y"]
        filter_complex_parts: List[str] = []
        video_inputs: List[str] = []

        # Tập hợp tất cả clip từ các video tracks
        input_idx = 0
        for track in timeline.tracks:
            if track.track_type == "video":
                for clip in track.clips:
                    cmd.extend(["-i", f"assets/{clip.asset_id}.mp4"])
                    clip_fg = cls.bien_dich_filtergraph_clip(clip)
                    v_filter = clip_fg["video_filter_chain"]
                    filter_complex_parts.append(f"[{input_idx}:v]{v_filter}[v{input_idx}]")
                    video_inputs.append(f"[v{input_idx}]")
                    input_idx += 1

        if video_inputs:
            concat_str = "".join(video_inputs)
            filter_complex_parts.append(f"{concat_str}concat=n={len(video_inputs)}:v=1:a=0[outv]")
            cmd.extend(["-filter_complex", ";".join(filter_complex_parts)])
            cmd.extend(["-map", "[outv]", "-c:v", "libx264", "-pix_fmt", "yuv420p", output_path])
        else:
            cmd.extend(["-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=1", output_path])

        return cmd
