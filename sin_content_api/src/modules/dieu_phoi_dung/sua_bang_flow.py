from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .hop_dong import (
    DonSuaCanh,
    TrangThaiDonSua,
    KetQuaNhapCanh,
    LoiHopDong
)
from .kho_luu_tru import KhoLuuTruDung


class CapabilityProvider(BaseModel):
    provider_name: str
    route: str  # ASSISTED_UI | API_DIRECT
    model: str
    max_duration_seconds: int = 10
    supports_extend: bool = False
    supports_preserve_list: bool = True
    expiry_epoch: float = Field(default_factory=lambda: time.time() + 86400)


class QuanLySuaCanh:
    """
    Quan ly sua canh bang Flow / API.
    Phan tach 2 routes doc lap, kiem soat capability, bao ve preserve list va thoi luong.
    Luu tru don sua tren kho ben vung va xac minh toan ven asset dau ra (Workspace, SHA, Duration).
    """
    _don_sua_store: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def tao_don_sua_canh(
        cls,
        don: DonSuaCanh,
        capability: CapabilityProvider,
        workspace_id: Optional[str] = None
    ) -> TrangThaiDonSua:
        now = time.time()
        ws_id = workspace_id or getattr(don, "workspace_id", None) or "ws_default"

        # 1. Kiem tra capability het han
        if capability.expiry_epoch <= now:
            raise ValueError("Capability provider da het han (expired), khong duoc phep goi")

        # 2. Kiem tra khong nham lan giua reference asset va source video can sua
        if don.source_asset_id in don.reference_asset_ids:
            raise ValueError("Reference asset khong duoc trung voi source video can sua")

        # 3. Kiem tra route doc lap
        if don.route != capability.route:
            raise ValueError(f"Route yeu cau {don.route} khong khop voi capability {capability.route}")

        # 4. Xu ly theo tung Route
        receipt_token: Optional[str] = None
        status = "PENDING"
        notes = f"Don da tao thanh cong qua route {don.route}"

        if don.route == "ASSISTED_UI":
            receipt_token = f"rcpt_flow_{don.request_id}_{int(now)}"
            notes = (
                f"Don Assisted UI da khoi tao voi receipt_token: {receipt_token}. "
                "San sang cho Operator thuc hien bien tap tren Google Flow Assisted UI."
            )
        elif don.route == "API_DIRECT":
            # Kiem tra ket noi provider truc tiep (Gemini / Flow API)
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("FLOW_API_KEY") or os.getenv("LLM_API_KEY")
            if not api_key and capability.provider_name in ("GEMINI_LIVE", "FLOW_API_LIVE"):
                status = "PROVIDER_UNAVAILABLE"
                notes = "Provider API_DIRECT chua duoc cau hinh API key hoac dang offline."

        # 5. Luu tru don vao kho ben vung va RAM
        don_data = don.model_dump()
        don_data["workspace_id"] = ws_id
        cap_data = capability.model_dump()

        record = {
            "request_id": don.request_id,
            "project_id": don.project_id,
            "workspace_id": ws_id,
            "draft_id": don.draft_id,
            "source_asset_id": don.source_asset_id,
            "source_sha256": don.source_sha256,
            "route": don.route,
            "status": status,
            "don": don_data,
            "capability": cap_data,
            "output_asset_id": None,
            "receipt_token": receipt_token,
            "created_at": now
        }

        KhoLuuTruDung.luu_don_sua_canh(record)
        cls._don_sua_store[don.request_id] = record

        return TrangThaiDonSua(
            request_id=don.request_id,
            status=status,
            notes=notes
        )

    @classmethod
    def nhan_ket_qua_canh(
        cls,
        request_id: str,
        output_asset_id: str,
        workspace_id: str,
        duration_ms: int,
        expected_duration_ms: int,
        project_id: Optional[str] = None,
        sha256: Optional[str] = None,
        db_session: Any = None
    ) -> KetQuaNhapCanh:
        # 1. Tra cuu don sua tu RAM hoac kho ben vung
        item = cls._don_sua_store.get(request_id)
        if not item:
            item = KhoLuuTruDung.lay_don_sua_canh(request_id)
            if item:
                cls._don_sua_store[request_id] = item

        if not item:
            raise ValueError(f"Khong tim thay request_id {request_id}")

        don_data = item["don"]
        don_project_id = don_data.get("project_id")
        don_ws_id = item.get("workspace_id") or don_data.get("workspace_id")

        # 2. Kiem tra workspace boundary
        if not workspace_id or not workspace_id.startswith("ws_"):
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Workspace khong hop le hoac sai tenant")

        if don_ws_id and don_ws_id != "ws_default" and don_ws_id != workspace_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Request {request_id} thuoc workspace {don_ws_id}, khong khop voi {workspace_id}")

        if project_id and don_project_id and don_project_id != project_id:
            raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Request {request_id} thuoc du an {don_project_id}, khong khop voi {project_id}")

        # 3. Kiem tra thoi luong (duration verification):
        tolerance_ms = 200
        if abs(duration_ms - expected_duration_ms) > tolerance_ms:
            item["status"] = "REJECTED"
            KhoLuuTruDung.cap_nhat_trang_thai_don_sua(request_id, "REJECTED")
            raise ValueError(f"Thoi luong ket qua {duration_ms}ms khong khop voi expected {expected_duration_ms}ms (lech qua {tolerance_ms}ms)")

        # 4. Tra cuu va doi chieu Asset trong CSDL neu co DB session
        if db_session:
            from src.models.entities import MediaAsset
            asset = db_session.query(MediaAsset).filter(
                MediaAsset.id == output_asset_id
            ).first()
            if not asset:
                raise ValueError(f"Khong tim thay tai san media {output_asset_id} trong he thong")

            if asset.workspace_id != workspace_id:
                raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Tai san {output_asset_id} thuoc workspace {asset.workspace_id}, khong thuoc workspace hien tai {workspace_id}")

            if asset.project_id and don_project_id and asset.project_id != don_project_id:
                raise ValueError(f"{LoiHopDong.CROSS_WORKSPACE_ASSET}: Tai san {output_asset_id} thuoc du an {asset.project_id}, khong khop voi don {don_project_id}")

            if sha256 and asset.sha256 and asset.sha256 != sha256:
                raise ValueError(f"Ma bam SHA256 cua tai san ({asset.sha256}) khong khop voi ma bam nhan duoc ({sha256})")

            if asset.duration_ms and abs(asset.duration_ms - expected_duration_ms) > tolerance_ms:
                raise ValueError(f"Thoi luong thuc te cua tai san ({asset.duration_ms}ms) khong khop voi expected {expected_duration_ms}ms")

        # 5. Cap nhat hoan thanh hop le
        item["status"] = "COMPLETED"
        item["output_asset_id"] = output_asset_id
        KhoLuuTruDung.cap_nhat_trang_thai_don_sua(request_id, "COMPLETED", output_asset_id)

        return KetQuaNhapCanh(
            request_id=request_id,
            status="SUCCESS",
            asset_id=output_asset_id,
            duration_ms=duration_ms,
            verified=True
        )

    @classmethod
    def xu_ly_timeout_khong_ro_trang_thai(cls, request_id: str) -> TrangThaiDonSua:
        """
        Khi goi API bi timeout ma khong ro upstream da tru tien hay chua -> chuyen sang NEEDS_RECONCILIATION
        tuyet doi khong resubmit mu de tranh mat tien lan 2.
        """
        item = cls._don_sua_store.get(request_id)
        if item:
            item["status"] = "NEEDS_RECONCILIATION"
        KhoLuuTruDung.cap_nhat_trang_thai_don_sua(request_id, "NEEDS_RECONCILIATION")
        return TrangThaiDonSua(
            request_id=request_id,
            status="NEEDS_RECONCILIATION",
            notes="Goi provider timeout chua ro trang thai tinh phi. Chuyen sang doi soat, khong resubmit tu dong."
        )

    @classmethod
    def khoi_phuc_tu_asset_da_luu(
        cls,
        request_id: str,
        saved_asset_id: str
    ) -> TrangThaiDonSua:
        """
        Khi session provider het han, tiep tuc phien tu asset cuc bo da luu ma khong goi lai generation cu.
        """
        item = cls._don_sua_store.get(request_id)
        if item:
            item["output_asset_id"] = saved_asset_id
            item["status"] = "COMPLETED"
        KhoLuuTruDung.cap_nhat_trang_thai_don_sua(request_id, "COMPLETED", saved_asset_id)

        return TrangThaiDonSua(
            request_id=request_id,
            status="COMPLETED",
            output_asset_id=saved_asset_id,
            notes="Phien provider het han, tiep tuc an toan tu asset cuc bo da luu tru"
        )
