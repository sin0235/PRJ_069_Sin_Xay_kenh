# -*- coding: utf-8 -*-
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
# -*- coding: utf-8 -*-
"""Động cơ điều phối Video Dọc 9:16 (Video Engine) cho BAHA Creator Studio (P09 + GF01/02/03).
Tích hợp Video Prompt Compiler (Bộ biên dịch chỉ thị lệnh video chuẩn hóa) cho Google Flow Omni Flash.
Quy trình cốt lõi:
1. Biên dịch yêu cầu người dùng thành Bộ lệnh video đa tầng (Intent, Subject, Kinetic, Camera, Lighting, 4K).
2. Flow tạo video gốc tỷ lệ 16:9 (10s) từ mô hình Omni Flash.
3. Hệ thống tự động mở rộng (Blurred Canvas Outpainting) từ 16:9 sang 9:16 (1080x1920) chuẩn TikTok, giữ trọn 10s.
Tuyệt đối tuân thủ Ground Truth: KHÔNG tạo video lỗi testsrc 6s, KHÔNG tự ý bốc video test cũ khi thất bại.
"""

import hashlib
import os
import pathlib
import shutil
import sys
import uuid
import subprocess
from typing import Callable, Dict, Any, Optional, List
from sqlalchemy.orm import Session

BAN_LAM_VIEC = pathlib.Path(__file__).resolve().parents[4]
FLOW_BRIDGE = BAN_LAM_VIEC / "cong_cu_tu_dong" / "flow_bridge"
if str(BAN_LAM_VIEC) not in sys.path:
    sys.path.insert(0, str(BAN_LAM_VIEC))
if str(FLOW_BRIDGE) not in sys.path:
    sys.path.insert(0, str(FLOW_BRIDGE))

from src.models.entities import MediaAsset, AIGenerationJob
from src.modules.media_studio.video_processor import video_processor
from src.modules.media_studio.security import MEDIA_ROOT_DIR
from src.modules.media_studio.prompt_compiler import video_prompt_compiler
from session_manager import FlowLoginRequired, FlowSubmissionNotSent

class GoogleFlowZeroCostProvider:
    """Luồng sản xuất video nội bộ 0đ chi phí sử dụng Google Flow AI Pro (Omni Flash 10s)."""

    def __init__(self):
        self.provider_id = "GOOGLE_FLOW_OMNI"

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        prompt_language: str = "vi",
        include_audio: bool = True,
        workspace_id: str = "default_ws",
        remove_watermark: bool = False,
        flow_project_url: Optional[str] = None,
        on_flow_project_created: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Quy trình chuẩn:
        Biên dịch brief theo tỷ lệ đích, tạo video đúng tỷ lệ trong Flow rồi chuẩn hóa kích thước, fps và codec.
        """
        if aspect_ratio not in {"9:16", "16:9"}:
            raise ValueError(f"FLOW_ASPECT_RATIO_UNSUPPORTED: {aspect_ratio}")
        target_dir = MEDIA_ROOT_DIR / "workspaces" / workspace_id / "media"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        job_hash = uuid.uuid4().hex[:10]
        output_filename = f"flow_native_{aspect_ratio.replace(':', '_')}_{job_hash}.mp4"
        output_path = target_dir / output_filename

        # Bước 0: Biên dịch chỉ thị lệnh
        compiled_info = video_prompt_compiler.compile(
            user_prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration_seconds=10,
            language=prompt_language,
        )
        flow_directive = compiled_info.compiled_directive
        print(f"[HARNESS PROMPT COMPILER] Đã chuẩn hóa bộ lệnh cho Flow: {flow_directive[:80]}...", flush=True)

        # Bước 1: Gọi Flow Client điều khiển trình duyệt
        try:
            from google_flow_client import GoogleFlowClient
            client = GoogleFlowClient(headless=True)
            flow_res = client.create_video(
                prompt=flow_directive,
                aspect_ratio=aspect_ratio,
                workspace_id=workspace_id,
                timeout_sec=240,
                flow_project_url=flow_project_url,
                on_flow_project_created=on_flow_project_created,
            )
            raw_flow_path = pathlib.Path(flow_res["storage_path"])
        except Exception as flow_err:
            if isinstance(flow_err, (FlowLoginRequired, FlowSubmissionNotSent)):
                raise
            raise RuntimeError(
                f"Google Flow: {flow_err}. "
                "Nếu video đã xuất hiện trên Flow, không tạo lại ngay; kiểm tra video trong project Flow và nhật ký tải kết quả của hệ thống."
            ) from flow_err

        shutil.copy2(raw_flow_path, target_dir / f"flow_source_{aspect_ratio.replace(':', '_')}_{job_hash}.mp4")
        watermark_removed = False
        input_path = raw_flow_path
        clean_path = target_dir / f"flow_clean_{job_hash}.mp4"
        if remove_watermark:
            clean_result = video_processor.remove_veo_watermark(raw_flow_path, clean_path, use_cpu=True)
            if clean_result.get("status") != "SUCCEEDED" or not clean_result.get("watermark_removed"):
                raise RuntimeError("WATERMARK_REMOVAL_FAILED: Flow chưa xác nhận đã loại bỏ watermark.")
            input_path = clean_path
            watermark_removed = True
        width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
        audio_options = ["-c:a", "aac", "-b:a", "192k"] if include_audio else ["-an"]
        normalize = subprocess.run(
            [video_processor.ffmpeg_bin, "-y", "-i", str(input_path), "-vf",
             f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=30",
             "-c:v", "libx264", *audio_options, "-pix_fmt", "yuv420p", str(output_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if normalize.returncode != 0:
            raise RuntimeError(f"FLOW_VIDEO_NORMALIZATION_FAILED: {normalize.stderr[-1000:]}")
        if clean_path.exists():
            clean_path.unlink()
        meta = video_processor.probe_video(output_path)

        data = output_path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()

        return {
            "status": "SUCCEEDED",
            "provider": self.provider_id,
            "source_product": "GOOGLE_FLOW",
            "filename": output_filename,
            "storage_path": str(output_path),
            "relative_storage_key": f"workspaces/{workspace_id}/media/{output_filename}",
            "sha256": sha,
            "byte_size": len(data),
            "mime_detected": "video/mp4",
            "duration_ms": int(meta.get("duration_seconds", 10.0) * 1000),
            "aspect_ratio": aspect_ratio,
            "raw_source_aspect": aspect_ratio,
            "expansion_technique": None,
            "watermark_removed": watermark_removed,
            "actual_cost": 0.0,
            "cost_currency": "USD",
            "credits_source": "GOOGLE_FLOW_PRO",
            "compiled_prompt": compiled_info.model_dump()
        }

    def generate_from_image(
        self,
        prompt: str,
        image_path: pathlib.Path,
        workspace_id: str = "default_ws",
        flow_project_url: Optional[str] = None,
        on_flow_project_created: Optional[Callable[[str], None]] = None,
        aspect_ratio: str = "9:16",
        include_audio: bool = True,
    ) -> Dict[str, Any]:
        """Tạo I2V trong Flow rồi chuẩn hóa theo tỷ lệ người dùng chọn."""
        if aspect_ratio not in {"9:16", "16:9"}:
            raise ValueError(f"FLOW_ASPECT_RATIO_UNSUPPORTED: {aspect_ratio}")
        target_dir = MEDIA_ROOT_DIR / "workspaces" / workspace_id / "media"
        target_dir.mkdir(parents=True, exist_ok=True)
        compiled_info = video_prompt_compiler.compile(user_prompt=prompt, aspect_ratio=aspect_ratio, duration_seconds=10)
        file_id = uuid.uuid4().hex[:10]
        filename = f"flow_i2v_{aspect_ratio.replace(':', '_')}_{file_id}.mp4"
        output_path = target_dir / filename
        try:
            from google_flow_client import GoogleFlowClient
            flow_res = GoogleFlowClient(headless=True).create_video(
                prompt=compiled_info.compiled_directive,
                aspect_ratio=aspect_ratio,
                workspace_id=workspace_id,
                timeout_sec=240,
                start_image_path=image_path,
                flow_project_url=flow_project_url,
                on_flow_project_created=on_flow_project_created,
            )
            shutil.copy2(flow_res["storage_path"], target_dir / f"flow_source_{aspect_ratio.replace(':', '_')}_{file_id}.mp4")
            width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
            audio_options = ["-c:a", "aac", "-b:a", "192k"] if include_audio else ["-an"]
            normalized = subprocess.run(
                [video_processor.ffmpeg_bin, "-y", "-i", flow_res["storage_path"], "-vf",
                 f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=30",
                 "-c:v", "libx264", *audio_options, "-pix_fmt", "yuv420p", str(output_path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            )
            if normalized.returncode != 0:
                raise RuntimeError(f"FLOW_VIDEO_NORMALIZATION_FAILED: {normalized.stderr[-1000:]}")
            meta = video_processor.probe_video(output_path)
        except (FlowLoginRequired, FlowSubmissionNotSent):
            raise
        except Exception as ex:
            raise RuntimeError(f"Google Flow không tạo được video từ ảnh: {ex}") from ex

        with output_path.open("rb") as video_file:
            digest = hashlib.file_digest(video_file, "sha256").hexdigest()
        return {
            "status": "SUCCEEDED",
            "provider": self.provider_id,
            "source_product": "GOOGLE_FLOW_I2V",
            "filename": filename,
            "storage_path": str(output_path),
            "relative_storage_key": f"workspaces/{workspace_id}/media/{filename}",
            "sha256": digest,
            "byte_size": output_path.stat().st_size,
            "mime_detected": "video/mp4",
            "duration_ms": int(meta.get("duration_seconds", 10.0) * 1000),
            "aspect_ratio": aspect_ratio,
            "raw_source_aspect": aspect_ratio,
            "expansion_technique": None,
            "watermark_removed": bool(meta.get("watermark_removed", False)),
            "actual_cost": 0.0,
            "cost_currency": "USD",
            "credits_source": "GOOGLE_FLOW_PRO",
            "compiled_prompt": compiled_info.model_dump(),
        }

class GoogleOfficialOmniProvider:
    """Luồng sản xuất sử dụng mô hình Google Omni Flash 10s."""

    def __init__(self):
        self.provider_id = "GOOGLE_OMNI_FLASH"
        self.flow_provider = GoogleFlowZeroCostProvider()

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        prompt_language: str = "vi",
        include_audio: bool = True,
        workspace_id: str = "default_ws",
        remove_watermark: bool = False,
        flow_project_url: Optional[str] = None,
        on_flow_project_created: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Tạo video Flow theo tỷ lệ yêu cầu và chuẩn hóa đầu ra."""
        res = self.flow_provider.generate(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            prompt_language=prompt_language,
            include_audio=include_audio,
            workspace_id=workspace_id,
            remove_watermark=remove_watermark,
            flow_project_url=flow_project_url,
            on_flow_project_created=on_flow_project_created,
        )
        return res

class VideoOrchestrator:
    """Điều phối toàn bộ quy trình tạo và lắp ráp video dọc 9:16."""

    def __init__(self):
        self.flow_provider = GoogleFlowZeroCostProvider()
        self.omni_provider = GoogleOfficialOmniProvider()

    def generate_video_scene(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        prompt: str,
        aspect_ratio: str = "9:16",
        prompt_language: str = "vi",
        include_audio: bool = True,
        use_official_omni: bool = False,
        start_image_path: Optional[pathlib.Path] = None,
        start_image_asset_id: Optional[str] = None,
        project_id: Optional[str] = None,
        remove_watermark: bool = False,
        flow_project_url: Optional[str] = None,
        on_flow_project_created: Optional[Callable[[str], None]] = None,
    ) -> MediaAsset:
        if start_image_path:
            res = self.flow_provider.generate_from_image(
                prompt=prompt,
                image_path=start_image_path,
                aspect_ratio=aspect_ratio,
                include_audio=include_audio,
                workspace_id=workspace_id,
                flow_project_url=flow_project_url,
                on_flow_project_created=on_flow_project_created,
            )
        elif use_official_omni:
            res = self.omni_provider.generate(prompt=prompt, aspect_ratio=aspect_ratio, prompt_language=prompt_language, include_audio=include_audio, workspace_id=workspace_id, remove_watermark=remove_watermark, flow_project_url=flow_project_url, on_flow_project_created=on_flow_project_created)
        else:
            res = self.flow_provider.generate(prompt=prompt, aspect_ratio=aspect_ratio, prompt_language=prompt_language, include_audio=include_audio, workspace_id=workspace_id, remove_watermark=remove_watermark, flow_project_url=flow_project_url, on_flow_project_created=on_flow_project_created)

        v_path = pathlib.Path(res["storage_path"])
        meta = video_processor.probe_video(v_path)

        asset = MediaAsset(
            id=f"asset-{uuid.uuid4().hex[:12]}",
            workspace_id=workspace_id,
            project_id=project_id,
            storage_key=res["relative_storage_key"],
            sha256=res["sha256"],
            byte_size=res["byte_size"],
            mime_detected="video/mp4",
            source_product=res["source_product"],
            original_filename=res["filename"],
            created_by=user_id,
            parent_asset_id=start_image_asset_id,
            duration_ms=int(meta["duration_seconds"] * 1000),
            approval_state="UNREVIEWED"
        )

        db.add(asset)
        db.commit()
        db.refresh(asset)
        return asset

video_orchestrator = VideoOrchestrator()
