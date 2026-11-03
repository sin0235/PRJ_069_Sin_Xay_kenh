from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.tenancy import TenantContext, require_action
from src.database import get_db as get_content_db
from src.models.entities import MediaAsset, ProductionProject
from src.modules.llm.client import LLMClient
from src.modules.media_queue.service import enqueue_media_job
from .hop_dong import (
    TimelineV2,
    DinhDanhPhien,
    ChinhSachPhien,
    LenhDung,
    KetQuaCongCu,
    DonSuaCanh,
    TrangThaiDonSua,
    KetQuaNhapCanh,
    GoiBanGiao,
    LoiHopDong
)
from .phien_dung import QuanLyPhienDung, BanNhapDung, CheckpointPhien
from .cong_cu import DieuPhoiCongCu
from .sua_bang_flow import QuanLySuaCanh, CapabilityProvider
from .ket_noi_phan_mem_dung import BoKetNoiPhanMemDung
from .kho_luu_tru import KhoLuuTruDung


router = APIRouter(prefix="/v1/media/projects/{project_id}/dung", tags=["Điều Phối Dựng Video"])


class TaoPhienRequest(BaseModel):
    base_revision: int = Field(default=1, ge=1)
    base_hash: str
    policy: Optional[ChinhSachPhien] = None


class TaoBanNhapRequest(BaseModel):
    run_id: str
    timeline_base: TimelineV2


class ThucHienLenhRequest(BaseModel):
    expected_draft_revision: int = Field(ge=1)
    commands: List[LenhDung]


class CommitBanNhapRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    approval_id: str


class NhanKetQuaCanhRequest(BaseModel):
    output_asset_id: str
    duration_ms: int
    expected_duration_ms: int


class XuatGoiBanGiaoRequest(BaseModel):
    revision: int = Field(ge=1)
    adapter_id: str = "FINAL_CUT_XML"


class TaoVideoDaiRequest(BaseModel):
    source_asset_id: str = Field(min_length=1, max_length=36)
    idempotency_key: str = Field(min_length=8, max_length=128)


def _kiem_tra_quyen_du_an(db: Session, project_id: str, workspace_id: str) -> ProductionProject:
    """Xác minh project thật thuộc workspace trước khi đọc hoặc đổi state Harness."""
    project = db.query(ProductionProject).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == workspace_id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy dự án trong workspace.")
    try:
        QuanLyPhienDung.kiem_tra_so_huu_du_an(project_id, workspace_id)
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Dự án {project_id} không thuộc quyền quản lý của workspace {workspace_id}."
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return project


@router.post("/tu-dong-dung-video-dai", status_code=status.HTTP_202_ACCEPTED)
def tu_dong_dung_video_dai(
    project_id: str,
    req: TaoVideoDaiRequest,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload")),
):
    project = _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    if project.workflow_type != "AUTO_EDIT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "PROJECT_WORKFLOW_MISMATCH", "message": "Auto Edit yêu cầu dự án thuộc luồng Auto Edit."},
        )
    source = db.query(MediaAsset).filter(
        MediaAsset.id == req.source_asset_id,
        MediaAsset.workspace_id == ctx.workspace_id,
    ).first()
    if not source or not (source.mime_detected or "").startswith("video/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy video nguồn trong workspace.")
    if source.project_id and source.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video nguồn không thuộc dự án này.")
    if source.source_product != "UPLOAD" or source.parent_asset_id:
        raise HTTPException(status_code=409, detail={
            "error_code": "AUTO_EDIT_ORIGINAL_SOURCE_REQUIRED",
            "message": "Chọn video gốc tải lên; không dùng thành phẩm hoặc cảnh AI để dựng lại.",
        })

    llm = LLMClient.from_db(db)
    if not llm.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "LLM_NOT_CONFIGURED", "message": "Chưa bật cấu hình LLM cho workspace."},
        )

    job = enqueue_media_job(
        db,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        provider="MEDIA_VIDEO",
        operation="auto_edit_video",
        backend_provider="BAHA_AUTO_EDIT",
        provider_mode="LOCAL_CPU_AND_CONFIGURED_LLM",
        model_id=llm.model,
        prompt_text="Dựng video nguồn thành các clip mạng xã hội, giữ nguyên khuôn mặt gốc.",
        parameters={"source_asset_id": source.id},
        idempotency_key=req.idempotency_key,
        project_id=project_id,
        estimated_cost=0.0,
        credits_source="LOCAL_PROCESSING",
    )
    return {
        "job_id": job.id,
        "state": job.state,
        "source_asset_id": source.id,
        "idempotency_key": req.idempotency_key,
    }


@router.post("/phien", response_model=DinhDanhPhien)
def tao_phien(
    project_id: str,
    req: TaoPhienRequest,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        phien = QuanLyPhienDung.tao_phien(
            project_id=project_id,
            workspace_id=ctx.workspace_id,
            actor_id=ctx.user_id,
            base_revision=req.base_revision,
            base_hash=req.base_hash,
            policy=req.policy
        )
        return phien
    except ValueError as e:
        if "409" in str(e) or LoiHopDong.OCC_CONFLICT_409 in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/phien/{run_id}", response_model=CheckpointPhien)
def lay_trang_thai_phien(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.read"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        QuanLyPhienDung.xac_thuc_run(run_id, project_id, ctx.workspace_id)
        return QuanLyPhienDung.tiep_tuc_phien(run_id)
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/phien/{run_id}/tiep-tuc", response_model=CheckpointPhien)
def tiep_tuc_phien(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        QuanLyPhienDung.xac_thuc_run(run_id, project_id, ctx.workspace_id)
        return QuanLyPhienDung.tiep_tuc_phien(run_id)
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/phien/{run_id}/huy")
def huy_phien(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        QuanLyPhienDung.xac_thuc_run(run_id, project_id, ctx.workspace_id)
        QuanLyPhienDung.huy_phien(run_id)
        return {"status": "SUCCESS", "message": f"Phien {run_id} da duoc huy"}
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/ban-nhap", response_model=BanNhapDung)
def tao_ban_nhap(
    project_id: str,
    req: TaoBanNhapRequest,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        QuanLyPhienDung.xac_thuc_run(req.run_id, project_id, ctx.workspace_id)
        return QuanLyPhienDung.tao_ban_nhap(req.run_id, req.timeline_base)
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/ban-nhap/{draft_id}", response_model=BanNhapDung)
def lay_ban_nhap(
    project_id: str,
    draft_id: str,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.read"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        return QuanLyPhienDung.xac_thuc_draft(draft_id, project_id, ctx.workspace_id)
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/ban-nhap/{draft_id}/lenh", response_model=KetQuaCongCu)
def thuc_hien_lenh(
    project_id: str,
    draft_id: str,
    req: ThucHienLenhRequest,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        # Xac thuc draft thuoc project va workspace
        QuanLyPhienDung.xac_thuc_draft(draft_id, project_id, ctx.workspace_id)
        return DieuPhoiCongCu.thuc_hien_lenh(
            draft_id=draft_id,
            expected_draft_revision=req.expected_draft_revision,
            commands=req.commands,
            workspace_id=ctx.workspace_id
        )
    except ValueError as e:
        if "409" in str(e) or LoiHopDong.OCC_CONFLICT_409 in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/ban-nhap/{draft_id}/ghi-nhan")
def commit_ban_nhap(
    project_id: str,
    draft_id: str,
    req: CommitBanNhapRequest,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        QuanLyPhienDung.xac_thuc_draft(draft_id, project_id, ctx.workspace_id)
        new_version = QuanLyPhienDung.commit_ban_nhap(
            draft_id=draft_id,
            expected_revision=req.expected_revision,
            approval_id=req.approval_id
        )
        return {"status": "SUCCESS", "committed_version": new_version}
    except ValueError as e:
        if "409" in str(e) or LoiHopDong.OCC_CONFLICT_409 in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/don-sua-canh", response_model=TrangThaiDonSua)
def tao_don_sua_canh(
    project_id: str,
    don: DonSuaCanh,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    if don.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã dự án trong đơn ({don.project_id}) không khớp với đường dẫn ({project_id})."
        )

    # Mac dinh capability phu hop voi route
    cap = CapabilityProvider(
        provider_name="FLOW_OR_GEMINI",
        route=don.route,
        model="standard"
    )
    try:
        return QuanLySuaCanh.tao_don_sua_canh(don, cap, workspace_id=ctx.workspace_id)
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/don-sua-canh/{request_id}/ket-qua", response_model=KetQuaNhapCanh)
def nhan_ket_qua_canh(
    project_id: str,
    request_id: str,
    req: NhanKetQuaCanhRequest,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)
    try:
        return QuanLySuaCanh.nhan_ket_qua_canh(
            request_id=request_id,
            output_asset_id=req.output_asset_id,
            workspace_id=ctx.workspace_id,
            duration_ms=req.duration_ms,
            expected_duration_ms=req.expected_duration_ms,
            project_id=project_id
        )
    except ValueError as e:
        if LoiHopDong.CROSS_WORKSPACE_ASSET in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/ban-giao", response_model=GoiBanGiao)
def xuat_goi_ban_giao(
    project_id: str,
    req: XuatGoiBanGiaoRequest,
    db: Session = Depends(get_content_db),
    ctx: TenantContext = Depends(require_action("media.upload"))
):
    _kiem_tra_quyen_du_an(db, project_id, ctx.workspace_id)

    # Lay timeline snapshot da luu tru tu draft hoac committed revision
    draft_record = KhoLuuTruDung.tim_ban_nhap_theo_project_revision(
        project_id=project_id,
        revision=req.revision,
        workspace_id=ctx.workspace_id
    )
    if not draft_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy bản dựng nào của dự án {project_id} tại revision {req.revision} trong workspace {ctx.workspace_id}."
        )

    t = TimelineV2(**draft_record["timeline"])
    return BoKetNoiPhanMemDung.xuat_goi_ban_giao(
        project_id=project_id,
        revision=req.revision,
        timeline=t,
        adapter_id=req.adapter_id,
        workspace_id=ctx.workspace_id
    )
