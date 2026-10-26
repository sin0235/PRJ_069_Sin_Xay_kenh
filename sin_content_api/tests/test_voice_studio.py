from __future__ import annotations

import json
import uuid

import pytest
from fastapi import HTTPException
import numpy as np

from src.database import Base, SessionLocal, engine
from src.models.entities import AIGenerationJob, ContentVideoWorkerLease, MediaAsset, User, VoiceProfile, VoiceStudioSetting, Workspace
from src.modules.voice_studio.contracts import VoiceProfileCreateRequest, VoiceStudioCreateRequest, VoiceStudioSettingsUpdateRequest
from src.modules.voice_studio.service import (
    apply_pronunciation_dictionary,
    list_voice_profiles,
    parse_pronunciation_dictionary,
    get_voice_studio_settings,
    save_voice_studio_settings,
    save_voice_profile,
    submit_voice_job,
    serialize_voice_job,
)
from src.modules.voice_studio import worker as voice_worker
from src.modules.tao_video_noi_dung.tts_provider import TTSProviderManager


@pytest.fixture
def workspace_and_user():
    Base.metadata.create_all(bind=engine)
    workspace_id = f"ws-voice-{uuid.uuid4().hex[:8]}"
    user_id = f"user-voice-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Workspace(id=workspace_id, name="Voice Studio", slug=workspace_id))
        db.add(User(id=user_id, email=f"{user_id}@baha.vn", hashed_password="test"))
        db.commit()
        yield workspace_id, user_id
        db.query(VoiceProfile).filter(VoiceProfile.workspace_id == workspace_id).delete()
        db.query(VoiceStudioSetting).filter(VoiceStudioSetting.workspace_id == workspace_id).delete()
        db.query(AIGenerationJob).filter(AIGenerationJob.workspace_id == workspace_id).delete()
        db.query(MediaAsset).filter(MediaAsset.workspace_id == workspace_id).delete()
        db.query(Workspace).filter(Workspace.id == workspace_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()


@pytest.fixture
def db_session(workspace_and_user):
    with SessionLocal() as db:
        yield db


def test_voice_studio_requires_clone_consent_and_gwen_reference():
    with pytest.raises(ValueError):
        VoiceStudioCreateRequest(provider="GWEN_TTS", text="Xin chào")

    with pytest.raises(ValueError):
        VoiceStudioCreateRequest(
            provider="VIE_NEU_V3_TURBO", text="Xin chào", reference_asset_id="asset-1"
        )

    request = VoiceStudioCreateRequest(
        provider="GWEN_TTS", text="Xin chào", reference_asset_id="asset-1",
        reference_text="Đây là câu mẫu.", voice_clone_consent=True, idempotency_key=str(uuid.uuid4()),
    )
    assert request.provider == "GWEN_TTS"


def test_submit_voice_job_is_idempotent_and_does_not_return_private_text(db_session, workspace_and_user):
    workspace_id, user_id = workspace_and_user
    request = VoiceStudioCreateRequest(
        provider="VIE_NEU_V3_TURBO", text="Nội dung riêng cần đọc.",
        idempotency_key=str(uuid.uuid4()), voice_id="Hải Đăng",
    )

    job = submit_voice_job(db_session, workspace_id, user_id, request)
    repeated = submit_voice_job(db_session, workspace_id, user_id, request)

    assert repeated.id == job.id
    assert "Nội dung riêng cần đọc." not in json.dumps(serialize_voice_job(db_session, job), ensure_ascii=False)

    changed = request.model_copy(update={"text": "Nội dung khác."})
    with pytest.raises(HTTPException) as error:
        submit_voice_job(db_session, workspace_id, user_id, changed)
    assert error.value.status_code == 409


def test_clone_reference_must_belong_to_workspace_and_be_audio(db_session, workspace_and_user):
    workspace_id, user_id = workspace_and_user
    request = VoiceStudioCreateRequest(
        provider="VIE_NEU_V3_TURBO", text="Xin chào", reference_asset_id="missing",
        voice_clone_consent=True, idempotency_key=str(uuid.uuid4()),
    )
    with pytest.raises(HTTPException) as error:
        submit_voice_job(db_session, workspace_id, user_id, request)
    assert error.value.status_code == 404


def test_voice_worker_writes_asset_without_video_project(db_session, workspace_and_user, monkeypatch, tmp_path):
    workspace_id, user_id = workspace_and_user
    job = AIGenerationJob(
        id=str(uuid.uuid4()), workspace_id=workspace_id, asset_type="AUDIO", provider="VOICE_STUDIO",
        provider_mode="VIE_NEU_V3_TURBO", model_id="test-model", idempotency_key=str(uuid.uuid4()),
        state="RUNNING", request_payload_json=json.dumps({
            "provider": "VIE_NEU_V3_TURBO", "text": "OpenAI xin chào",
            "pronunciation_dictionary": [{"source": "OpenAI", "pronunciation": "âu pần ai"}],
            "advanced": {"temperature": 0.7, "max_chars": 180},
        }),
        created_by=user_id,
    )
    token = str(uuid.uuid4())
    db_session.add_all([job, ContentVideoWorkerLease(name=voice_worker.LEASE_NAME, token=token)])
    db_session.commit()
    monkeypatch.setattr(voice_worker, "MEDIA_ROOT_DIR", tmp_path)
    synthesis = []
    monkeypatch.setattr(voice_worker.tts_provider_manager, "synthesize", lambda config, text, *_: synthesis.append((config, text)) or (np.ones(800, dtype=np.float32) * 0.1, 8000))
    monkeypatch.setattr(voice_worker.audio_processor, "probe_audio", lambda *_: {"codec_name": "pcm_s16le", "duration_seconds": 0.1})

    voice_worker.process_voice_studio_job(job.id, token)

    db_session.refresh(job)
    asset = db_session.query(MediaAsset).filter(MediaAsset.workspace_id == workspace_id).one()
    assert job.state == "SUCCEEDED"
    assert asset.project_id is None
    assert asset.source_product == "VOICE_STUDIO_TTS"
    assert asset.storage_key.endswith(".wav")
    assert synthesis[0][1] == "âu pần ai xin chào"
    assert synthesis[0][0]["advanced"]["temperature"] == 0.7


def test_pronunciation_dictionary_parses_and_replaces_whole_terms():
    entries = parse_pronunciation_dictionary("OpenAI = âu pần ai\nGPT-4 = gi pi ti bốn")

    assert apply_pronunciation_dictionary("OpenAI gặp OpenAIcom", entries) == "âu pần ai gặp OpenAIcom"
    chained = parse_pronunciation_dictionary("A = BC\nBC = bê xê")
    assert apply_pronunciation_dictionary("A BC", chained) == "BC bê xê"
    with pytest.raises(ValueError):
        parse_pronunciation_dictionary("OpenAI=1\nopenai=2")
    with pytest.raises(ValueError):
        parse_pronunciation_dictionary("dòng sai định dạng")


def test_pronunciation_dictionary_is_workspace_setting_and_default_for_jobs(db_session, workspace_and_user):
    workspace_id, user_id = workspace_and_user
    assert get_voice_studio_settings(db_session, workspace_id)["pronunciation_dictionary"] == ""

    saved = save_voice_studio_settings(
        db_session, workspace_id, user_id,
        VoiceStudioSettingsUpdateRequest(pronunciation_dictionary="OpenAI=âu pần ai"),
    )
    assert saved["pronunciation_dictionary"] == "OpenAI=âu pần ai"
    with SessionLocal() as reopened_db:
        assert get_voice_studio_settings(reopened_db, workspace_id) == saved

    request = VoiceStudioCreateRequest(
        provider="VIE_NEU_V3_TURBO", text="Xin chào OpenAI", idempotency_key=str(uuid.uuid4()),
        pronunciation_dictionary=None,
    )
    job = submit_voice_job(db_session, workspace_id, user_id, request)
    assert json.loads(job.request_payload_json)["pronunciation_dictionary"] == [
        {"source": "OpenAI", "pronunciation": "âu pần ai"},
    ]

    override = request.model_copy(update={"idempotency_key": str(uuid.uuid4()), "pronunciation_dictionary": ""})
    job = submit_voice_job(db_session, workspace_id, user_id, override)
    assert json.loads(job.request_payload_json)["pronunciation_dictionary"] == []

    with pytest.raises(ValueError):
        save_voice_studio_settings(
            db_session, workspace_id, user_id,
            VoiceStudioSettingsUpdateRequest(pronunciation_dictionary="dòng sai định dạng"),
        )


def test_advanced_settings_reach_vieneu_and_gwen_adapters():
    class FakeVieNeu:
        sample_rate = 48000

        def infer(self, text, **kwargs):
            self.call = (text, kwargs)
            return np.ones(10, dtype=np.float32)

    class FakeGwen:
        def generate_voice_clone(self, **kwargs):
            self.call = kwargs
            return [np.ones(10, dtype=np.float32)], 24000

    vieneu = FakeVieNeu()
    TTSProviderManager._infer("VIE_NEU_V3_TURBO", vieneu, {
        "advanced": {"temperature": 0.6, "max_chars": 120, "denoise_reference": False},
    }, "Xin chào", None)
    assert vieneu.call[1]["temperature"] == 0.6
    assert vieneu.call[1]["max_chars"] == 120
    assert vieneu.call[1]["denoise"] is False

    gwen = FakeGwen()
    TTSProviderManager._infer("GWEN_TTS", gwen, {
        "reference_text": "Câu mẫu.", "advanced": {"temperature": 0.4, "max_new_tokens": 2048},
    }, "Xin chào", "voice.wav")
    assert gwen.call["temperature"] == 0.4
    assert gwen.call["max_new_tokens"] == 2048
    assert gwen.call["ref_audio"] == "voice.wav"


def test_voice_profile_is_workspace_scoped_and_reused_by_tts(db_session, workspace_and_user, tmp_path, monkeypatch):
    workspace_id, user_id = workspace_and_user
    reference = tmp_path / "voice.wav"
    reference.write_bytes(b"audio")
    asset = MediaAsset(
        id="voice-reference", workspace_id=workspace_id, project_id=None, storage_key="ref.wav",
        sha256="not-used-in-submit", byte_size=5, mime_detected="audio/wav", source_product="UPLOAD",
        created_by=user_id,
    )
    db_session.add(asset)
    db_session.commit()
    voice = save_voice_profile(db_session, workspace_id, user_id, VoiceProfileCreateRequest(
        name="Giọng của tôi", provider="VIE_NEU_V3_TURBO", reference_asset_id=asset.id,
        voice_clone_consent=True,
    ))
    listed_voice = list_voice_profiles(db_session, workspace_id)[0]
    assert listed_voice["id"] == voice.id
    assert "reference_text" not in listed_voice

    request = VoiceStudioCreateRequest(
        provider="VIE_NEU_V3_TURBO", text="Xin chào", voice_profile_id=voice.id,
        idempotency_key=str(uuid.uuid4()), pronunciation_dictionary="OpenAI=âu pần ai",
        advanced={"temperature": 0.7, "max_chars": 180},
    )
    job = submit_voice_job(db_session, workspace_id, user_id, request)
    payload = json.loads(job.request_payload_json)
    assert payload["reference_asset_id"] == asset.id
    assert payload["pronunciation_dictionary"] == [{"source": "OpenAI", "pronunciation": "âu pần ai"}]
    assert payload["advanced"]["max_chars"] == 180

    mismatch = request.model_copy(update={"provider": "GWEN_TTS", "idempotency_key": str(uuid.uuid4())})
    with pytest.raises(HTTPException) as error:
        submit_voice_job(db_session, workspace_id, user_id, mismatch)
    assert error.value.status_code == 422

    foreign_request = request.model_copy(update={"idempotency_key": str(uuid.uuid4())})
    with pytest.raises(HTTPException) as error:
        submit_voice_job(db_session, "other-workspace", user_id, foreign_request)
    assert error.value.status_code == 404
