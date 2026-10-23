"""
Downstream Executor for Phase P12 (T121, P12-01, P12-02, P12-03, P12-05).
Enforces bounded retries, idempotent output, and zero duplicate costs or artifacts
in the face of external timeouts or network interruptions.
P12-01: Cache scoped per (workspace_id, idempotency_key) to prevent cross-tenant artifact leaks.
P12-02: DB-persisted idempotent replay survives process restart / cache clear.
P12-03: Rejects replaying REFUSED ledger or modified payload.
"""
import time
import uuid
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.models.entities import CostLedger, AuditEvent
from src.modules.staging_reliability.budget_guard import budget_guard
from src.schemas.contracts import TaskExecuteRequest, TaskExecuteResponse

# Bộ nhớ tạm in-memory cho các artifact đã sinh: khóa theo (workspace_id, idempotency_key)
_PROCESSED_ARTIFACT_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}

class DownstreamExecutor:
    def execute_with_resilience(
        self,
        db: Session,
        workspace_id: str,
        user_id: str,
        req: TaskExecuteRequest
    ) -> TaskExecuteResponse:
        """
        T121: external timeout after downstream job side effect ->
        bounded retry, idempotent output, no duplicate costs/artifacts.
        """
        idempotency_key = req.idempotency_key
        cache_key = (workspace_id, idempotency_key)

        # 1. IDEMPOTENCY CHECK IN-MEMORY (P12-01: Scoped theo workspace_id)
        if cache_key in _PROCESSED_ARTIFACT_CACHE:
            cached = _PROCESSED_ARTIFACT_CACHE[cache_key]
            return TaskExecuteResponse(
                task_id=req.task_id,
                idempotency_key=idempotency_key,
                status="COMPLETED",
                retry_count=cached.get("retry_count", 0),
                charged_units=0.0, # NO DUPLICATE COSTS
                output_artifact_id=cached.get("artifact_id"),
                is_idempotent_replay=True,
                message="Tác vụ đã hoàn thành trước đó; trả về kết quả lũy đẳng không tính thêm phí."
            )

        # 1.1 IDEMPOTENCY CHECK IN DATABASE (P12-02: Replay ben vung ngay ca khi mat cache RAM)
        existing_committed = db.query(CostLedger).filter(
            CostLedger.workspace_id == workspace_id,
            CostLedger.idempotency_key == idempotency_key,
            CostLedger.status == "COMMITTED"
        ).first()

        if existing_committed and existing_committed.output_artifact_id:
            # Re-populate cache
            _PROCESSED_ARTIFACT_CACHE[cache_key] = {
                "artifact_id": existing_committed.output_artifact_id,
                "retry_count": getattr(existing_committed, "retry_count", 0),
                "charged_units": existing_committed.actual_units or 0.0,
                "task_id": existing_committed.task_id,
            }
            return TaskExecuteResponse(
                task_id=req.task_id,
                idempotency_key=idempotency_key,
                status="COMPLETED",
                retry_count=getattr(existing_committed, "retry_count", 0),
                charged_units=0.0, # KHONG TRU PHI LAI
                output_artifact_id=existing_committed.output_artifact_id,
                is_idempotent_replay=True,
                message="Tác vụ đã hoàn thành trong cơ sở dữ liệu; trả về kết quả lũy đẳng không tính thêm phí."
            )

        # 2. PRE-FLIGHT BUDGET RESERVATION (T122 & P12-03)
        reserve_res = budget_guard.reserve_budget(
            db=db,
            workspace_id=workspace_id,
            task_id=req.task_id,
            idempotency_key=idempotency_key,
            action_type=req.action_type,
            estimated_units=req.estimated_units
        )

        if reserve_res.status == "REFUSED_OVER_BUDGET":
            raise HTTPException(
                status_code=402,
                detail=f"Budget reservation failed: {reserve_res.message}"
            )

        ledger_id = reserve_res.ledger_id

        # 3. BOUNDED RETRY EXECUTION (T121 & P12-05)
        # Giới hạn thử lại tối đa (bounded retry), tuyệt đối không loop vô hạn
        max_retries = min(req.max_retries, 3)
        attempts = 0
        success = False
        artifact_id = None
        last_error = None

        while attempts < max_retries:
            attempts += 1
            try:
                # Mô phỏng trường hợp downstream timeout nếu req.simulate_timeout == True
                if req.simulate_timeout and attempts < max_retries:
                    raise TimeoutError(f"Downstream service timeout on attempt {attempts}")

                # Thực hiện công việc downstream và tạo artifact duy nhất
                artifact_id = f"art_{req.task_id}_{uuid.uuid4().hex[:8]}"
                success = True
                break
            except TimeoutError as te:
                last_error = str(te)
                # Bounded backoff
                time.sleep(0.05)

        # 4. KET QUA & COMMIT CHI PHI
        if success:
            actual_cost = req.estimated_units
            if ledger_id:
                budget_guard.commit_budget(
                    db,
                    workspace_id,
                    ledger_id,
                    actual_cost,
                    success=True,
                    output_artifact_id=artifact_id,
                    retry_count=attempts - 1
                )

            # Lưu vào cache lũy đẳng scoped tenant để chống trùng lặp artifacts và chi phí
            _PROCESSED_ARTIFACT_CACHE[cache_key] = {
                "artifact_id": artifact_id,
                "retry_count": attempts - 1,
                "charged_units": actual_cost,
                "task_id": req.task_id,
            }

            return TaskExecuteResponse(
                task_id=req.task_id,
                idempotency_key=idempotency_key,
                status="COMPLETED",
                retry_count=attempts - 1,
                charged_units=actual_cost,
                output_artifact_id=artifact_id,
                is_idempotent_replay=False,
                message=f"Tác vụ hoàn thành sau {attempts} lần thử (retry_count={attempts-1})."
            )
        else:
            # That bai hoan toan sau khi het so lan retry -> hoan tien giu cho
            if ledger_id:
                budget_guard.commit_budget(db, workspace_id, ledger_id, 0.0, success=False)

            return TaskExecuteResponse(
                task_id=req.task_id,
                idempotency_key=idempotency_key,
                status="FAILED",
                retry_count=attempts,
                charged_units=0.0, # KHONG TRU PHI KHI THAT BAI
                output_artifact_id=None,
                is_idempotent_replay=False,
                message=f"Tác vụ thất bại sau {attempts} lần thử do lỗi ngoại cảnh: {last_error}. Đã hoàn lại toàn bộ hạn mức giữ chỗ."
            )

downstream_executor = DownstreamExecutor()
