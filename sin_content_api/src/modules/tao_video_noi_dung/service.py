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
    RetryRunRequest,
    StyleSnapshot,
)
from .cong_harness import approval_receipt_hash, build_shot_receipt, canonical_hash, verify_shot_receipt
from .planner import Storyboard, generate_storyboard

_PILOT_STYLE_SNAPSHOT = StyleSnapshot(
    style_name="Origami giấy gấp · pilot v1",
    visual_rules=(
        "Nhân vật, đạo cụ và bối cảnh đều là mô hình giấy origami gấp nếp rõ, bề mặt giấy mịn có thớ nhẹ; "
        "dùng cùng một mô hình nhân vật giấy đã hoàn thiện xuyên suốt và chỉ hoạt họa mô hình đó; tuyệt đối không có người thật, bàn tay, ngón tay hay thao tác gấp giấy; bố cục theo tỷ lệ người dùng chọn, "
        "ánh sáng studio mềm từ trên trái, bóng đổ giấy nhất quán, máy quay macro điện ảnh chậm; "
        "nhân vật có dáng người hoàn chỉnh, đầu và thân rõ, đủ hai tay, hai chân và bàn chân với tỷ lệ tự nhiên; khuôn mặt origami cách điệu, không mô phỏng da người thật; hai mắt cùng kích thước và cao độ, cân đối hai bên; mũi giấy nhỏ ở giữa; miệng khép kín rõ nét với biểu cảm thân thiện tự nhiên; "
        "không mắt lác hoặc lệch, không mặt nạ trống, không nét mặt méo hoặc đáng sợ; "
        "không thiếu chi, không mặt trống, không dị dạng, quái vật hoặc hình thể ngoài loài người; "
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
        message = "Hạn mức sử dụng 9Router đã đạt. Hãy đợi giới hạn làm mới rồi thử lại." if exc.error_code == "UPSTREAM_RATE_LIMITED" else "LLM chưa tạo được storyboard hợp lệ."
        raise HTTPException(status_code=503, detail={"error_code": exc.error_code, "message": message}) from exc
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


def update_plan(db: Session, project_id: str, plan_id: str, workspace_id: str, user_id: str, storyboard: Storyboard) -> ContentVideoPlanResponse:
    _project(db, project_id, workspace_id)
    plan = db.query(ContentVideoPlan).filter(
        ContentVideoPlan.id == plan_id,
        ContentVideoPlan.project_id == project_id,
        ContentVideoPlan.workspace_id == workspace_id,
    ).with_for_update().first()
    if not plan:
        raise HTTPException(status_code=404, detail={"error_code": "PLAN_NOT_FOUND", "message": "Không tìm thấy storyboard."})
    if plan.created_by != user_id:
        raise HTTPException(status_code=403, detail={"error_code": "PLAN_EDIT_FORBIDDEN", "message": "Chỉ người tạo storyboard được sửa bản nháp."})
    if plan.status not in {"DRAFT", "APPROVED"}:
        raise HTTPException(status_code=409, detail={"error_code": "PLAN_NOT_EDITABLE", "message": "Storyboard này không còn sửa được."})
    original = Storyboard.model_validate_json(plan.storyboard_json)
    if (
        [shot.shot_id for shot in storyboard.shots] != [shot.shot_id for shot in original.shots]
        or [shot.duration_seconds for shot in storyboard.shots] != [shot.duration_seconds for shot in original.shots]
        or sum(shot.duration_seconds for shot in storyboard.shots) != plan.target_duration_seconds
    ):
        raise HTTPException(status_code=422, detail={"error_code": "STORYBOARD_STRUCTURE_LOCKED", "message": "Không thể đổi thứ tự, mã cảnh hoặc thời lượng cảnh trong bản nháp này."})
    storyboard_json = storyboard.model_dump_json()
    storyboard_hash = canonical_hash(storyboard.model_dump(mode="json"))
    if plan.status == "APPROVED":
        latest = db.query(ContentVideoPlan.revision).filter(
            ContentVideoPlan.project_id == project_id,
            ContentVideoPlan.workspace_id == workspace_id,
        ).order_by(ContentVideoPlan.revision.desc()).first()
        revised = ContentVideoPlan(
            id=str(uuid.uuid4()), workspace_id=workspace_id, project_id=project_id,
            revision=(latest[0] if latest else plan.revision) + 1, status="DRAFT",
            source_content=plan.source_content, content_sha256=plan.content_sha256,
            target_duration_seconds=plan.target_duration_seconds,
            style_snapshot_json=plan.style_snapshot_json,
            style_snapshot_sha256=plan.style_snapshot_sha256,
            storyboard_json=storyboard_json, storyboard_sha256=storyboard_hash,
            llm_model=plan.llm_model, created_by=user_id,
        )
        db.add(revised)
        try:
            db.commit()
            db.refresh(revised)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail={"error_code": "PLAN_REVISION_CONFLICT", "message": "Một storyboard mới vừa được lưu; hãy tải lại rồi thử lại."}) from exc
        return _response(revised)

    plan.storyboard_json = storyboard_json
    plan.storyboard_sha256 = storyboard_hash
    db.commit()
    db.refresh(plan)
    return _response(plan)


def get_latest_history(db: Session, project_id: str, workspace_id: str) -> dict:
    _project(db, project_id, workspace_id)
    plan = db.query(ContentVideoPlan).filter(
        ContentVideoPlan.project_id == project_id,
        ContentVideoPlan.workspace_id == workspace_id,
    ).order_by(ContentVideoPlan.revision.desc()).first()
    run = db.query(ContentVideoRun).filter(
        ContentVideoRun.project_id == project_id,
        ContentVideoRun.workspace_id == workspace_id,
        ContentVideoRun.plan_id == plan.id if plan else False,
    ).order_by(ContentVideoRun.created_at.desc()).first() if plan else None
    return {"plan": _response(plan) if plan else None, "run": _run_response(run) if run else None}


def approve_plan(
    db: Session,
    project_id: str,
    plan_id: str,
    workspace_id: str,
    user_id: str,
    *,
    allow_self_approval: bool = False,
) -> ContentVideoPlanResponse:
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
    if plan.created_by == user_id and not (allow_self_approval or _e2e_test_self_approval_enabled()):
        raise HTTPException(status_code=403, detail={"error_code": "SEPARATION_OF_DUTIES", "message": "Người tạo storyboard không được tự duyệt."})
    plan.status = "APPROVED"
    plan.approved_by = user_id
    plan.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(plan)
    return _response(plan)


def _run_response(run: ContentVideoRun) -> ContentVideoRunResponse:
    tts_config_json = getattr(run, "tts_config_json", None)
    tts_config = json.loads(tts_config_json) if tts_config_json else None
    return ContentVideoRunResponse(
        id=run.id,
        project_id=run.project_id,
        plan_id=run.plan_id,
        plan_revision=run.plan_revision,
        voice_asset_id=run.voice_asset_id,
        voice_source="TTS" if tts_config else "UPLOAD" if run.voice_asset_id else "NONE",
        tts_provider=tts_config.get("provider") if tts_config else None,
        include_subtitles=getattr(run, "include_subtitles", True),
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


def _tts_config(request: CreateRunRequest) -> dict | None:
    if not request.tts_provider:
        return None
    return {
        "provider": request.tts_provider,
        "voice_id": request.tts_voice_id,
        "reference_asset_id": request.tts_reference_asset_id,
        "reference_text": request.tts_reference_text,
        "voice_clone_consent": request.voice_clone_consent,
    }


def _same_run_request(run, workspace_id: str, project_id: str, plan_id: str, voice_asset_id: str | None, tts_config_json: str | None, include_subtitles: bool) -> bool:
    return (
        (run.workspace_id, run.project_id, run.plan_id, run.tts_config_json)
        == (workspace_id, project_id, plan_id, tts_config_json)
        and getattr(run, "include_subtitles", True) == include_subtitles
        and (tts_config_json is not None or run.voice_asset_id == voice_asset_id)
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

    tts_config = _tts_config(request)
    tts_config_json = json.dumps(tts_config, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if tts_config else None
    existing = db.query(ContentVideoRun).filter(ContentVideoRun.idempotency_key == request.idempotency_key).first()
    if existing:
        if not _same_run_request(existing, workspace_id, project_id, plan.id, request.voice_asset_id, tts_config_json, request.include_subtitles):
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
    if request.tts_reference_asset_id:
        reference_asset = db.query(MediaAsset).filter(
            MediaAsset.id == request.tts_reference_asset_id,
            MediaAsset.workspace_id == workspace_id,
            MediaAsset.project_id == project_id,
        ).first()
        if not reference_asset or not (reference_asset.mime_detected or "").startswith("audio/"):
            raise HTTPException(status_code=404, detail={"error_code": "TTS_REFERENCE_NOT_FOUND", "message": "Audio tham chiếu không thuộc dự án này hoặc không phải tệp âm thanh."})

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
            include_narration_audio=not voice_asset and not tts_config,
        ))
    run = ContentVideoRun(
        id=run_id,
        workspace_id=workspace_id,
        project_id=project_id,
        plan_id=plan.id,
        voice_asset_id=voice_asset.id if voice_asset else None,
        tts_config_json=tts_config_json,
        include_subtitles=request.include_subtitles,
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
        if existing and _same_run_request(existing, workspace_id, project_id, plan.id, request.voice_asset_id, tts_config_json, request.include_subtitles):
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


def retry_run(
    db: Session,
    project_id: str,
    run_id: str,
    workspace_id: str,
    user_id: str,
    request: RetryRunRequest,
) -> ContentVideoRunResponse:
    _project(db, project_id, workspace_id)
    source = db.query(ContentVideoRun).filter(
        ContentVideoRun.id == run_id,
        ContentVideoRun.project_id == project_id,
        ContentVideoRun.workspace_id == workspace_id,
    ).with_for_update().first()
    if not source:
        raise HTTPException(status_code=404, detail={"error_code": "RUN_NOT_FOUND", "message": "Không tìm thấy run sản xuất."})
    if source.status not in {"FAILED", "FAILED_QC", "BLOCKED_FLOW_SETUP", "NEEDS_RECONCILIATION", "COMPLETED"}:
        raise HTTPException(status_code=409, detail={"error_code": "RUN_NOT_RETRYABLE", "message": "Run đang hoạt động hoặc chưa ở trạng thái có thể tạo lại shot."})

    plan = db.query(ContentVideoPlan).filter(
        ContentVideoPlan.id == source.plan_id,
        ContentVideoPlan.project_id == project_id,
        ContentVideoPlan.workspace_id == workspace_id,
    ).first()
    if not plan or plan.status != "APPROVED" or not plan.approved_by or not plan.approved_at:
        raise HTTPException(status_code=409, detail={"error_code": "PLAN_NOT_APPROVED", "message": "Storyboard của run này không còn được duyệt."})
    storyboard = Storyboard.model_validate_json(plan.storyboard_json)
    source_steps = json.loads(source.steps_json or "[]")
    shot_ids = [shot.shot_id for shot in storyboard.shots]
    if [step.get("shot_id") for step in source_steps] != shot_ids:
        raise HTTPException(status_code=409, detail={"error_code": "RUN_SHOTS_CHANGED", "message": "Danh sách shot của run không còn khớp storyboard."})
    selected = set(request.shot_ids)
    if not selected <= set(shot_ids):
        raise HTTPException(status_code=422, detail={"error_code": "SHOT_NOT_IN_RUN", "message": "Danh sách có shot không thuộc run này."})
    selected_ids = [shot_id for shot_id in shot_ids if shot_id in selected]
    uncertain_ids = {step["shot_id"] for step in source_steps if step.get("state") in {"SUBMITTING", "NEEDS_RECONCILIATION"}}
    if uncertain_ids and (not request.confirm_no_flow_clip or not uncertain_ids <= selected):
        raise HTTPException(status_code=409, detail={"error_code": "FLOW_RESULT_UNCONFIRMED", "message": "Hãy xác nhận không có clip trong Flow cho shot đang chờ đối soát trước khi gửi lại."})
    all_selected = selected == set(shot_ids)
    first_unfinished = next((step.get("shot_id") for step in source_steps if step.get("state") != "SUCCEEDED"), None)
    if request.new_flow_project and (source.status != "BLOCKED_FLOW_SETUP" or source.error_code != "FLOW_REQUEST_NOT_SUBMITTED"):
        raise HTTPException(status_code=409, detail={"error_code": "FLOW_PROJECT_NOT_UNAVAILABLE", "message": "Chỉ mở project Flow mới khi project hiện tại không truy cập được."})
    if request.new_flow_project and selected_ids != [first_unfinished]:
        raise HTTPException(status_code=409, detail={"error_code": "NEW_FLOW_PROJECT_MUST_START_AT_FAILED_SHOT", "message": "Project Flow mới phải bắt đầu từ shot chưa hoàn tất đầu tiên."})
    if source.status not in {"COMPLETED", "FAILED_QC"} and selected_ids != [first_unfinished]:
        raise HTTPException(status_code=409, detail={"error_code": "RETRY_MUST_START_AT_FAILED_SHOT", "message": "Run chưa hoàn tất; hãy tạo lại đúng shot chưa hoàn tất đầu tiên."})

    signature = canonical_hash({
        "source_run_id": source.id,
        "shot_ids": selected_ids,
        "new_flow_project": request.new_flow_project,
        "confirm_no_flow_clip": request.confirm_no_flow_clip,
    })
    existing = db.query(ContentVideoRun).filter(ContentVideoRun.idempotency_key == request.idempotency_key).first()
    if existing:
        existing_steps = json.loads(existing.steps_json or "[]")
        if (
            existing.workspace_id == workspace_id
            and existing.project_id == project_id
            and existing.plan_id == plan.id
            and existing_steps
            and existing_steps[0].get("retry_signature") == signature
        ):
            return _run_response(existing)
        raise HTTPException(status_code=409, detail={"error_code": "IDEMPOTENCY_KEY_REUSED", "message": "Khóa idempotency đã được dùng cho một yêu cầu khác."})

    tts_config_json = source.tts_config_json
    style = json.loads(plan.style_snapshot_json)
    retry_id = str(uuid.uuid4())
    steps = []
    reusable_assets = []
    for shot, old_step in zip(storyboard.shots, source_steps, strict=True):
        step = build_shot_receipt(
            run_id=retry_id, workspace_id=workspace_id, project_id=project_id, plan=plan,
            voice_asset_id=source.voice_asset_id, shot=shot, style_snapshot=style,
            continuity_anchor=storyboard.continuity_anchor,
            include_narration_audio=not source.voice_asset_id and not tts_config_json,
        )
        if old_step.get("state") == "CLEANING":
            raw_asset_id = old_step.get("raw_asset_id") or old_step.get("asset_id")
            raw_asset = db.query(MediaAsset).filter(
                MediaAsset.id == raw_asset_id,
                MediaAsset.workspace_id == workspace_id,
                MediaAsset.project_id == project_id,
            ).first()
            if not raw_asset:
                raise HTTPException(status_code=409, detail={"error_code": "RETRY_ASSET_NOT_FOUND", "message": f"Không tìm thấy clip Flow gốc của shot {shot.shot_id}."})
            step.update({
                "state": "SUCCEEDED", "raw_asset_id": raw_asset.id, "asset_id": raw_asset.id,
                "watermark_removed": False,
                "finished_at": old_step.get("finished_at") or datetime.now(timezone.utc).isoformat(),
            })
            reusable_assets.append(raw_asset.id)
        elif shot.shot_id not in selected and old_step.get("state") == "SUCCEEDED":
            verify_shot_receipt(source, plan, shot, old_step)
            asset = db.query(MediaAsset).filter(
                MediaAsset.id == old_step.get("asset_id"),
                MediaAsset.workspace_id == workspace_id,
                MediaAsset.project_id == project_id,
            ).first()
            if not asset:
                raise HTTPException(status_code=409, detail={"error_code": "RETRY_ASSET_NOT_FOUND", "message": f"Không tìm thấy clip đã hoàn tất của shot {shot.shot_id}."})
            step.update({
                "state": "SUCCEEDED", "asset_id": asset.id, "finished_at": old_step.get("finished_at"),
                "watermark_removed": old_step.get("watermark_removed", False),
                "raw_asset_id": old_step.get("raw_asset_id"),
            })
            reusable_assets.append(asset.id)
        steps.append(step)

    if not request.new_flow_project:
        flow_project_url = next((step.get("flow_project_url") for step in source_steps if step.get("flow_project_url")), None)
        if flow_project_url:
            steps[0]["flow_project_url"] = flow_project_url
    steps[0]["retry_signature"] = signature
    output_asset_ids = list(dict.fromkeys(reusable_assets + ([source.voice_asset_id] if source.voice_asset_id else [])))
    retry = ContentVideoRun(
        id=retry_id, workspace_id=workspace_id, project_id=project_id, plan_id=plan.id,
        voice_asset_id=source.voice_asset_id, tts_config_json=tts_config_json,
        include_subtitles=getattr(source, "include_subtitles", True),
        plan_revision=plan.revision, storyboard_sha256=plan.storyboard_sha256,
        style_snapshot_sha256=plan.style_snapshot_sha256, approval_sha256=approval_receipt_hash(plan),
        idempotency_key=request.idempotency_key, status="QUEUED",
        steps_json=json.dumps(steps, ensure_ascii=False, separators=(",", ":")),
        output_asset_ids_json=json.dumps(output_asset_ids), created_by=user_id,
    )
    db.add(retry)
    try:
        db.commit()
        db.refresh(retry)
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(ContentVideoRun).filter(ContentVideoRun.idempotency_key == request.idempotency_key).first()
        if existing:
            existing_steps = json.loads(existing.steps_json or "[]")
            if (
                existing
                and existing.workspace_id == workspace_id
                and existing.project_id == project_id
                and existing.plan_id == plan.id
                and existing_steps
                and existing_steps[0].get("retry_signature") == signature
            ):
                return _run_response(existing)
        raise HTTPException(status_code=409, detail={"error_code": "RUN_IDEMPOTENCY_CONFLICT", "message": "Không thể tạo run trùng."}) from exc
    return _run_response(retry)


def resume_run(db: Session, project_id: str, run_id: str, workspace_id: str) -> ContentVideoRunResponse:
    _project(db, project_id, workspace_id)
    run = db.query(ContentVideoRun).filter(
        ContentVideoRun.id == run_id,
        ContentVideoRun.project_id == project_id,
        ContentVideoRun.workspace_id == workspace_id,
    ).with_for_update().first()
    if not run:
        raise HTTPException(status_code=404, detail={"error_code": "RUN_NOT_FOUND", "message": "Không tìm thấy run sản xuất."})
    steps = json.loads(run.steps_json or "[]")
    render_only_retry = (
        run.status == "FAILED"
        and run.error_message == "VOICE_ASSET_DURATION_MISMATCH"
        and bool(run.tts_config_json)
        and bool(run.voice_asset_id)
        and bool(steps)
        and all(step.get("state") == "SUCCEEDED" and step.get("asset_id") for step in steps)
    )
    if render_only_retry:
        voice_asset = db.query(MediaAsset).filter(
            MediaAsset.id == run.voice_asset_id,
            MediaAsset.project_id == project_id,
            MediaAsset.workspace_id == workspace_id,
            MediaAsset.source_product == "CONTENT_VIDEO_TTS",
        ).first()
        asset_ids = [step["asset_id"] for step in steps]
        shot_asset_count = db.query(MediaAsset.id).filter(
            MediaAsset.id.in_(asset_ids),
            MediaAsset.project_id == project_id,
            MediaAsset.workspace_id == workspace_id,
        ).count()
        render_only_retry = bool(voice_asset) and shot_asset_count == len(set(asset_ids))
    if run.status not in {"BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_SETUP"} and not render_only_retry:
        raise HTTPException(status_code=409, detail={"error_code": "RUN_NOT_RESUMABLE", "message": "Run chưa ở trạng thái có thể tiếp tục an toàn."})
    if any(step.get("state") in {"SUBMITTING", "NEEDS_RECONCILIATION"} for step in steps):
        raise HTTPException(status_code=409, detail={"error_code": "RUN_HAS_UNCERTAIN_SHOT", "message": "Cần đối soát shot chưa rõ kết quả trước khi tiếp tục."})
    run.status = "QUEUED"
    run.error_code = None
    run.error_message = None
    run.finished_at = None
    db.commit()
    db.refresh(run)
    return _run_response(run)
