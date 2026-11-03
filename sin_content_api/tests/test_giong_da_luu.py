"""Giọng đã lưu trong thư viện clone giọng dùng lại được cho mọi video: chọn một lần, hệ thống thêm audio vào đúng dự án."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.entities import Base, MediaAsset, VoiceProfile
from src.modules.tao_video_noi_dung.contracts import CreateRunRequest
from src.modules.tao_video_noi_dung.giong_da_luu import ap_dung_ho_so_giong

WS = "ws-1"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[MediaAsset.__table__, VoiceProfile.__table__])
    with sessionmaker(bind=engine)() as session:
        yield session


def _asset(db, project_id="p1", sha="a" * 64):
    row = MediaAsset(id=f"asset-{project_id}", workspace_id=WS, project_id=project_id, storage_key="workspaces/x/media/aa", sha256=sha, byte_size=10,
                     mime_detected="audio/mpeg", duration_ms=5000, source_product="UPLOAD", original_filename="giong.mp3", approval_state="UNREVIEWED", created_by="u")
    db.add(row)
    db.commit()
    return row


def _profile(db, asset):
    row = VoiceProfile(id="vp-1", workspace_id=WS, name="Sếp", provider="VIE_NEU_V3_TURBO", reference_asset_id=asset.id, reference_text=None,
                       voice_clone_consent=True, created_by="u")
    db.add(row)
    db.commit()
    return row


def _request(**extra):
    return CreateRunRequest(plan_id="plan-1", idempotency_key="khoa-12345678", **extra)


def test_khong_chon_giong_da_luu_giu_nguyen_yeu_cau(db):
    request = _request(voice_source="NONE")
    assert ap_dung_ho_so_giong(db, WS, "p2", request) is request


def test_giong_da_luu_thanh_cau_hinh_tts_day_du_va_audio_vao_du_an(db):
    profile = _profile(db, _asset(db, "p1"))
    resolved = ap_dung_ho_so_giong(db, WS, "p2", _request(voice_profile_id=profile.id))
    assert resolved.voice_profile_id is None and resolved.voice_source == "TTS"
    assert resolved.tts_provider == "VIE_NEU_V3_TURBO" and resolved.tts_voice_id == "Sếp" and resolved.voice_clone_consent
    copy = db.get(MediaAsset, resolved.tts_reference_asset_id)
    assert copy.project_id == "p2" and copy.sha256 == "a" * 64 and copy.id != "asset-p1"
    again = ap_dung_ho_so_giong(db, WS, "p2", _request(voice_profile_id=profile.id))   # dùng lại: không nhân thêm dòng audio
    assert again.tts_reference_asset_id == resolved.tts_reference_asset_id
    assert db.query(MediaAsset).filter(MediaAsset.project_id == "p2").count() == 1


def test_audio_da_thuoc_du_an_thi_dung_luon(db):
    asset = _asset(db, "p1")
    profile = _profile(db, asset)
    assert ap_dung_ho_so_giong(db, WS, "p1", _request(voice_profile_id=profile.id)).tts_reference_asset_id == asset.id


def test_giong_khong_ton_tai_hoac_khac_workspace(db):
    _profile(db, _asset(db))
    with pytest.raises(HTTPException) as error:
        ap_dung_ho_so_giong(db, "ws-khac", "p2", _request(voice_profile_id="vp-1"))
    assert error.value.status_code == 404
    with pytest.raises(HTTPException):
        ap_dung_ho_so_giong(db, WS, "p2", _request(voice_profile_id="khong-co"))


def test_khong_tron_giong_da_luu_voi_cau_hinh_thu_cong():
    with pytest.raises(ValueError, match="Giọng đã lưu"):
        _request(voice_profile_id="vp-1", voice_source="TTS", tts_provider="VIE_NEU_V3_TURBO")
    with pytest.raises(ValueError, match="Giọng đã lưu"):
        _request(voice_profile_id="vp-1", voice_asset_id="asset-x")
