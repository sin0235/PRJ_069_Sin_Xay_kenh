from __future__ import annotations

import json
import os
import re
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.entities import AIGenerationJob, MediaAsset, VoiceProfile, VoiceStudioSetting
from src.modules.voice_studio.contracts import VoiceProfileCreateRequest, VoiceStudioCreateRequest, VoiceStudioSettingsUpdateRequest

MODELS = {
    "GWEN_TTS": "g-group-ai-lab/gwen-tts-0.6B",
    "VIE_NEU_V3_TURBO": "pnnbao-ump/VieNeu-TTS-v3-Turbo",
}


def _private_payload(request: VoiceStudioCreateRequest, pronunciation_dictionary: str) -> dict:
    return {
        "provider": request.provider,
        "text": request.text,
        "voice_id": request.voice_id,
        "voice_profile_id": request.voice_profile_id,
        "reference_asset_id": request.reference_asset_id,
        "reference_text": request.reference_text,
        "voice_clone_consent": request.voice_clone_consent,
        "pronunciation_dictionary": parse_pronunciation_dictionary(pronunciation_dictionary),
        "advanced": request.advanced.model_dump(exclude_none=True),
    }


def parse_pronunciation_dictionary(value: str) -> list[dict[str, str]]:
    entries = []
    seen = set()
    for line_number, raw_line in enumerate(value.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Dòng {line_number}: dùng định dạng từ gốc = cách đọc.")
        source, pronunciation = (part.strip() for part in line.split("=", 1))
        if not source or not pronunciation or len(source) > 80 or len(pronunciation) > 120:
            raise ValueError(f"Dòng {line_number}: từ gốc hoặc cách đọc không hợp lệ.")
        key = source.casefold()
        if key in seen:
            raise ValueError(f"Dòng {line_number}: từ gốc bị lặp.")
        seen.add(key)
        entries.append({"source": source, "pronunciation": pronunciation})
        if len(entries) > 100:
            raise ValueError("Bảng phiên âm tối đa 100 dòng.")
    return entries


def apply_pronunciation_dictionary(text: str, entries: list[dict[str, str]]) -> str:
    if not entries:
        return text
    ordered = sorted(entries, key=lambda item: len(item["source"]), reverse=True)
    replacements = {entry["source"].casefold(): entry["pronunciation"] for entry in ordered}
    alternatives = "|".join(re.escape(entry["source"]) for entry in ordered)
    pattern = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", flags=re.IGNORECASE)
    return pattern.sub(lambda match: replacements[match.group(0).casefold()], text)


def get_voice_studio_settings(db: Session, workspace_id: str) -> dict[str, str]:
    setting = db.query(VoiceStudioSetting).filter(VoiceStudioSetting.workspace_id == workspace_id).first()
    return {"pronunciation_dictionary": setting.pronunciation_dictionary if setting else ""}


def save_voice_studio_settings(
    db: Session, workspace_id: str, user_id: str, request: VoiceStudioSettingsUpdateRequest,
) -> dict[str, str]:
    parse_pronunciation_dictionary(request.pronunciation_dictionary)
    setting = db.query(VoiceStudioSetting).filter(VoiceStudioSetting.workspace_id == workspace_id).first()
    if setting:
        setting.pronunciation_dictionary = request.pronunciation_dictionary
        setting.updated_by = user_id
    else:
        db.add(VoiceStudioSetting(
            workspace_id=workspace_id,
            pronunciation_dictionary=request.pronunciation_dictionary,
            updated_by=user_id,
        ))
    db.commit()
    return get_voice_studio_settings(db, workspace_id)


def save_voice_profile(
    db: Session, workspace_id: str, user_id: str, request: VoiceProfileCreateRequest,
) -> VoiceProfile:
    reference = db.query(MediaAsset).filter(
        MediaAsset.id == request.reference_asset_id,
        MediaAsset.workspace_id == workspace_id,
    ).first()
    if not reference or not (reference.mime_detected or "").startswith("audio/"):
        raise HTTPException(404, detail={"error_code": "VOICE_REFERENCE_NOT_FOUND", "message": "Không tìm thấy audio tham chiếu trong workspace."})
    if db.query(VoiceProfile).filter(
        VoiceProfile.workspace_id == workspace_id,
        VoiceProfile.name == request.name,
    ).first():
        raise HTTPException(409, detail={"error_code": "VOICE_NAME_EXISTS", "message": "Tên giọng này đã có trong thư viện."})
    profile = VoiceProfile(
        id=str(uuid.uuid4()), workspace_id=workspace_id, name=request.name,
        provider=request.provider, reference_asset_id=reference.id,
        reference_text=request.reference_text, voice_clone_consent=True, created_by=user_id,
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail={"error_code": "VOICE_NAME_EXISTS", "message": "Tên giọng này đã có trong thư viện."}) from exc
    db.refresh(profile)
    return profile


def list_voice_profiles(db: Session, workspace_id: str) -> list[dict]:
    rows = db.query(VoiceProfile, MediaAsset).join(
        MediaAsset, MediaAsset.id == VoiceProfile.reference_asset_id,
    ).filter(VoiceProfile.workspace_id == workspace_id).order_by(VoiceProfile.created_at.desc()).all()
    return [{
        "id": profile.id,
        "name": profile.name,
        "provider": profile.provider,
        "reference_filename": asset.original_filename,
        "duration_ms": asset.duration_ms,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
    } for profile, asset in rows]


def submit_voice_job(db: Session, workspace_id: str, user_id: str, request: VoiceStudioCreateRequest) -> AIGenerationJob:
    if os.getenv("APP_ENV", "").lower() == "production":
        from src.model_runtime import require_provider, model_status
        from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError
        try:
            require_provider(request.provider)
        except TTSProviderError as exc:
            raise HTTPException(503, detail={"error_code": str(exc), "message": "Provider TTS chưa sẵn sàng trên NAS."}) from exc
        if model_status()["state"] != "READY":
            raise HTTPException(503, detail={"error_code": "TTS_MODEL_NOT_READY", "message": "Model TTS chưa được chuẩn bị xong."})

    dictionary = request.pronunciation_dictionary
    if dictionary is None:
        dictionary = get_voice_studio_settings(db, workspace_id)["pronunciation_dictionary"]
    payload = _private_payload(request, dictionary)
    if request.voice_profile_id:
        profile = db.query(VoiceProfile).filter(
            VoiceProfile.id == request.voice_profile_id,
            VoiceProfile.workspace_id == workspace_id,
        ).first()
        if not profile:
            raise HTTPException(404, detail={"error_code": "VOICE_PROFILE_NOT_FOUND", "message": "Không tìm thấy giọng đã lưu trong workspace."})
        if profile.provider != request.provider:
            raise HTTPException(422, detail={"error_code": "VOICE_PROFILE_PROVIDER_MISMATCH", "message": "Model TTS không khớp với giọng đã lưu."})
        payload.update({
            "reference_asset_id": profile.reference_asset_id,
            "reference_text": profile.reference_text,
            "voice_clone_consent": profile.voice_clone_consent,
        })
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    key = f"voice-studio:{workspace_id}:{request.idempotency_key}"
    existing = db.query(AIGenerationJob).filter(AIGenerationJob.idempotency_key == key).first()
    if existing:
        if existing.request_payload_json != payload_json:
            raise HTTPException(409, detail={"error_code": "IDEMPOTENCY_CONFLICT", "message": "Mã gửi lại đã được dùng với nội dung khác."})
        return existing

    if payload["reference_asset_id"]:
        reference = db.query(MediaAsset).filter(
            MediaAsset.id == payload["reference_asset_id"],
            MediaAsset.workspace_id == workspace_id,
        ).first()
        if not reference or not (reference.mime_detected or "").startswith("audio/"):
            raise HTTPException(404, detail={"error_code": "VOICE_REFERENCE_NOT_FOUND", "message": "Không tìm thấy audio tham chiếu trong workspace."})

    job = AIGenerationJob(
        id=str(uuid.uuid4()), workspace_id=workspace_id, project_id=None,
        asset_type="AUDIO", provider="VOICE_STUDIO", provider_mode=request.provider,
        model_id=MODELS[request.provider], idempotency_key=key, state="QUEUED",
        request_payload_json=payload_json, created_by=user_id,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(AIGenerationJob).filter(AIGenerationJob.idempotency_key == key).first()
        if not existing or existing.request_payload_json != payload_json:
            raise HTTPException(409, detail={"error_code": "IDEMPOTENCY_CONFLICT", "message": "Mã gửi lại đã được dùng với nội dung khác."})
        return existing
    db.refresh(job)
    return job


def serialize_voice_job(db: Session, job: AIGenerationJob) -> dict:
    asset = None
    if job.state == "SUCCEEDED":
        try:
            asset_ids = json.loads(job.output_asset_ids_json or "[]")
        except (TypeError, ValueError):
            asset_ids = []
        if asset_ids:
            asset = db.query(MediaAsset).filter(
                MediaAsset.id == asset_ids[0], MediaAsset.workspace_id == job.workspace_id,
            ).first()
    return {
        "job_id": job.id,
        "state": job.state,
        "provider": job.provider_mode,
        "model_id": job.model_id,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "asset": ({
            "id": asset.id,
            "mime_detected": asset.mime_detected,
            "duration_ms": asset.duration_ms,
            "original_filename": asset.original_filename,
            "url": f"/v1/media/assets/{asset.id}/download?ttl=3600",
        } if asset else None),
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
