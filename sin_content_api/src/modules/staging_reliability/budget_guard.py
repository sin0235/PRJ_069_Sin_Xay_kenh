"""
Budget Guard Service for Phase P12 (T122, P12-03, P12-04).
Enforces strict pre-flight budget cap check: tasks estimated > available cap are refused before billable work.
Prevents reservation overruns with atomic database updates and reconciles vendor billing with discrepancy alerting.
P12-03: Rejects IDEMPOTENT_HIT on previously REFUSED ledgers or mismatched payloads.
P12-04: Atomic reservation query prevents concurrent race-condition overruns.
"""
from datetime import datetime, timezone
import math
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.models.entities import WorkspaceBudget, CostLedger, AuditEvent
from src.schemas.contracts import BudgetReserveResponse, ReconciliationResponse

class BudgetGuard:
    def get_or_create_budget(self, db: Session, workspace_id: str, default_allocated: float = 100.0) -> WorkspaceBudget:
        budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == workspace_id).first()
        if not budget:
            budget = WorkspaceBudget(
                workspace_id=workspace_id,
                allocated_units=default_allocated,
                reserved_units=0.0,
                spent_units=0.0,
                hard_limit_units=default_allocated,
                alert_threshold_percent=80.0
            )
            db.add(budget)
            db.commit()
            db.refresh(budget)
        return budget

    def reserve_budget(
        self,
        db: Session,
        workspace_id: str,
        task_id: str,
        idempotency_key: str,
        action_type: str,
        estimated_units: float,
    ) -> BudgetReserveResponse:
        """
        T122 & P12-03 & P12-04:
        Budget of 1 unit and task estimated > cap -> refused/rescoped before billable work.
        Enforces atomic reservation to avoid concurrent overruns.
        Ranh gioi bao ve: Tu choi estimated_units <= 0 hoac khong huu han.
        """
        if not isinstance(estimated_units, (int, float)) or isinstance(estimated_units, bool) or not math.isfinite(estimated_units) or estimated_units <= 0:
            raise HTTPException(
                status_code=422,
                detail=f"Số ngân sách ước tính phải là số thực dương hữu hạn (nhận được: {estimated_units}). Không thể giữ chỗ ngân sách âm hoặc bằng 0."
            )

        # 1. Kiem tra tinh luy dang theo (workspace_id, idempotency_key)
        existing_ledger = db.query(CostLedger).filter(
            CostLedger.workspace_id == workspace_id,
            CostLedger.idempotency_key == idempotency_key
        ).first()

        budget = self.get_or_create_budget(db, workspace_id)
        available_units = round(budget.allocated_units - (budget.spent_units + budget.reserved_units), 4)

        if existing_ledger:
            # P12-03: Neu ledger truoc do da bi REFUSED -> Tiep tuc tu choi, KHONG cho phep thuc thi!
            if existing_ledger.status == "REFUSED":
                return BudgetReserveResponse(
                    status="REFUSED_OVER_BUDGET",
                    ledger_id=existing_ledger.id,
                    allocated_units=budget.allocated_units,
                    available_units=available_units,
                    reserved_units=budget.reserved_units,
                    message="Tác vụ đã bị từ chối trước đó do vượt quá ngân sách khả dụng."
                )

            # P12-03: Neu goi lai voi estimated_units khac ledger da giu cho -> Tu choi de bao ve tinh nhat quan
            if abs(existing_ledger.estimated_units - estimated_units) > 1e-4:
                raise HTTPException(
                    status_code=409,
                    detail=f"Idempotency key '{idempotency_key}' payload mismatch: previously reserved {existing_ledger.estimated_units} units, got {estimated_units}."
                )

            return BudgetReserveResponse(
                status="IDEMPOTENT_HIT",
                ledger_id=existing_ledger.id,
                allocated_units=budget.allocated_units,
                available_units=available_units,
                reserved_units=budget.reserved_units,
                message="Tác vụ đã được đăng ký trước đó với idempotency_key tương ứng."
            )

        # 2. P12-04: ATOMIC RESERVATION (Chong race-condition mat du lieu / vuot cap giua hai session)
        # Cap nhat nguyen tu co dieu kien tren database
        updated = db.query(WorkspaceBudget).filter(
            WorkspaceBudget.id == budget.id,
            (WorkspaceBudget.allocated_units - WorkspaceBudget.spent_units - WorkspaceBudget.reserved_units) >= estimated_units
        ).update(
            {WorkspaceBudget.reserved_units: WorkspaceBudget.reserved_units + estimated_units},
            synchronize_session="fetch"
        )

        if updated == 0:
            # T122: TU CHOI NGAY TRUOC KHI THUC HIEN BAT KY BILLABLE WORK NAO
            refused_ledger = CostLedger(
                workspace_id=workspace_id,
                task_id=task_id,
                idempotency_key=idempotency_key,
                action_type=action_type,
                estimated_units=estimated_units,
                actual_units=0.0,
                status="REFUSED",
            )
            db.add(refused_ledger)
            db.commit()
            db.refresh(refused_ledger)

            return BudgetReserveResponse(
                status="REFUSED_OVER_BUDGET",
                ledger_id=refused_ledger.id,
                allocated_units=budget.allocated_units,
                available_units=available_units,
                reserved_units=budget.reserved_units,
                message=f"Từ chối tác vụ: Ngân sách khả dụng ({available_units}) không đủ để đáp ứng ước tính ({estimated_units}). Không có chi phí nào phát sinh."
            )

        # Giu cho thanh cong -> Ghi nhan CostLedger
        ledger = CostLedger(
            workspace_id=workspace_id,
            task_id=task_id,
            idempotency_key=idempotency_key,
            action_type=action_type,
            estimated_units=estimated_units,
            actual_units=None,
            status="RESERVED",
        )
        db.add(ledger)
        db.commit()
        db.refresh(ledger)
        db.refresh(budget)

        new_available = round(budget.allocated_units - (budget.spent_units + budget.reserved_units), 4)
        return BudgetReserveResponse(
            status="RESERVED",
            ledger_id=ledger.id,
            allocated_units=budget.allocated_units,
            available_units=new_available,
            reserved_units=budget.reserved_units,
            message="Đã giữ chỗ ngân sách thành công trước khi thực thi."
        )

    def commit_budget(
        self,
        db: Session,
        workspace_id: str,
        ledger_id: str,
        actual_units: float,
        success: bool = True,
        output_artifact_id: Optional[str] = None,
        retry_count: int = 0
    ) -> CostLedger:
        """
        Ket thuc cong viec: giai phong phan giu cho va ghi nhan chi phi thuc te.
        P12-02: Luu giu output_artifact_id va retry_count de phuc vu replay ben vung.
        """
        ledger = db.query(CostLedger).filter(
            CostLedger.id == ledger_id,
            CostLedger.workspace_id == workspace_id
        ).first()
        if not ledger:
            raise HTTPException(status_code=404, detail="Ledger not found")

        budget = self.get_or_create_budget(db, workspace_id)

        # Giai phong phan giu cho
        budget.reserved_units = max(0.0, round(budget.reserved_units - ledger.estimated_units, 4))

        if success:
            budget.spent_units = round(budget.spent_units + actual_units, 4)
            ledger.actual_units = actual_units
            ledger.status = "COMMITTED"
            if output_artifact_id:
                ledger.output_artifact_id = output_artifact_id
            ledger.retry_count = retry_count
        else:
            ledger.actual_units = 0.0
            ledger.status = "REFUNDED"

        db.commit()
        db.refresh(ledger)
        return ledger

    def reconcile_vendor_billing(
        self,
        db: Session,
        workspace_id: str,
        ledger_id: str,
        vendor_reported_units: float,
        tolerance_percent: float = 10.0
    ) -> ReconciliationResponse:
        """
        T122: Separately reconcile vendor billing and alert on discrepancies.
        """
        ledger = db.query(CostLedger).filter(
            CostLedger.id == ledger_id,
            CostLedger.workspace_id == workspace_id
        ).first()
        if not ledger:
            raise HTTPException(status_code=404, detail="Ledger record not found")

        ledger.vendor_reported_units = vendor_reported_units

        internal_units = ledger.actual_units if ledger.actual_units is not None else ledger.estimated_units
        discrepancy = round(abs(vendor_reported_units - internal_units), 4)

        threshold = internal_units * (tolerance_percent / 100.0)
        has_discrepancy = discrepancy > threshold

        ledger.discrepancy_alert = has_discrepancy

        if has_discrepancy:
            audit = AuditEvent(
                workspace_id=workspace_id,
                actor_id="SYSTEM_BILLING_RECONCILER",
                event_type="BILLING_DISCREPANCY_DETECTED",
                details=f"Vendor billed {vendor_reported_units} units vs internal {internal_units} units (delta={discrepancy}). Discrepancy alert raised."
            )
            db.add(audit)

        db.commit()
        db.refresh(ledger)

        msg = "Đối soát hóa đơn vendor thành công; số liệu khớp trong dung sai cho phép."
        if has_discrepancy:
            msg = f"CẢNH BÁO: Sai lệch chi phí vượt ngưỡng cho phép! Nội bộ: {internal_units}, Vendor: {vendor_reported_units}, Chênh lệch: {discrepancy} units."

        return ReconciliationResponse(
            ledger_id=ledger.id,
            actual_units=internal_units,
            vendor_reported_units=vendor_reported_units,
            discrepancy_delta=discrepancy,
            discrepancy_alert=has_discrepancy,
            reconciled=True,
            message=msg
        )

budget_guard = BudgetGuard()
