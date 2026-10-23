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
import sys
import uuid
import subprocess
from typing import Dict, Any, Optional, List
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
from session_manager import FlowLoginRequired

class GoogleFlowZeroCostProvider:
    """Luồng sản xuất video nội bộ 0đ chi phí sử dụng Google Flow AI Pro (Omni Flash 10s)."""

    def __init__(self):
        self.provider_id = "GOOGLE_FLOW_OMNI"

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        workspace_id: str = "default_ws",
        remove_watermark: bool = False
    ) -> Dict[str, Any]:
        """
        Quy trình chuẩn:
        Bước 0: Biên dịch câu lệnh người dùng thành Bộ lệnh Video 16:9 đầy đủ động học & góc máy.
        Bước 1: Flow Omni tạo video gốc tỷ lệ 16:9 (10 giây).
        Bước 2: Xử lý mở rộng (Outpainting Extension) chuyển 16:9 thành 9:16 (1080x1920) chuẩn TikTok, giữ đủ 10s.
        """
        target_dir = MEDIA_ROOT_DIR / "workspaces" / workspace_id / "media"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        job_hash = uuid.uuid4().hex[:10]
        expanded_9_16_filename = f"flow_expanded_9_16_{job_hash}.mp4"
        expanded_9_16_path = target_dir / expanded_9_16_filename

        # Bước 0: Biên dịch chỉ thị lệnh
        compiled_info = video_prompt_compiler.compile(
            user_prompt=prompt,
            aspect_ratio="16:9",
            duration_seconds=10
        )
        flow_directive = compiled_info.compiled_directive
        print(f"[HARNESS PROMPT COMPILER] Đã chuẩn hóa bộ lệnh cho Flow: {flow_directive[:80]}...", flush=True)

        # Bước 1: Gọi Flow Client điều khiển trình duyệt
        try:
            from google_flow_client import GoogleFlowClient
            client = GoogleFlowClient(headless=True)
            flow_res = client.create_video(
                prompt=flow_directive,
                aspect_ratio="16:9",
                workspace_id=workspace_id,
                timeout_sec=240
            )
            raw_16_9_path = pathlib.Path(flow_res["storage_path"])
        except Exception as flow_err:
            if isinstance(flow_err, FlowLoginRequired):
                raise
            raise RuntimeError(
                f"Google Flow: {flow_err}. "
                "Nếu video đã xuất hiện trên Flow, không tạo lại ngay; kiểm tra video trong project Flow và nhật ký tải kết quả của hệ thống."
            ) from flow_err

        # Bước 2: Tự động mở rộng video 16:9 thật của Flow thành 9:16 chuẩn TikTok (Blurred Backdrop Extension)
        meta_9_16 = video_processor.expand_16_9_to_9_16(
            input_video_path=raw_16_9_path,
            output_video_path=expanded_9_16_path,
            blur_strength=25,
            remove_watermark=remove_watermark
        )

        data = expanded_9_16_path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()

        return {
            "status": "SUCCEEDED",
            "provider": self.provider_id,
            "source_product": "GOOGLE_FLOW",
            "filename": expanded_9_16_filename,
            "storage_path": str(expanded_9_16_path),
            "relative_storage_key": f"workspaces/{workspace_id}/media/{expanded_9_16_filename}",
            "sha256": sha,
            "byte_size": len(data),
            "mime_detected": "video/mp4",
            "duration_ms": int(meta_9_16.get("duration_seconds", 10.0) * 1000),
            "aspect_ratio": "9:16",
            "raw_source_aspect": "16:9",
            "expansion_technique": "BLURRED_CANVAS_OUTPAINTING",
            "watermark_removed": bool(meta_9_16.get("watermark_removed", False)),
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
    ) -> Dict[str, Any]:
        """Tạo I2V trong Flow rồi chuẩn hóa thành video dọc 9:16."""
        target_dir = MEDIA_ROOT_DIR / "workspaces" / workspace_id / "media"
        target_dir.mkdir(parents=True, exist_ok=True)
        compiled_info = video_prompt_compiler.compile(user_prompt=prompt, aspect_ratio="16:9", duration_seconds=10)
        filename = f"flow_i2v_9_16_{uuid.uuid4().hex[:10]}.mp4"
        output_path = target_dir / filename
        try:
            from google_flow_client import GoogleFlowClient
            flow_res = GoogleFlowClient(headless=True).create_video(
                prompt=compiled_info.compiled_directive,
                aspect_ratio="16:9",
                workspace_id=workspace_id,
                timeout_sec=240,
                start_image_path=image_path,
            )
            meta = video_processor.expand_16_9_to_9_16(
                input_video_path=pathlib.Path(flow_res["storage_path"]),
                output_video_path=output_path,
                blur_strength=25,
                remove_watermark=False,
            )
        except FlowLoginRequired:
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
            "aspect_ratio": "9:16",
            "raw_source_aspect": "16:9",
            "expansion_technique": "BLURRED_CANVAS_OUTPAINTING",
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
        workspace_id: str = "default_ws",
        remove_watermark: bool = False
    ) -> Dict[str, Any]:
        """Tạo video 16:9 từ mô hình Omni 10s và mở rộng sang 9:16 chuẩn TikTok."""
        res = self.flow_provider.generate(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            workspace_id=workspace_id,
            remove_watermark=remove_watermark
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
        use_official_omni: bool = False,
        start_image_path: Optional[pathlib.Path] = None,
        start_image_asset_id: Optional[str] = None,
        project_id: Optional[str] = None,
        remove_watermark: bool = False
    ) -> MediaAsset:
        if start_image_path:
            res = self.flow_provider.generate_from_image(
                prompt=prompt,
                image_path=start_image_path,
                workspace_id=workspace_id,
            )
        elif use_official_omni:
            res = self.omni_provider.generate(prompt=prompt, aspect_ratio=aspect_ratio, workspace_id=workspace_id, remove_watermark=remove_watermark)
        else:
            res = self.flow_provider.generate(prompt=prompt, aspect_ratio=aspect_ratio, workspace_id=workspace_id, remove_watermark=remove_watermark)

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
