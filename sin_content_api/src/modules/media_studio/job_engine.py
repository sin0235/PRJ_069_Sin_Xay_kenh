# -*- coding: utf-8 -*-
"""Động cơ điều phối tác vụ sinh media AI (AI Media Job Engine & State Machine).
Hiện thực hóa các yêu cầu B03 (Idempotency), B06 (Lỗi & Bounded Retry), B07/GF05-02 (Ngân sách & Hard Cap),
GF05-04 (Tách biệt sổ cái Flow 0đ vs Cloud Billing), GF05-05 (Reconciliation khi timeout),
GF05-07 (Session Revocation) và GF05-08 (Feature Flag Toggles).
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models.entities import AIGenerationJob, WorkspaceBudget, CostLedger
from src.modules.staging_reliability.budget_guard import budget_guard
from src.schemas.contracts import AIGenerationJobCreate

def utc_now():
    return datetime.now(timezone.utc)

class FakeProviderSimulator:
    """Bộ giả lập nhà cung cấp để kiểm thử lỗi, retry, state machine và đối soát ngân sách (B03, B06, GF05-05)."""

    @staticmethod
    def execute(job: AIGenerationJob, sim_mode: str = "SUCCESS") -> Dict[str, Any]:
        """
        Mô phỏng phản hồi từ Provider:
        - SUCCESS: Hoàn tất thành công, sinh ID output.
        - HTTP_401: Lỗi xác thực khóa bí mật -> không retry.
        - HTTP_429: Bị giới hạn tần suất -> retry tối đa 3 lần.
        - HTTP_500: Lỗi máy chủ nhà cung cấp -> retry tối đa 3 lần.
        - TIMEOUT: Hết thời gian chờ kết nối -> retry tối đa 3 lần.
        - TIMEOUT_UNCERTAIN_BILL: Mất kết nối không xác định được trạng thái trừ tiền -> NEEDS_RECONCILIATION.
        """
        if sim_mode == "HTTP_401":
            return {
                "success": False,
                "status_code": 401,
                "error_code": "AUTH_DENIED",
                "message": "Khóa API không hợp lệ hoặc đã bị vô hiệu hóa bởi nhà cung cấp.",
                "retryable": False
            }
        elif sim_mode == "HTTP_429":
            return {
                "success": False,
                "status_code": 429,
                "error_code": "RATE_LIMITED",
                "message": "Quá hạn mức số lượt yêu cầu đồng thời (429 Too Many Requests).",
                "retryable": True
            }
        elif sim_mode == "HTTP_500":
            return {
                "success": False,
                "status_code": 500,
                "error_code": "PROVIDER_INTERNAL_ERROR",
                "message": "Máy chủ nhà cung cấp gặp sự cố nội bộ (500).",
                "retryable": True
            }
        elif sim_mode == "TIMEOUT":
            return {
                "success": False,
                "status_code": 504,
                "error_code": "DOWNSTREAM_TIMEOUT",
                "message": "Hết thời gian chờ kết nối tới dịch vụ AI.",
                "retryable": True
            }
        elif sim_mode == "TIMEOUT_UNCERTAIN_BILL":
            return {
                "success": False,
                "status_code": 504,
                "error_code": "NEEDS_RECONCILIATION",
                "message": "Mất kết nối với nhà cung cấp không xác định được trạng thái trừ tiền. Tác vụ bị phong tỏa chờ đối soát.",
                "retryable": False,
                "needs_reconciliation": True
            }
        else:
            # SUCCESS
            return {
                "success": True,
                "status_code": 200,
                "output_asset_ids": [f"asset-fake-{uuid.uuid4().hex[:8]}"],
                "actual_cost": job.estimated_cost
            }

class JobEngine:
    """Động cơ quản lý vòng đời tác vụ AI sinh media và kiểm soát ngân sách đa tenant."""

    def submit_job(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        payload: AIGenerationJobCreate,
        budget_cap: Optional[float] = None
    ) -> AIGenerationJob:
        """
        Tiếp nhận và khởi tạo tác vụ sinh media:
        - B03: Kiểm tra lũy đẳng (Idempotency Key) chống tính phí hai lần.
        - GF05-01: Cách ly tuyệt đối giữa các tenant, không để lộ metadata.
        - GF05-02 & B07: Kiểm tra trần ngân sách (Pre-flight Budget Guard) trước khi thực thi việc tính phí.
        - GF05-03: Kiểm tra báo giá so với trần ngân sách được phê duyệt (Re-approval requirement).
        - GF05-04: Tách biệt sổ cái Flow 0đ vs Cloud Billing (riêng biệt native units).
        - GF05-05: Chặn gửi lại tác vụ đang trong trạng thái NEEDS_RECONCILIATION.
        - GF05-07: Chặn thực thi khi phiên đăng nhập bị thu hồi (SESSION_REVOKED).
        - GF05-08: Tôn trọng cờ tính năng Flow Pilot (FEATURE_FLAG_DISABLED).
        - B08: Chặn khi thiếu khóa API nhà cung cấp (BLOCKED_CREDENTIALS).
        """
        # 1. Kiểm tra tính lũy đẳng (Idempotency check - B03 & GF05-05)
        existing_job = db.query(AIGenerationJob).filter(
            AIGenerationJob.idempotency_key == payload.idempotency_key
        ).first()

        if existing_job:
            # Chặn truy cập chéo tenant (GF05-01: No cross-tenant metadata leakage)
            if existing_job.workspace_id != workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "JOB_NOT_FOUND", "message": "Không tìm thấy tác vụ AI."}
                )

            # GF05-05: Nếu tác vụ trước đó rơi vào trạng thái NEEDS_RECONCILIATION -> Chặn thử lại ngay
            if existing_job.state == "NEEDS_RECONCILIATION":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "NEEDS_RECONCILIATION",
                        "message": "Tác vụ đang ở trạng thái cần đối soát ngân sách với nhà cung cấp. Bị phong tỏa để ngăn chặn việc trừ tiền trùng lặp."
                    }
                )

            # Trả về ngay bản ghi hiện có, không chạy lại, không phát sinh chi phí
            return existing_job

        # 2. Kiểm tra cờ tính năng (Feature Flag Gate - GF05-08)
        flow_pilot_enabled = os.getenv("FLOW_PILOT_ENABLED", "true").lower() in ("true", "1", "yes")
        if payload.provider in ("FLOW_MUSIC_ASSISTED", "GOOGLE_FLOW", "GOOGLE_FLOW_ASSISTED") and not flow_pilot_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "FEATURE_FLAG_DISABLED",
                    "message": "Tính năng Flow Pilot hiện đang tạm khóa hoặc đã bị vô hiệu hóa bởi chính sách quản trị."
                }
            )

        # 3. Kiểm tra trạng thái phiên đăng nhập (Session Revocation Gate - GF05-07)
        flow_session_revoked = os.getenv("FLOW_SESSION_REVOKED", "false").lower() in ("true", "1", "yes")
        if payload.provider in ("FLOW_MUSIC_ASSISTED", "GOOGLE_FLOW", "GOOGLE_FLOW_ASSISTED") and flow_session_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "SESSION_REVOKED",
                    "message": "Phiên làm việc Google Flow đã hết hạn hoặc bị thu hồi quyền truy cập. Vui lòng đăng nhập lại."
                }
            )

        # 4. Kiểm tra trần ngân sách & Giữ chỗ (Budget Hardening Gate - B07, GF05-02, GF05-03, GF05-04)
        is_billable = payload.provider in ("GOOGLE_OFFICIAL", "GOOGLE_OFFICIAL_OMNI", "GOOGLE_OFFICIAL_LYRIA") or (
            payload.provider == "FAKE_PROVIDER" and payload.estimated_cost > 0.0
        )
        ledger_id: Optional[str] = None

        if is_billable:
            # Luồng tính phí Cloud Billing: Bắt buộc kiểm tra trần ngân sách khả dụng (Pre-flight)
            reserve_res = budget_guard.reserve_budget(
                db=db,
                workspace_id=workspace_id,
                task_id=f"job-{payload.idempotency_key}",
                idempotency_key=payload.idempotency_key,
                action_type=f"ai_media_{payload.asset_type.lower()}",
                estimated_units=payload.estimated_cost
            )

            if reserve_res.status == "REFUSED_OVER_BUDGET":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error_code": "BUDGET_EXCEEDED",
                        "message": f"Từ chối tác vụ: Ngân sách khả dụng ({reserve_res.available_units}$) không đủ để đáp ứng ước tính ({payload.estimated_cost}$). Không có chi phí nào phát sinh.",
                        "available_units": reserve_res.available_units,
                        "estimated_units": payload.estimated_cost
                    }
                )
            ledger_id = reserve_res.ledger_id

            # GF05-03: Kiểm tra mức giá ước tính so với hạn mức ngân sách được duyệt
            if budget_cap is not None and payload.estimated_cost > budget_cap:
                budget_guard.commit_budget(db, workspace_id, ledger_id, actual_units=0.0, success=False)
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error_code": "BUDGET_CAP_EXCEEDED",
                        "message": f"Chi phí dự kiến ({payload.estimated_cost}$) vượt quá hạn mức ngân sách được cấp ({budget_cap}$). Yêu cầu tái phê duyệt hạn mức.",
                        "estimated_cost": payload.estimated_cost,
                        "budget_cap": budget_cap
                    }
                )
        else:
            # Luồng Zero-Cost Flow Pilot (GF05-04):
            # Chi phí gọi API = 0.00$. Không trừ ngân sách Cloud Billing.
            # Lưu CostLedger riêng với native units và credits_source riêng biệt.
            ledger = CostLedger(
                workspace_id=workspace_id,
                task_id=f"job-{payload.idempotency_key}",
                idempotency_key=payload.idempotency_key,
                action_type=f"flow_pilot_{payload.asset_type.lower()}",
                estimated_units=0.0,
                actual_units=0.0,
                status="COMMITTED"
            )
            db.add(ledger)
            db.commit()
            ledger_id = ledger.id

        # 5. Kiểm tra thông tin xác thực nhà cung cấp (No Credentials Gate - B08)
        if payload.provider in ("GOOGLE_OFFICIAL", "GOOGLE_OFFICIAL_OMNI", "GOOGLE_OFFICIAL_LYRIA"):
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                if ledger_id and is_billable:
                    budget_guard.commit_budget(db, workspace_id, ledger_id, actual_units=0.0, success=False)

                job = AIGenerationJob(
                    id=str(uuid.uuid4()),
                    workspace_id=workspace_id,
                    project_id=payload.project_id,
                    asset_type=payload.asset_type,
                    provider=payload.provider,
                    provider_mode=payload.provider_mode,
                    model_id=payload.model_id,
                    idempotency_key=payload.idempotency_key,
                    state="FAILED",
                    request_payload_json=json.dumps(payload.parameters),
                    estimated_cost=payload.estimated_cost,
                    actual_cost=0.0,
                    credits_source="API_BILLING",
                    error_code="BLOCKED_CREDENTIALS",
                    error_message="Chưa cấu hình Google Cloud API Key / Billing cho dự án. Tác vụ bị chặn để bảo vệ hệ thống.",
                    created_by=user_id,
                    created_at=utc_now(),
                    finished_at=utc_now()
                )
                db.add(job)
                db.commit()
                db.refresh(job)
                return job

        # 6. Khởi tạo tác vụ trong hàng đợi (State: QUEUED)
        job = AIGenerationJob(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            project_id=payload.project_id,
            asset_type=payload.asset_type,
            provider=payload.provider,
            provider_mode=payload.provider_mode,
            model_id=payload.model_id,
            idempotency_key=payload.idempotency_key,
            state="QUEUED",
            request_payload_json=json.dumps(payload.parameters),
            estimated_cost=payload.estimated_cost,
            actual_cost=0.0,
            credits_source="FLOW_MUSIC_PLUS" if payload.provider == "FLOW_MUSIC_ASSISTED" else (
                "GOOGLE_FLOW_PRO" if payload.provider in ("GOOGLE_FLOW", "GOOGLE_FLOW_ASSISTED") else "API_BILLING"
            ),
            created_by=user_id,
            created_at=utc_now()
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # 7. Thực thi tích hợp Flow (Flow-First, Chi phí 0đ) hoặc FAKE_PROVIDER (B06)
        if payload.provider == "FAKE_PROVIDER":
            sim_mode = payload.parameters.get("simulate_error", "SUCCESS")
            self._process_fake_job(db, job, sim_mode, ledger_id, is_billable)
        elif payload.provider in ("FLOW_MUSIC_ASSISTED", "GOOGLE_FLOW", "GOOGLE_FLOW_ASSISTED"):
            self._process_flow_job(db, job, payload)

        return job

    def _process_flow_job(self, db: Session, job: AIGenerationJob, payload: AIGenerationJobCreate):
        """Thực thi tác vụ Flow tự động qua Flow Provider (0đ chi phí gọi API)."""
        job.state = "RUNNING"
        db.commit()

        try:
            if payload.provider == "FLOW_MUSIC_ASSISTED":
                from src.modules.media_studio.music_provider import music_orchestrator
                res = music_orchestrator.flow_provider.generate(
                    prompt=payload.prompt_text,
                    genre=payload.parameters.get("genre", "Pop"),
                    mood=payload.parameters.get("mood", "Upbeat"),
                    lyrics=payload.parameters.get("lyrics"),
                    workspace_id=job.workspace_id
                )
            else:
                from src.modules.media_studio.video_provider import video_orchestrator
                res = video_orchestrator.flow_provider.generate(
                    prompt=payload.prompt_text,
                    aspect_ratio=payload.parameters.get("aspect_ratio", "9:16"),
                    workspace_id=job.workspace_id
                )

            from src.models.entities import MediaAsset
            asset = MediaAsset(
                id=str(uuid.uuid4()),
                workspace_id=job.workspace_id,
                project_id=job.project_id,
                storage_key=res["relative_storage_key"],
                sha256=res["sha256"],
                byte_size=res["byte_size"],
                mime_detected=res["mime_detected"],
                duration_ms=res.get("duration_ms", 60000),
                source_product=res["source_product"],
                original_filename=res["filename"],
                approval_state="UNREVIEWED",
                created_by=job.created_by
            )
            db.add(asset)

            # Cập nhật job hoàn tất với chi phí 0đ
            job.state = "SUCCEEDED"
            job.actual_cost = 0.0
            job.output_asset_ids_json = json.dumps([asset.id])
            job.finished_at = utc_now()
            db.commit()

        except Exception as e:
            job.state = "FAILED"
            job.error_code = "FLOW_EXECUTION_ERROR"
            job.error_message = str(e)
            job.finished_at = utc_now()
            db.commit()

    def _process_fake_job(
        self,
        db: Session,
        job: AIGenerationJob,
        sim_mode: str,
        ledger_id: Optional[str] = None,
        is_billable: bool = False
    ):
        """Thực hiện chu trình chuyển đổi trạng thái với cơ chế Bounded Retry và đối soát ngân sách (B06, GF05-05)."""
        job.state = "RUNNING"
        db.commit()

        max_retries = 3
        current_retry = 0

        while current_retry <= max_retries:
            resp = FakeProviderSimulator.execute(job, sim_mode)

            if resp.get("needs_reconciliation"):
                # GF05-05: Chuyển sang trạng thái NEEDS_RECONCILIATION
                job.state = "NEEDS_RECONCILIATION"
                job.error_code = "NEEDS_RECONCILIATION"
                job.error_message = resp.get("message")
                job.finished_at = utc_now()
                db.commit()
                return

            if resp["success"]:
                job.state = "SUCCEEDED"
                job.actual_cost = resp.get("actual_cost", job.estimated_cost)
                job.output_asset_ids_json = json.dumps(resp.get("output_asset_ids", []))
                job.finished_at = utc_now()
                db.commit()

                if ledger_id and is_billable:
                    budget_guard.commit_budget(
                        db=db,
                        workspace_id=job.workspace_id,
                        ledger_id=ledger_id,
                        actual_units=job.actual_cost,
                        success=True
                    )
                return

            # Xử lý lỗi không thể retry (Ví dụ: 401 AUTH_DENIED)
            if not resp.get("retryable", False):
                job.state = "FAILED"
                job.error_code = resp.get("error_code")
                job.error_message = resp.get("message")
                job.retry_count = current_retry
                job.finished_at = utc_now()
                db.commit()

                if ledger_id and is_billable:
                    budget_guard.commit_budget(
                        db=db,
                        workspace_id=job.workspace_id,
                        ledger_id=ledger_id,
                        actual_units=0.0,
                        success=False
                    )
                return

            # Xử lý lỗi có thể retry (429, 500, timeout)
            current_retry += 1
            job.retry_count = current_retry
            db.commit()

            if current_retry > max_retries:
                # Đã vượt quá số lần thử lại tối đa
                job.state = "FAILED"
                job.error_code = f"MAX_RETRIES_EXCEEDED_{resp.get('error_code')}"
                job.error_message = f"Đã thử lại {max_retries} lần nhưng vẫn gặp sự cố: {resp.get('message')}"
                job.finished_at = utc_now()
                db.commit()

                if ledger_id and is_billable:
                    budget_guard.commit_budget(
                        db=db,
                        workspace_id=job.workspace_id,
                        ledger_id=ledger_id,
                        actual_units=0.0,
                        success=False
                    )
                return

job_engine = JobEngine()
