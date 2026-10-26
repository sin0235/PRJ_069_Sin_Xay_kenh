from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.entities import ContentVideoPlan, ContentVideoRun, MediaAsset, ProductionProject
from src.modules.llm.client import LLMClient, LLMClientError
from .contracts import (
    ContentVideoPlanResponse,
    ContentVideoRunResponse,
    CreatePlanRequest,
    CreateRunRequest,
    StyleSnapshot,
)
from .cong_harness import approval_receipt_hash, build_shot_receipt, canonical_hash
from .planner import Storyboard, generate_storyboard

_PILOT_STYLE_SNAPSHOT = StyleSnapshot(
    style_name="Origami giấy gấp · pilot v1",
    visual_rules=(
        "Mọi vật thể và nhân vật đều là mô hình giấy origami gấp nếp rõ, bề mặt giấy mịn có thớ nhẹ; "
        "dùng cùng một mô hình nhân vật giấy xuyên suốt, chuyển động gấp/mở liền mạch; bố cục theo tỷ lệ người dùng chọn, "
        "ánh sáng studio mềm từ trên trái, bóng đổ giấy nhất quán, máy quay macro điện ảnh chậm; "
        "không đổi chất liệu sang ảnh thật hoặc 3D nhựa, không sinh chữ trong cảnh."
    ),
    palette=["xanh navy", "trắng ngà", "xanh teal"],
)


def _e2e_test_self_approval_enabled() -> bool:
    try:
        from baha_auth.src.policy.evaluator import e2e_test_self_approval_enabled
        return e2e_test_self_approval_enabled()
    except Exception:
        return False


def _project(db: Session, project_id: str, workspace_id: str) -> ProductionProject:
    project = db.query(ProductionProject).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == workspace_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail={"error_code": "PROJECT_NOT_FOUND", "message": "Không tìm thấy dự án trong workspace."})
    return project


def _response(plan: ContentVideoPlan) -> ContentVideoPlanResponse:
    return ContentVideoPlanResponse(
        id=plan.id,
        project_id=plan.project_id,
        revision=plan.revision,
        status=plan.status,
        source_content=plan.source_content,
        content_sha256=plan.content_sha256,
        target_duration_seconds=plan.target_duration_seconds,
        style_snapshot=StyleSnapshot.model_validate_json(plan.style_snapshot_json),
        style_snapshot_sha256=plan.style_snapshot_sha256,
        storyboard=Storyboard.model_validate_json(plan.storyboard_json),
        storyboard_sha256=plan.storyboard_sha256,
        llm_model=plan.llm_model,
        created_by=plan.created_by,
        approved_by=plan.approved_by,
        approved_at=plan.approved_at,
        created_at=plan.created_at,
    )


def create_plan(db: Session, project_id: str, workspace_id: str, user_id: str, request: CreatePlanRequest) -> ContentVideoPlanResponse:
    _project(db, project_id, workspace_id)
    content = request.content.strip()
    if len(content.encode("utf-8")) > 12000:
        raise HTTPException(status_code=422, detail={"error_code": "CONTENT_TOO_LARGE", "message": "Content vượt quá 12 KB."})

    client = LLMClient.from_db(db)
    if not client.is_enabled:
        raise HTTPException(status_code=503, detail={"error_code": "LLM_NOT_CONFIGURED", "message": "LLM chưa được cấu hình hoặc đang tắt; chưa tạo storyboard."})
    try:
        style_data = _PILOT_STYLE_SNAPSHOT.model_copy(update={"aspect_ratio": request.aspect_ratio}).model_dump(mode="json")
        storyboard, model = generate_storyboard(
            content,
            request.target_duration_seconds,
            style_data,
            client,
        )
    except LLMClientError as exc:
        raise HTTPException(status_code=503, detail={"error_code": exc.error_code, "message": "LLM chưa tạo được storyboard hợp lệ."}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error_code": "INVALID_STORYBOARD", "message": str(exc)}) from exc

    latest = db.query(ContentVideoPlan.revision).filter(
        ContentVideoPlan.project_id == project_id,
        ContentVideoPlan.workspace_id == workspace_id,
    ).order_by(ContentVideoPlan.revision.desc()).first()
    plan = ContentVideoPlan(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        project_id=project_id,
        revision=(latest[0] if latest else 0) + 1,
        status="DRAFT",
        source_content=content,
        content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        target_duration_seconds=request.target_duration_seconds,
        style_snapshot_json=json.dumps(style_data, ensure_ascii=False, sort_keys=True),
        style_snapshot_sha256=canonical_hash(style_data),
        storyboard_json=storyboard.model_dump_json(),
        storyboard_sha256=canonical_hash(storyboard.model_dump(mode="json")),
        llm_model=model,
        created_by=user_id,
    )
    db.add(plan)
    try:
        db.commit()
        db.refresh(plan)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"error_code": "PLAN_REVISION_CONFLICT", "message": "Một storyboard mới vừa được tạo; hãy thử lại."}) from exc
    return _response(plan)


def get_plan(db: Session, project_id: str, plan_id: str, workspace_id: str) -> ContentVideoPlanResponse:
    _project(db, project_id, workspace_id)
    plan = db.query(ContentVideoPlan).filter(
        ContentVideoPlan.id == plan_id,
        ContentVideoPlan.project_id == project_id,
        ContentVideoPlan.workspace_id == workspace_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "Không tìm thấy storyboard."})
    return _response(plan)


def approve_plan(db: Session, project_id: str, plan_id: str, workspace_id: str, user_id: str) -> ContentVideoPlanResponse:
    _project(db, project_id, workspace_id)
    plan = db.query(ContentVideoPlan).filter(
        ContentVideoPlan.id == plan_id,
        ContentVideoPlan.project_id == project_id,
        ContentVideoPlan.workspace_id == workspace_id,
    ).with_for_update().first()
    if not plan:
        raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "Không tìm thấy storyboard."})
    if plan.status != "DRAFT":
        raise HTTPException(status_code=409, detail={"error_code": "PLAN_NOT_DRAFT", "message": "Storyboard không còn ở trạng thái chờ duyệt."})
    if plan.created_by == user_id and not _e2e_test_self_approval_enabled():
        raise HTTPException(status_code=403, detail={"error_code": "SEPARATION_OF_DUTIES", "message": "Người tạo storyboard không được tự duyệt."})
    plan.status = "APPROVED"
    plan.approved_by = user_id
    plan.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(plan)
    return _response(plan)


def _run_response(run: ContentVideoRun) -> ContentVideoRunResponse:
    return ContentVideoRunResponse(
        id=run.id,
        project_id=run.project_id,
        plan_id=run.plan_id,
        plan_revision=run.plan_revision,
        voice_asset_id=run.voice_asset_id,
        status=run.status,
        current_step=run.current_step,
        steps=json.loads(run.steps_json or "[]"),
        output_asset_ids=json.loads(run.output_asset_ids_json or "[]"),
        final_asset_id=run.final_asset_id,
        qc_report=json.loads(run.qc_report_json) if run.qc_report_json else None,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def create_run(
    db: Session,
    project_id: str,
    workspace_id: str,
    user_id: str,
    request: CreateRunRequest,
) -> ContentVideoRunResponse:
    _project(db, project_id, workspace_id)
    plan = db.query(ContentVideoPlan).filter(
        ContentVideoPlan.id == request.plan_id,
        ContentVideoPlan.project_id == project_id,
        ContentVideoPlan.workspace_id == workspace_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "Không tìm thấy storyboard."})
    if plan.status != "APPROVED" or not plan.approved_by or not plan.approved_at:
        raise HTTPException(status_code=409, detail={"error_code": "PLAN_NOT_APPROVED", "message": "Cần duyệt storyboard trước khi sản xuất."})

    existing = db.query(ContentVideoRun).filter(ContentVideoRun.idempotency_key == request.idempotency_key).first()
    if existing:
        if (existing.workspace_id, existing.project_id, existing.plan_id, existing.voice_asset_id) != (
            workspace_id, project_id, plan.id, request.voice_asset_id
        ):
            raise HTTPException(status_code=409, detail={"error_code": "IDEMPOTENCY_KEY_REUSED", "message": "Khóa idempotency đã được dùng cho một run khác."})
        return _run_response(existing)

    voice_asset = None
    if request.voice_asset_id:
        voice_asset = db.query(MediaAsset).filter(
            MediaAsset.id == request.voice_asset_id,
            MediaAsset.workspace_id == workspace_id,
            MediaAsset.project_id == project_id,
        ).first()
        if not voice_asset or not (voice_asset.mime_detected or "").startswith("audio/"):
            raise HTTPException(status_code=404, detail={"error_code": "VOICE_ASSET_NOT_FOUND", "message": "Hãy chọn tệp giọng đọc âm thanh thuộc dự án này."})

    style = json.loads(plan.style_snapshot_json)
    StyleSnapshot.model_validate(style)
    storyboard = Storyboard.model_validate_json(plan.storyboard_json)
    approval_hash = approval_receipt_hash(plan)
    run_id = str(uuid.uuid4())
    steps = []
    for shot in storyboard.shots:
        steps.append(build_shot_receipt(
            run_id=run_id,
            workspace_id=workspace_id,
            project_id=project_id,
            plan=plan,
            voice_asset_id=voice_asset.id if voice_asset else None,
            shot=shot,
            style_snapshot=style,
            continuity_anchor=storyboard.continuity_anchor,
        ))
    run = ContentVideoRun(
        id=run_id,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan.id,
        voice_asset_id=voice_asset.id if voice_asset else None,
        plan_revision=plan.revision,
        storyboard_sha256=plan.storyboard_sha256,
        style_snapshot_sha256=plan.style_snapshot_sha256,
        approval_sha256=approval_hash,
        idempotency_key=request.idempotency_key,
        status="QUEUED",
        steps_json=json.dumps(steps, ensure_ascii=False, separators=(",", ":")),
        created_by=user_id,
    )
    db.add(run)
    try:
        db.commit()
        db.refresh(run)
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(ContentVideoRun).filter(ContentVideoRun.idempotency_key == request.idempotency_key).first()
        if existing and (existing.workspace_id, existing.project_id, existing.plan_id, existing.voice_asset_id) == (
            workspace_id, project_id, plan.id, request.voice_asset_id
        ):
            return _run_response(existing)
        raise HTTPException(status_code=409, detail={"error_code": "RUN_IDEMPOTENCY_CONFLICT", "message": "Không thể tạo run trùng."}) from exc
    return _run_response(run)


def get_run(db: Session, project_id: str, run_id: str, workspace_id: str) -> ContentVideoRunResponse:
    _project(db, project_id, workspace_id)
    run = db.query(ContentVideoRun).filter(
        ContentVideoRun.id == run_id,
        ContentVideoRun.project_id == project_id,
        ContentVideoRun.workspace_id == workspace_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail={"error_code": "RUN_NOT_FOUND", "message": "Không tìm thấy run sản xuất."})
    return _run_response(run)


def resume_run(db: Session, project_id: str, run_id: str, workspace_id: str) -> ContentVideoRunResponse:
    _project(db, project_id, workspace_id)
    run = db.query(ContentVideoRun).filter(
        ContentVideoRun.id == run_id,
        ContentVideoRun.project_id == project_id,
        ContentVideoRun.workspace_id == workspace_id,
    ).with_for_update().first()
    if not run:
        raise HTTPException(status_code=404, detail={"error_code": "RUN_NOT_FOUND", "message": "Không tìm thấy run sản xuất."})
    if run.status not in {"BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_SETUP"}:
        raise HTTPException(status_code=409, detail={"error_code": "RUN_NOT_RESUMABLE", "message": "Run chưa ở trạng thái có thể tiếp tục an toàn."})
    if any(step.get("state") in {"SUBMITTING", "NEEDS_RECONCILIATION"} for step in json.loads(run.steps_json or "[]")):
        raise HTTPException(status_code=409, detail={"error_code": "RUN_HAS_UNCERTAIN_SHOT", "message": "Cần đối soát shot chưa rõ kết quả trước khi tiếp tục."})
    run.status = "QUEUED"
    run.error_code = None
    run.error_message = None
    run.finished_at = None
    db.commit()
    db.refresh(run)
    return _run_response(run)
