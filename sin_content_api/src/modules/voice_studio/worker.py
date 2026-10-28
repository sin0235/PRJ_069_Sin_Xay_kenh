from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import update

from src.database import SessionLocal
from src.models.entities import AIGenerationJob, ContentVideoWorkerLease, MediaAsset
from src.modules.media_studio.audio_processor import audio_processor
from src.modules.media_studio.security import MEDIA_ROOT_DIR
from src.modules.tao_video_noi_dung.tts_provider import TTSProviderError, tts_provider_manager
from src.modules.voice_studio.service import apply_pronunciation_dictionary

logger = logging.getLogger(__name__)
LEASE_NAME = "content-video-flow"
LEASE_SECONDS = 480


def _now():
    return datetime.now(timezone.utc)


def claim_next_voice_job(db, token: str) -> AIGenerationJob | None:
    # Acquiring the shared lease means any remaining RUNNING voice job lost its worker.
    workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
    running_jobs = db.query(AIGenerationJob).filter(
        AIGenerationJob.provider == "VOICE_STUDIO",
        AIGenerationJob.state == "RUNNING",
    )
    if workspace_id:
        running_jobs = running_jobs.filter(AIGenerationJob.workspace_id == workspace_id)
    running_jobs.update({"state": "QUEUED", "retry_count": AIGenerationJob.retry_count + 1}, synchronize_session=False)
    db.commit()
    queued_jobs = db.query(AIGenerationJob).filter(
        AIGenerationJob.provider == "VOICE_STUDIO",
        AIGenerationJob.state == "QUEUED",
    )
    if workspace_id:
        queued_jobs = queued_jobs.filter(AIGenerationJob.workspace_id == workspace_id)
    job = queued_jobs.order_by(AIGenerationJob.created_at).first()
    if not job:
        return None
    claim = db.query(AIGenerationJob).filter(
        AIGenerationJob.id == job.id,
        AIGenerationJob.state == "QUEUED",
    )
    if workspace_id:
        claim = claim.filter(AIGenerationJob.workspace_id == workspace_id)
    updated = claim.update({"state": "RUNNING"}, synchronize_session=False)
    db.commit()
    return db.get(AIGenerationJob, job.id) if updated == 1 else None


class _LeaseHeartbeat:
    def __init__(self, token: str):
        self.token = token
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="voice-studio-heartbeat", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _loop(self):
        while not self.stop_event.wait(LEASE_SECONDS / 4):
            try:
                with SessionLocal() as db:
                    db.execute(update(ContentVideoWorkerLease).where(
                        ContentVideoWorkerLease.name == LEASE_NAME,
                        ContentVideoWorkerLease.token == self.token,
                    ).values(expires_at=_now() + timedelta(seconds=LEASE_SECONDS)))
                    db.commit()
            except Exception:
                logger.exception("Voice Studio worker heartbeat failed")


def _reference_path(db, job, reference_asset_id: str | None) -> str | None:
    if not reference_asset_id:
        return None
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == reference_asset_id,
        MediaAsset.workspace_id == job.workspace_id,
    ).first()
    if not asset or not (asset.mime_detected or "").startswith("audio/"):
        raise TTSProviderError("TTS_REFERENCE_NOT_FOUND")
    path = (MEDIA_ROOT_DIR / asset.storage_key).resolve()
    if not path.is_relative_to(MEDIA_ROOT_DIR.resolve()) or not path.is_file():
        raise TTSProviderError("TTS_REFERENCE_FILE_MISSING")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != asset.sha256:
        raise TTSProviderError("TTS_REFERENCE_HASH_MISMATCH")
    return str(path)


def process_voice_studio_job(job_id: str, token: str) -> None:
    heartbeat = _LeaseHeartbeat(token)
    heartbeat.start()
    output_path = None
    try:
        with SessionLocal() as db:
            query = db.query(AIGenerationJob).filter(
                AIGenerationJob.id == job_id,
                AIGenerationJob.provider == "VOICE_STUDIO",
                AIGenerationJob.state == "RUNNING",
            )
            workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
            if workspace_id:
                query = query.filter(AIGenerationJob.workspace_id == workspace_id)
            job = query.first()
            if not job:
                return
            config = json.loads(job.request_payload_json)
            reference_path = _reference_path(db, job, config.get("reference_asset_id"))
            text = apply_pronunciation_dictionary(config["text"], config.get("pronunciation_dictionary", []))
            audio, sample_rate = tts_provider_manager.synthesize(config, text, reference_path)
            import numpy as np

            samples = np.asarray(audio, dtype=np.float32)
            if samples.size == 0 or not np.isfinite(samples).all() or sample_rate <= 0:
                raise TTSProviderError("TTS_AUDIO_INVALID")
            pcm = (np.clip(samples.reshape(-1), -1.0, 1.0) * 32767).astype("<i2").tobytes()
            filename = f"voice_studio_{job.id}.wav"
            storage_key = f"workspaces/{job.workspace_id}/media/{filename}"
            output_path = MEDIA_ROOT_DIR / storage_key
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = output_path.with_suffix(".wav.tmp")
            try:
                with wave.open(str(temporary_path), "wb") as output:
                    output.setnchannels(1)
                    output.setsampwidth(2)
                    output.setframerate(int(sample_rate))
                    output.writeframes(pcm)
                temporary_path.replace(output_path)
            finally:
                temporary_path.unlink(missing_ok=True)

            metadata = audio_processor.probe_audio(output_path)
            if metadata.get("codec_name") not in {"pcm_s16le", "wav"} or float(metadata.get("duration_seconds", 0)) <= 0:
                raise TTSProviderError("TTS_AUDIO_QC_FAILED")
            data = output_path.read_bytes()
            asset = MediaAsset(
                id=f"asset-{uuid.uuid4().hex[:12]}", workspace_id=job.workspace_id, project_id=None,
                storage_key=storage_key, sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data),
                mime_detected="audio/wav", duration_ms=int(metadata["duration_seconds"] * 1000),
                source_product="VOICE_STUDIO_TTS", original_filename=filename,
                created_by=job.created_by, approval_state="UNREVIEWED",
            )
            db.add(asset)
            job.output_asset_ids_json = json.dumps([asset.id])
            job.state = "SUCCEEDED"
            job.finished_at = _now()
            job.error_code = None
            job.error_message = None
            db.commit()
    except Exception as exc:
        logger.exception("Voice Studio job failed: job_id=%s", job_id)
        if output_path:
            output_path.unlink(missing_ok=True)
        with SessionLocal() as db:
            query = db.query(AIGenerationJob).filter(AIGenerationJob.id == job_id)
            workspace_id = os.getenv("SIN_WORKSPACE_ID", "").strip()
            if workspace_id:
                query = query.filter(AIGenerationJob.workspace_id == workspace_id)
            job = query.first()
            if job and job.state == "RUNNING":
                job.state = "FAILED"
                job.error_code = str(exc)[:100] if isinstance(exc, TTSProviderError) else "VOICE_STUDIO_JOB_FAILED"
                job.error_message = "Không thể tạo audio. Kiểm tra cấu hình model và thử lại."
                job.finished_at = _now()
                db.commit()
    finally:
        heartbeat.stop()
        with SessionLocal() as db:
            db.execute(update(ContentVideoWorkerLease).where(
                ContentVideoWorkerLease.name == LEASE_NAME,
                ContentVideoWorkerLease.token == token,
            ).values(token=None, expires_at=None))
            db.commit()
