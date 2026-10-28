from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.tenancy import TenantContext, require_action
from src.database import get_db
from src.models.entities import AIGenerationJob
from src.modules.voice_studio.contracts import VoiceProfileCreateRequest, VoiceStudioCreateRequest, VoiceStudioSettingsUpdateRequest
from src.modules.voice_studio.service import get_voice_studio_settings, list_voice_profiles, save_voice_profile, save_voice_studio_settings, serialize_voice_job, submit_voice_job

router = APIRouter(prefix="/v1/voice-studio", tags=["Voice Clone & TTS"])


@router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    return get_voice_studio_settings(db, tenant.workspace_id)


@router.put("/settings")
def update_settings(
    request: VoiceStudioSettingsUpdateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    try:
        return save_voice_studio_settings(db, tenant.workspace_id, tenant.user_id, request)
    except ValueError as exc:
        raise HTTPException(422, detail={"error_code": "VOICE_SETTINGS_INVALID", "message": str(exc)}) from exc


@router.post("/jobs", status_code=202)
def create_voice_job(
    request: VoiceStudioCreateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    try:
        job = submit_voice_job(db, tenant.workspace_id, tenant.user_id, request)
    except ValueError as exc:
        raise HTTPException(422, detail={"error_code": "VOICE_REQUEST_INVALID", "message": str(exc)}) from exc
    return serialize_voice_job(db, job)


@router.get("/voices")
def get_voice_profiles(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    return list_voice_profiles(db, tenant.workspace_id)


@router.post("/voices", status_code=201)
def create_voice_profile(
    request: VoiceProfileCreateRequest,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.upload")),
):
    profile = save_voice_profile(db, tenant.workspace_id, tenant.user_id, request)
    return next(item for item in list_voice_profiles(db, tenant.workspace_id) if item["id"] == profile.id)


@router.get("/jobs")
def list_voice_jobs(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    jobs = db.query(AIGenerationJob).filter(
        AIGenerationJob.workspace_id == tenant.workspace_id,
        AIGenerationJob.asset_type == "AUDIO",
        AIGenerationJob.provider == "VOICE_STUDIO",
    ).order_by(AIGenerationJob.created_at.desc()).limit(limit).all()
    return [serialize_voice_job(db, job) for job in jobs]


@router.get("/jobs/{job_id}")
def get_voice_job(
    job_id: str,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_action("media.read")),
):
    job = db.query(AIGenerationJob).filter(
        AIGenerationJob.id == job_id,
        AIGenerationJob.workspace_id == tenant.workspace_id,
        AIGenerationJob.provider == "VOICE_STUDIO",
    ).first()
    if not job:
        raise HTTPException(404, detail={"error_code": "VOICE_JOB_NOT_FOUND", "message": "Không tìm thấy tác vụ TTS."})
    return serialize_voice_job(db, job)


@router.get("/capabilities")
def get_capabilities(tenant: TenantContext = Depends(require_action("media.read"))):
    from src.model_runtime import model_status
    from src.runtime_status import worker_status
    return {"providers": {
        "VIE_NEU_V3_TURBO": model_status(),
        "GWEN_TTS": {"state": "NOT_READY", "error_code": "TTS_PROVIDER_NOT_READY"},
    }, "worker": worker_status()}
