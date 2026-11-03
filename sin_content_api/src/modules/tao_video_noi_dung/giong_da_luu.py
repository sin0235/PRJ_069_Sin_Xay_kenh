"""Dùng giọng đã lưu trong thư viện clone giọng (VoiceProfile) cho lượt dựng video nội dung.

Hồ sơ giọng giữ audio tham chiếu của workspace; lượt dựng cần audio thuộc đúng dự án nên ở đây thêm một dòng trỏ cùng tệp
(tệp lưu theo nội dung nên không nhân đôi dữ liệu) rồi đổi yêu cầu thành cấu hình TTS đầy đủ. Nhờ vậy chọn giọng một lần, dùng lại cho mọi video."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.models.entities import MediaAsset, VoiceProfile

from .contracts import CreateRunRequest


def _audio_trong_du_an(db: Session, workspace_id: str, project_id: str, source: MediaAsset) -> str:
    if source.project_id == project_id:
        return source.id
    exists = db.query(MediaAsset).filter(
        MediaAsset.workspace_id == workspace_id, MediaAsset.project_id == project_id, MediaAsset.sha256 == source.sha256,
        MediaAsset.mime_detected.like("audio/%"),
    ).first()
    if exists:
        return exists.id
    columns = {c.name: getattr(source, c.name) for c in MediaAsset.__table__.columns if c.name not in ("id", "project_id", "created_at")}
    row = MediaAsset(**columns, id=str(uuid.uuid4()), project_id=project_id)
    db.add(row)
    db.commit()
    return row.id


def ap_dung_ho_so_giong(db: Session, workspace_id: str, project_id: str, request: CreateRunRequest) -> CreateRunRequest:
    """Không có voice_profile_id thì trả lại nguyên yêu cầu."""
    if not request.voice_profile_id:
        return request
    profile = db.query(VoiceProfile).filter(VoiceProfile.id == request.voice_profile_id, VoiceProfile.workspace_id == workspace_id).first()
    if not profile:
        raise HTTPException(404, detail={"error_code": "VOICE_PROFILE_NOT_FOUND", "message": "Không tìm thấy giọng đã lưu trong thư viện."})
    source = db.query(MediaAsset).filter(MediaAsset.id == profile.reference_asset_id, MediaAsset.workspace_id == workspace_id).first()
    if not source or not (source.mime_detected or "").startswith("audio/"):
        raise HTTPException(404, detail={"error_code": "VOICE_REFERENCE_NOT_FOUND", "message": "Giọng đã lưu không còn audio tham chiếu."})
    data = request.model_dump()
    data.update(
        voice_profile_id=None, voice_source="TTS", tts_provider=profile.provider, tts_voice_id=profile.name,
        tts_reference_asset_id=_audio_trong_du_an(db, workspace_id, project_id, source),
        tts_reference_text=profile.reference_text, voice_clone_consent=bool(profile.voice_clone_consent),
    )
    return CreateRunRequest(**data)
