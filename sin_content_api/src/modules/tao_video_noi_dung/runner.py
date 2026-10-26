from __future__ import annotations

import json
import hashlib
import logging
import subprocess
import threading
import tempfile
import uuid
import wave
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_, update

from src.database import SessionLocal
from src.models.entities import (
    ContentVideoPlan,
    ContentVideoRun,
    ContentVideoWorkerLease,
    MediaAsset,
    ProductionProject,
    TimelineVersion,
)
from src.modules.media_studio.security import MEDIA_ROOT_DIR, get_workspace_storage_dir
from src.modules.media_studio.audio_processor import audio_processor
from src.modules.media_studio.video_processor import VIETSUB_FONT_PATH, video_processor
from src.schemas.contracts import TimelineAudioTrack, TimelineCaption, TimelineClip, TimelineDocument, TimelineMediaType
from session_manager import FlowLoginRequired, FlowSubmissionNotSent
from .cong_harness import approval_receipt_hash, dispatch_shot, verify_shot_receipt
from .contracts import ReconcileShotRequest
from .planner import Storyboard
from .tts_provider import TTSProviderError, tts_provider_manager
from .vietsub import MODEL_SIZE as VIETSUB_MODEL_SIZE, VietsubError, to_srt, transcribe_cached

logger = logging.getLogger(__name__)
LEASE_NAME = "content-video-flow"
LEASE_SECONDS = 480


def evaluate_video_qc(meta: dict, expected_duration_seconds: int, decode_ok: bool, aspect_ratio: str = "9:16") -> list[str]:
    issues = []
    expected_dimensions = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    if (meta.get("width"), meta.get("height")) != expected_dimensions:
        issues.append("DIMENSIONS")
    if meta.get("codec_name") != "h264":
        issues.append("VIDEO_CODEC")
    if abs(float(meta.get("duration_seconds", 0)) - expected_duration_seconds) > 0.5:
        issues.append("DURATION")
    if abs(float(meta.get("frame_rate", 0)) - 30.0) > 0.1:
        issues.append("FRAME_RATE")
    if not decode_ok:
        issues.append("DECODE")
    return issues


def evaluate_shot_qc(meta: dict, used_duration_seconds: int, decode_ok: bool = True, aspect_ratio: str = "9:16") -> list[str]:
    issues = evaluate_video_qc(meta, used_duration_seconds, decode_ok=decode_ok, aspect_ratio=aspect_ratio)
    width, height = int(meta.get("width", 0)), int(meta.get("height", 0))
    ratio = 9 / 16 if aspect_ratio == "9:16" else 16 / 9
    if height and min(width, height) >= 720 and abs(width / height - ratio) < 0.01:
        issues = [issue for issue in issues if issue != "DIMENSIONS"]
    frame_rate = float(meta.get("frame_rate", 0))
    if 23.9 <= frame_rate <= 60:
        issues = [issue for issue in issues if issue != "FRAME_RATE"]
    if float(meta.get("duration_seconds", 0)) + 0.5 >= used_duration_seconds:
        issues = [issue for issue in issues if issue != "DURATION"]
    return issues


def _probe_shot_with_qc(path: Path, used_duration_seconds: int, aspect_ratio: str = "9:16") -> tuple[dict, list[str]]:
    meta = video_processor.probe_video(path)
    decode = subprocess.run(
        [video_processor.ffmpeg_bin, "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    return meta, evaluate_shot_qc(
        meta, used_duration_seconds,
        decode_ok=decode.returncode == 0 and not decode.stderr.strip(),
        aspect_ratio=aspect_ratio,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _has_duplicate_shot_media(hashes: list[str]) -> bool:
    return len(hashes) != len(set(hashes))


def _verified_asset_path(asset: MediaAsset, error_code: str) -> Path:
    path = (MEDIA_ROOT_DIR / asset.storage_key).resolve()
    if not path.is_relative_to(MEDIA_ROOT_DIR.resolve()) or not path.is_file():
        raise RuntimeError(f"{error_code}_FILE_MISSING")
    if _file_sha256(path) != asset.sha256:
        raise RuntimeError(f"{error_code}_HASH_MISMATCH")
    return path


def _extract_final_reference_frame(path: Path, workspace_id: str) -> tempfile.TemporaryDirectory:
    temp_dir = tempfile.TemporaryDirectory(prefix=f"flow_reference_{workspace_id}_")
    frame_path = Path(temp_dir.name) / "khung_hinh_cuoi.png"
    result = subprocess.run(
        [video_processor.ffmpeg_bin, "-y", "-sseof", "-0.15", "-i", str(path), "-frames:v", "1", str(frame_path)],
        capture_output=True, text=True, timeout=60, check=False,
    )
    if result.returncode != 0 or not frame_path.is_file() or frame_path.stat().st_size == 0:
        temp_dir.cleanup()
        raise RuntimeError("CONTINUITY_FRAME_EXTRACTION_FAILED")
    return temp_dir


def _save_run(db, run: ContentVideoRun, steps: list[dict]) -> None:
    run.steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
    db.commit()
    db.refresh(run)


def _mark_flow_setup_blocked(run: ContentVideoRun, steps: list[dict], error: Exception) -> bool:
    active = next((step for step in steps if step.get("state") == "SUBMITTING"), None)
    if not active:
        return False
    active["state"] = "READY"
    run.status = "BLOCKED_FLOW_SETUP"
    run.error_code = "FLOW_CREDITS_INSUFFICIENT" if "FLOW_CREDITS_INSUFFICIENT" in str(error) else "FLOW_REQUEST_NOT_SUBMITTED"
    run.error_message = str(error)[:1000]
    run.finished_at = None
    run.steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
    return True


def _release_lease(db, token: str) -> None:
    db.query(ContentVideoWorkerLease).filter(
        ContentVideoWorkerLease.name == LEASE_NAME,
        ContentVideoWorkerLease.token == token,
    ).update({"token": None, "expires_at": None})
    db.query(ContentVideoRun).filter(ContentVideoRun.lease_token == token).update({
        "lease_token": None,
        "lease_expires_at": None,
    })
    db.commit()


def _acquire_lease(db, token: str) -> bool:
    lease = db.get(ContentVideoWorkerLease, LEASE_NAME)
    if lease is None:
        db.add(ContentVideoWorkerLease(name=LEASE_NAME))
        try:
            db.commit()
        except Exception:
            db.rollback()
    result = db.execute(
        update(ContentVideoWorkerLease)
        .where(
            ContentVideoWorkerLease.name == LEASE_NAME,
            or_(ContentVideoWorkerLease.expires_at.is_(None), ContentVideoWorkerLease.expires_at < _now()),
        )
        .values(token=token, expires_at=_now() + timedelta(seconds=LEASE_SECONDS))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


def _heartbeat(db, token: str) -> bool:
    result = db.execute(
        update(ContentVideoWorkerLease)
        .where(ContentVideoWorkerLease.name == LEASE_NAME, ContentVideoWorkerLease.token == token)
        .values(expires_at=_now() + timedelta(seconds=LEASE_SECONDS))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount == 1


class _RunHeartbeat:
    def __init__(self, run_id: str, token: str):
        self.run_id = run_id
        self.token = token
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name=f"content-video-heartbeat-{run_id[:8]}", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _loop(self) -> None:
        interval = LEASE_SECONDS / 4
        while not self.stop_event.wait(interval):
            try:
                with SessionLocal() as db:
                    if not _heartbeat(db, self.token):
                        logger.error("Content video lease lost: run_id=%s", self.run_id)
                        return
                    result = db.query(ContentVideoRun).filter(
                        ContentVideoRun.id == self.run_id,
                        ContentVideoRun.status == "RUNNING",
                        ContentVideoRun.lease_token == self.token,
                    ).update({"lease_expires_at": _now() + timedelta(seconds=LEASE_SECONDS)})
                    db.commit()
                    if result != 1:
                        logger.error("Content video run lease lost: run_id=%s", self.run_id)
                        return
            except Exception:
                logger.exception("Content video heartbeat failed: run_id=%s", self.run_id)


def _recover_expired_runs(db) -> None:
    stale_runs = db.query(ContentVideoRun).filter(
        ContentVideoRun.status == "RUNNING",
        ContentVideoRun.lease_expires_at < _now(),
    ).all()
    for run in stale_runs:
        steps = json.loads(run.steps_json or "[]")
        active = next((step for step in steps if step.get("state") == "SUBMITTING"), None)
        if active:
            active["state"] = "NEEDS_RECONCILIATION"
            run.status = "NEEDS_RECONCILIATION"
            run.error_code = "PROVIDER_SUBMISSION_UNCERTAIN"
            run.error_message = f"Không xác định được kết quả gửi shot {active['shot_id']}; không gửi lại tự động."
        else:
            run.status = "QUEUED"
            run.current_step = None
        run.lease_token = None
        run.lease_expires_at = None
        run.steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
    if stale_runs:
        db.commit()


def _claim_next_run(db, token: str) -> ContentVideoRun | None:
    _recover_expired_runs(db)
    run = db.query(ContentVideoRun).filter(ContentVideoRun.status == "QUEUED").order_by(ContentVideoRun.created_at).first()
    if not run:
        return None
    result = db.query(ContentVideoRun).filter(
        ContentVideoRun.id == run.id,
        ContentVideoRun.status == "QUEUED",
    ).update({
        "status": "RUNNING",
        "lease_token": token,
        "lease_expires_at": _now() + timedelta(seconds=LEASE_SECONDS),
        "started_at": _now(),
    })
    db.commit()
    return db.get(ContentVideoRun, run.id) if result == 1 else None


def _plan_and_project(db, run: ContentVideoRun):
    plan = db.query(ContentVideoPlan).filter(
        ContentVideoPlan.id == run.plan_id,
        ContentVideoPlan.project_id == run.project_id,
        ContentVideoPlan.workspace_id == run.workspace_id,
        ContentVideoPlan.revision == run.plan_revision,
        ContentVideoPlan.status == "APPROVED",
    ).first()
    project = db.query(ProductionProject).filter(
        ProductionProject.id == run.project_id,
        ProductionProject.workspace_id == run.workspace_id,
    ).first()
    if not plan or not project:
        raise RuntimeError("APPROVED_PLAN_OR_PROJECT_NOT_FOUND")
    if plan.storyboard_sha256 != run.storyboard_sha256 or plan.style_snapshot_sha256 != run.style_snapshot_sha256:
        raise RuntimeError("APPROVED_STORYBOARD_HASH_CHANGED")
    if plan.status != "APPROVED" or approval_receipt_hash(plan) != run.approval_sha256:
        raise RuntimeError("APPROVAL_RECEIPT_INVALID")
    return plan, project


def reconcile_shot(
    db,
    project_id: str,
    run_id: str,
    workspace_id: str,
    user_id: str,
    request: ReconcileShotRequest,
) -> None:
    project = db.query(ProductionProject).filter(
        ProductionProject.id == project_id,
        ProductionProject.workspace_id == workspace_id,
    ).first()
    run = db.query(ContentVideoRun).filter(
        ContentVideoRun.id == run_id,
        ContentVideoRun.project_id == project_id,
        ContentVideoRun.workspace_id == workspace_id,
    ).with_for_update().first()
    if not project or not run:
        raise HTTPException(status_code=404, detail={"error_code": "RUN_NOT_FOUND", "message": "Không tìm thấy run trong workspace."})
    if run.status != "NEEDS_RECONCILIATION":
        raise HTTPException(status_code=409, detail={"error_code": "RUN_NOT_RECONCILABLE", "message": "Run không có shot đang chờ đối soát."})
    lease_expiry = run.lease_expires_at
    if lease_expiry and lease_expiry.tzinfo is None:
        lease_expiry = lease_expiry.replace(tzinfo=timezone.utc)
    if run.lease_token and (not lease_expiry or lease_expiry > _now()):
        raise HTTPException(status_code=409, detail={"error_code": "RUN_WORKER_STILL_ACTIVE", "message": "Worker vẫn đang giữ run; thử lại sau."})

    plan, _ = _plan_and_project(db, run)
    storyboard = Storyboard.model_validate_json(plan.storyboard_json)
    shot = next((item for item in storyboard.shots if item.shot_id == request.shot_id), None)
    steps = json.loads(run.steps_json or "[]")
    step = next((item for item in steps if item.get("shot_id") == request.shot_id), None)
    if not shot or not step or step.get("state") != "NEEDS_RECONCILIATION":
        raise HTTPException(status_code=404, detail={"error_code": "SHOT_NOT_RECONCILABLE", "message": "Không tìm thấy shot đang chờ đối soát."})
    try:
        verify_shot_receipt(run, plan, shot, step)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"error_code": "HARNESS_RECEIPT_INVALID", "message": "Receipt của shot không còn hợp lệ."}) from exc

    asset = db.query(MediaAsset).filter(
        MediaAsset.id == request.asset_id,
        MediaAsset.workspace_id == workspace_id,
        MediaAsset.project_id == project_id,
    ).first()
    if not asset or asset.mime_detected != "video/mp4" or asset.source_product not in {"GOOGLE_FLOW", "GOOGLE_FLOW_I2V", "UPLOAD"}:
        raise HTTPException(status_code=404, detail={"error_code": "RECONCILE_ASSET_NOT_FOUND", "message": "Không tìm thấy video MP4 trong dự án."})
    run_started_at = run.started_at
    asset_created_at = asset.created_at
    if run_started_at and run_started_at.tzinfo is None:
        run_started_at = run_started_at.replace(tzinfo=timezone.utc)
    if asset_created_at and asset_created_at.tzinfo is None:
        asset_created_at = asset_created_at.replace(tzinfo=timezone.utc)
    if not run_started_at or not asset_created_at or asset_created_at < run_started_at:
        raise HTTPException(status_code=404, detail={"error_code": "RECONCILE_ASSET_NOT_FOUND", "message": "Không tìm thấy video MP4 mới của run trong dự án."})
    try:
        path = _verified_asset_path(asset, "RECONCILE_ASSET")
        aspect_ratio = json.loads(plan.style_snapshot_json).get("aspect_ratio", "9:16")
        _, issues = _probe_shot_with_qc(path, shot.duration_seconds, aspect_ratio)
        if issues:
            raise RuntimeError("SHOT_QC_FAILED:" + ",".join(issues))
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"error_code": "RECONCILE_ASSET_INVALID", "message": "Video không qua kiểm tra hash, hình ảnh, thời lượng hoặc âm thanh cần thiết."}) from exc

    expected_steps_json = run.steps_json or "[]"
    expected_output_ids_json = run.output_asset_ids_json or "[]"
    step.update({
        "state": "SUCCEEDED",
        "asset_id": asset.id,
        "reconciled_by": user_id,
        "reconciled_at": _now().isoformat(),
        "reconciliation_reason": request.reason.strip(),
    })
    new_steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
    new_output_ids_json = json.dumps(
        list(dict.fromkeys([*json.loads(run.output_asset_ids_json or "[]"), asset.id]))
    )
    claim = [
        ContentVideoRun.id == run.id,
        ContentVideoRun.status == "NEEDS_RECONCILIATION",
        ContentVideoRun.steps_json == expected_steps_json,
        ContentVideoRun.output_asset_ids_json == expected_output_ids_json,
    ]
    if run.lease_token is None:
        claim.append(ContentVideoRun.lease_token.is_(None))
    else:
        claim.extend([
            ContentVideoRun.lease_token == run.lease_token,
            ContentVideoRun.lease_expires_at == run.lease_expires_at,
        ])
    result = db.execute(
        update(ContentVideoRun)
        .where(*claim)
        .values(
            steps_json=new_steps_json,
            output_asset_ids_json=new_output_ids_json,
            status="QUEUED",
            current_step=None,
            error_code=None,
            error_message=None,
            finished_at=None,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail={"error_code": "RECONCILIATION_CONFLICT", "message": "Run vừa được cập nhật; tải lại trạng thái trước khi đối soát."})
    db.commit()


def _voice_input(db, run: ContentVideoRun, plan: ContentVideoPlan) -> tuple[MediaAsset, Path] | None:
    if not run.voice_asset_id:
        return None
    asset = db.query(MediaAsset).filter(
        MediaAsset.id == run.voice_asset_id,
        MediaAsset.workspace_id == run.workspace_id,
        MediaAsset.project_id == run.project_id,
    ).first()
    if not asset or not (asset.mime_detected or "").startswith("audio/"):
        raise RuntimeError("VOICE_ASSET_NOT_FOUND")
    path = _verified_asset_path(asset, "VOICE_ASSET")
    meta = audio_processor.probe_audio(path)
    if meta.get("codec_name") not in {"mp3", "aac", "wav", "pcm_s16le", "opus", "vorbis"}:
        raise RuntimeError("VOICE_ASSET_CODEC_UNSUPPORTED")
    if abs(float(meta.get("duration_seconds", 0)) - plan.target_duration_seconds) > 0.5:
        raise RuntimeError("VOICE_ASSET_DURATION_MISMATCH")
    return asset, path


def _generate_tts_voice(db, run: ContentVideoRun, plan: ContentVideoPlan, storyboard: Storyboard) -> None:
    config = json.loads(run.tts_config_json) if run.tts_config_json else None
    if not config or run.voice_asset_id:
        return
    reference_path = None
    if config.get("reference_asset_id"):
        reference = db.query(MediaAsset).filter(
            MediaAsset.id == config["reference_asset_id"],
            MediaAsset.workspace_id == run.workspace_id,
            MediaAsset.project_id == run.project_id,
        ).first()
        if not reference or not (reference.mime_detected or "").startswith("audio/"):
            raise TTSProviderError("TTS_REFERENCE_NOT_FOUND")
        reference_path = str(_verified_asset_path(reference, "TTS_REFERENCE"))
    audio, sample_rate = tts_provider_manager.synthesize(config, storyboard.narration, reference_path)
    import numpy as np
    samples = np.asarray(audio, dtype=np.float32)
    if samples.size == 0 or not np.isfinite(samples).all() or sample_rate <= 0:
        raise TTSProviderError("TTS_AUDIO_INVALID")
    samples = np.clip(samples.reshape(-1), -1.0, 1.0)
    pcm = (samples * 32767).astype("<i2").tobytes()
    filename = f"content_video_{run.id}_tts.wav"
    storage_key = f"workspaces/{run.workspace_id}/media/{filename}"
    output_path = MEDIA_ROOT_DIR / storage_key
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(".wav.tmp")
    try:
        with wave.open(str(temporary_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(int(sample_rate))
            wav.writeframes(pcm)
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    data = output_path.read_bytes()
    meta = audio_processor.probe_audio(output_path)
    if meta.get("codec_name") not in {"pcm_s16le", "wav"} or abs(float(meta.get("duration_seconds", 0)) - plan.target_duration_seconds) > 0.5:
        output_path.unlink(missing_ok=True)
        raise TTSProviderError("TTS_AUDIO_QC_FAILED")
    asset = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}", workspace_id=run.workspace_id,
        project_id=run.project_id, storage_key=storage_key,
        sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data),
        mime_detected="audio/wav", duration_ms=int(meta["duration_seconds"] * 1000),
        source_product="CONTENT_VIDEO_TTS", original_filename=filename,
        created_by=run.created_by, approval_state="UNREVIEWED",
    )
    db.add(asset)
    run.voice_asset_id = asset.id
    run.output_asset_ids_json = json.dumps([*json.loads(run.output_asset_ids_json or "[]"), asset.id])
    db.commit()
    db.refresh(run)


def _write_export_package(
    package_path: Path,
    video_path: Path,
    run: ContentVideoRun,
    plan: ContentVideoPlan,
    timeline: TimelineDocument,
    report: dict,
    shot_asset_hashes: list[dict],
    steps: list[dict],
    voice_asset: MediaAsset | None,
) -> None:
    files = {
        "content/source.txt": plan.source_content.encode("utf-8"),
        "plan/storyboard.json": plan.storyboard_json.encode("utf-8"),
        "timeline/timeline.json": timeline.model_dump_json(indent=2).encode("utf-8"),
        "production/shots.json": json.dumps(
            [{key: step.get(key) for key in (
                "shot_id", "prompt", "command_sha256", "asset_id", "reconciled_by",
                "reconciled_at", "reconciliation_reason",
            )} for step in steps],
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        "qc/report.json": json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"),
    }
    if timeline.captions:
        files["subtitles/vietsub.srt"] = to_srt([caption.model_dump() for caption in timeline.captions]).encode("utf-8")
    manifest = {
        "run_id": run.id,
        "plan_id": plan.id,
        "plan_revision": plan.revision,
        "acceptance_mode": "HYBRID",
        "style_snapshot_sha256": plan.style_snapshot_sha256,
        "voice_asset": {
            "id": voice_asset.id,
            "sha256": voice_asset.sha256,
            "source": "TTS" if getattr(voice_asset, "source_product", None) == "CONTENT_VIDEO_TTS" else "UPLOAD",
        } if voice_asset else None,
        "shot_assets": shot_asset_hashes,
        "files": {"video/final.mp4": _file_sha256(video_path), **{name: hashlib.sha256(data).hexdigest() for name, data in files.items()}},
        "speech_alignment": report.get("speech_alignment", "NOT_MEASURED"),
        "vietsub": report.get("vietsub"),
    }
    temporary_path = package_path.with_name(f".{package_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.write(video_path, "video/final.mp4")
            for name, data in files.items():
                archive.writestr(name, data)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        temporary_path.replace(package_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _render_and_qc(db, run: ContentVideoRun, plan: ContentVideoPlan, storyboard: Storyboard, asset_ids: list[str]) -> None:
    clips = []
    shot_asset_hashes = []
    start_ms = 0
    for shot, asset_id in zip(storyboard.shots, asset_ids, strict=True):
        duration_ms = shot.duration_seconds * 1000
        asset = db.query(MediaAsset).filter(
            MediaAsset.id == asset_id,
            MediaAsset.workspace_id == run.workspace_id,
            MediaAsset.project_id == run.project_id,
        ).first()
        if not asset or not asset.duration_ms or asset.duration_ms < duration_ms:
            raise RuntimeError(f"SHOT_DURATION_INVALID:{shot.shot_id}")
        shot_asset_hashes.append({"asset_id": asset.id, "sha256": asset.sha256})
        clips.append(TimelineClip(
            clip_id=shot.shot_id,
            asset_id=asset.id,
            media_type=TimelineMediaType.VIDEO,
            start_ms=start_ms,
            duration_ms=duration_ms,
            trim_in_ms=0,
            trim_out_ms=duration_ms,
        ))
        start_ms += duration_ms

    aspect_ratio = json.loads(plan.style_snapshot_json).get("aspect_ratio", "9:16")
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    voice_input = _voice_input(db, run, plan)
    voice_asset = voice_input[0] if voice_input else None
    caption_cues = []
    if voice_input:
        audio_sha256 = voice_asset.sha256 or _file_sha256(voice_input[1])
        cache_key = hashlib.sha256(f"{run.workspace_id}:{audio_sha256}:{VIETSUB_MODEL_SIZE}".encode("utf-8")).hexdigest()
        cache_path = MEDIA_ROOT_DIR / ".cache" / "vietsub" / f"{cache_key}.json"
        target_duration_ms = plan.target_duration_seconds * 1000
        for cue in transcribe_cached(voice_input[1], cache_path):
            cue_start = max(0, int(cue["start_ms"]))
            cue_end = min(target_duration_ms, cue_start + int(cue["duration_ms"]))
            if cue_end > cue_start:
                caption_cues.append(TimelineCaption(
                    caption_id=f"vietsub_{len(caption_cues) + 1:04d}",
                    text=cue["text"],
                    start_ms=cue_start,
                    duration_ms=cue_end - cue_start,
                    font_size=52 if height > width else 36,
                    safe_zone=True,
                ))
    vietsub_status = "NO_AUDIO_FOR_VIETSUB" if not voice_asset else "GENERATED_UNREVIEWED" if caption_cues else "NO_SPEECH_DETECTED"
    timeline = TimelineDocument(
        width=width,
        height=height,
        fps=30,
        clips=clips,
        voice_track=TimelineAudioTrack(asset_id=voice_asset.id, duration_ms=plan.target_duration_seconds * 1000) if voice_asset else None,
        captions=caption_cues,
    )
    latest = db.query(TimelineVersion).filter(TimelineVersion.project_id == run.project_id).order_by(TimelineVersion.version.desc()).first()
    version = (latest.version if latest else 0) + 1
    timeline_version = TimelineVersion(
        id=f"tl-{uuid.uuid4().hex[:12]}",
        project_id=run.project_id,
        version=version,
        tracks_json=timeline.model_dump_json(),
        is_locked=True,
        created_by=run.created_by,
    )
    db.add(timeline_version)
    db.commit()

    out_dir = get_workspace_storage_dir(run.workspace_id)
    filename = f"content_video_{run.id}_v{version}.mp4"
    output_path = out_dir / filename

    def resolve_asset(asset_id: str) -> Path:
        asset = db.query(MediaAsset).filter(
            MediaAsset.id == asset_id,
            MediaAsset.project_id == run.project_id,
            MediaAsset.workspace_id == run.workspace_id,
        ).first()
        if not asset:
            raise FileNotFoundError("SHOT_ASSET_NOT_FOUND")
        return _verified_asset_path(asset, "SHOT_ASSET")

    run.current_step = "RENDER"
    db.commit()
    render_meta = video_processor.render_timeline_document(
        timeline, resolve_asset, output_path, transition_seconds=0.3, caption_style="vietsub_v1"
    )
    meta = video_processor.probe_video(output_path)
    meta["flow_native_audio"] = bool(render_meta.get("flow_native_audio"))
    decode = subprocess.run(
        [video_processor.ffmpeg_bin, "-v", "error", "-i", str(output_path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    issues = evaluate_video_qc(
        meta, plan.target_duration_seconds, decode.returncode == 0 and not decode.stderr.strip(),
        aspect_ratio=aspect_ratio,
    )
    if not voice_asset and any(getattr(shot, "prompt_contract_version", None) == 3 for shot in storyboard.shots) and not meta["flow_native_audio"]:
        issues.append("FLOW_NATIVE_AUDIO_MISSING")
    audio_qc = (
        audio_processor.verify_audio_qc(output_path, expected_duration_sec=plan.target_duration_seconds)
        if voice_asset or meta.get("flow_native_audio") else {"status": "SKIPPED", "reason": "NO_AUDIO_SELECTED", "passed": True}
    )
    if not audio_qc.get("passed"):
        issues.append("AUDIO_QC")
    tts_config = json.loads(run.tts_config_json) if getattr(run, "tts_config_json", None) else None
    report = {
        "status": "PASS" if not issues else "FAIL",
        "acceptance_mode": "HYBRID",
        "issues": issues,
        "expected_duration_seconds": plan.target_duration_seconds,
        "measured": meta,
        "timeline_version_id": timeline_version.id,
        "shot_asset_ids": asset_ids,
        "shot_asset_hashes": shot_asset_hashes,
        "style_snapshot_sha256": plan.style_snapshot_sha256,
        "voice_asset_id": voice_asset.id if voice_asset else None,
        "voice_source": "TTS" if voice_asset and getattr(voice_asset, "source_product", None) == "CONTENT_VIDEO_TTS" else "UPLOAD" if voice_asset else "FLOW_NATIVE" if meta.get("flow_native_audio") else "NONE",
        "flow_native_audio": bool(meta.get("flow_native_audio")),
        "voice_asset_sha256": voice_asset.sha256 if voice_asset else None,
        "tts_provider": tts_config.get("provider") if tts_config and voice_asset else None,
        "tts_model": {"GWEN_TTS": "g-group-ai-lab/gwen-tts-0.6B", "VIE_NEU_V3_TURBO": "pnnbao-ump/VieNeu-TTS-v3-Turbo"}.get(tts_config.get("provider")) if tts_config and voice_asset else None,
        "audio_qc": audio_qc,
        "vietsub_status": vietsub_status,
        "caption_count": len(caption_cues),
        "vietsub": {
            "status": vietsub_status,
            "provider": "faster-whisper" if voice_asset else None,
            "model": VIETSUB_MODEL_SIZE if voice_asset else None,
            "language": "vi" if voice_asset else None,
            "audio_sha256": voice_asset.sha256 if voice_asset else None,
            "style": "be_vietnam_pro_semibold_box_v1" if caption_cues else None,
            "font_sha256": _file_sha256(VIETSUB_FONT_PATH) if caption_cues else None,
            "caption_count": len(caption_cues),
            "asr_quality_status": "UNVERIFIED" if voice_asset else None,
        },
        "speech_alignment": "WHISPER_ASR_TIMESTAMPS" if caption_cues else vietsub_status,
    }
    run.qc_report_json = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    if issues:
        if output_path.exists():
            output_path.unlink()
        run.status = "FAILED_QC"
        run.error_code = "FINAL_VIDEO_QC_FAILED"
        run.error_message = ",".join(issues)
        run.finished_at = _now()
        db.commit()
        return

    export_id = f"asset-{uuid.uuid4().hex[:12]}"
    report["export_asset_id"] = export_id
    package_path = out_dir / f"content_video_{run.id}_v{version}_export.zip"
    _write_export_package(package_path, output_path, run, plan, timeline, report, shot_asset_hashes, json.loads(run.steps_json or "[]"), voice_asset)
    data = output_path.read_bytes()
    output = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        storage_key=f"workspaces/{run.workspace_id}/media/{filename}",
        sha256=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        mime_detected="video/mp4",
        duration_ms=int(meta["duration_seconds"] * 1000),
        source_product="CONTENT_VIDEO_RENDER",
        original_filename=filename,
        created_by=run.created_by,
        approval_state="UNREVIEWED",
    )
    export_size = package_path.stat().st_size
    export = MediaAsset(
        id=export_id,
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        storage_key=f"workspaces/{run.workspace_id}/media/{package_path.name}",
        sha256=_file_sha256(package_path),
        byte_size=export_size,
        mime_detected="application/zip",
        source_product="CONTENT_VIDEO_EXPORT",
        original_filename=package_path.name,
        created_by=run.created_by,
        approval_state="UNREVIEWED",
    )
    db.add(output)
    db.add(export)
    run.final_asset_id = output.id
    report["export_sha256"] = export.sha256
    run.qc_report_json = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    run.output_asset_ids_json = json.dumps(asset_ids + ([voice_asset.id] if voice_asset else []) + [output.id, export.id])
    run.status = "COMPLETED"
    run.current_step = "QC_PASSED"
    run.finished_at = _now()
    db.commit()


def process_run(run_id: str, token: str | None = None) -> None:
    token = token or str(uuid.uuid4())
    with SessionLocal() as db:
        run = db.get(ContentVideoRun, run_id)
        if not run:
            return
        heartbeat = _RunHeartbeat(run_id, token)
        heartbeat.start()
        try:
            plan, _ = _plan_and_project(db, run)
            storyboard = Storyboard.model_validate_json(plan.storyboard_json)
            _generate_tts_voice(db, run, plan, storyboard)
            _voice_input(db, run, plan)
            steps = json.loads(run.steps_json or "[]")
            flow_project_url = next((step.get("flow_project_url") for step in steps if step.get("flow_project_url")), None)

            def save_flow_project_url(project_url: str) -> None:
                nonlocal flow_project_url
                if flow_project_url and flow_project_url != project_url:
                    raise RuntimeError("FLOW_PROJECT_CHANGED_WITHIN_RUN")
                flow_project_url = project_url
                steps[0]["flow_project_url"] = project_url
                _save_run(db, run, steps)

            if not _heartbeat(db, token):
                raise RuntimeError("WORKER_LEASE_LOST")

            for shot_index, (step, shot) in enumerate(zip(steps, storyboard.shots, strict=True)):
                verify_shot_receipt(run, plan, shot, step)
                if step.get("state") == "SUCCEEDED":
                    continue
                if step.get("state") == "SUBMITTING":
                    run.status = "NEEDS_RECONCILIATION"
                    run.error_code = "PROVIDER_SUBMISSION_UNCERTAIN"
                    run.error_message = f"Không gửi lại shot {shot.shot_id} vì trạng thái nhà cung cấp chưa rõ."
                    db.commit()
                    return
                reference_temp = None
                reference_path = None
                reference_asset_id = None
                if shot.continues_previous:
                    if shot_index == 0:
                        raise RuntimeError("CONTINUITY_PREVIOUS_SHOT_MISSING")
                    previous_step = steps[shot_index - 1]
                    if previous_step.get("state") != "SUCCEEDED" or not previous_step.get("asset_id"):
                        raise RuntimeError("CONTINUITY_PREVIOUS_SHOT_NOT_SUCCEEDED")
                    previous_asset = db.query(MediaAsset).filter(
                        MediaAsset.id == previous_step["asset_id"],
                        MediaAsset.workspace_id == run.workspace_id,
                        MediaAsset.project_id == run.project_id,
                    ).first()
                    if not previous_asset:
                        raise RuntimeError("CONTINUITY_PREVIOUS_ASSET_NOT_FOUND")
                    previous_path = _verified_asset_path(previous_asset, "CONTINUITY_PREVIOUS_ASSET")
                    reference_temp = _extract_final_reference_frame(previous_path, run.workspace_id)
                    reference_path = Path(reference_temp.name) / "khung_hinh_cuoi.png"
                    reference_asset_id = previous_asset.id
                step["state"] = "SUBMITTING"
                step["started_at"] = _now().isoformat()
                run.current_step = shot.shot_id
                _save_run(db, run, steps)
                if not _heartbeat(db, token):
                    raise RuntimeError("WORKER_LEASE_LOST")
                try:
                    try:
                        asset = dispatch_shot(
                            db=db,
                            run=run,
                            plan=plan,
                            shot=shot,
                            step=step,
                            start_image_path=reference_path,
                            start_image_asset_id=reference_asset_id,
                            flow_project_url=flow_project_url,
                            on_flow_project_created=save_flow_project_url,
                        )
                    finally:
                        if reference_temp:
                            reference_temp.cleanup()
                except FlowLoginRequired:
                    step["state"] = "READY"
                    run.status = "BLOCKED_FLOW_LOGIN"
                    run.error_code = "FLOW_LOGIN_REQUIRED"
                    run.error_message = "Đăng nhập Google Flow rồi tiếp tục run."
                    _save_run(db, run, steps)
                    return
                if asset.workspace_id != run.workspace_id or asset.project_id != run.project_id:
                    raise RuntimeError("PROVIDER_ASSET_SCOPE_MISMATCH")
                path = _verified_asset_path(asset, "PROVIDER_OUTPUT")
                if shot.prompt_contract_version == 3 and not run.voice_asset_id:
                    if audio_processor.probe_audio(path).get("codec_name") == "unknown":
                        step.update({"state": "FAILED", "asset_id": asset.id, "error_code": "FLOW_AUDIO_MISSING"})
                        _save_run(db, run, steps)
                        raise RuntimeError("FLOW_AUDIO_MISSING")
                aspect_ratio = json.loads(plan.style_snapshot_json).get("aspect_ratio", "9:16")
                shot_meta, shot_issues = _probe_shot_with_qc(path, shot.duration_seconds, aspect_ratio)
                if shot_issues:
                    raise RuntimeError(f"SHOT_QC_FAILED:{shot.shot_id}:{','.join(shot_issues)}")
                step["state"] = "SUCCEEDED"
                step["asset_id"] = asset.id
                step["finished_at"] = _now().isoformat()
                run.output_asset_ids_json = json.dumps([item.get("asset_id") for item in steps if item.get("asset_id")])
                _save_run(db, run, steps)
            asset_ids = [step["asset_id"] for step in steps]
            shot_assets = db.query(MediaAsset).filter(
                MediaAsset.id.in_(asset_ids),
                MediaAsset.workspace_id == run.workspace_id,
                MediaAsset.project_id == run.project_id,
            ).all()
            if len(shot_assets) != len(asset_ids):
                raise RuntimeError("SHOT_ASSET_MISSING")
            if _has_duplicate_shot_media([asset.sha256 for asset in shot_assets]):
                raise RuntimeError("DUPLICATE_SHOT_MEDIA")
            _render_and_qc(db, run, plan, storyboard, asset_ids)
        except FlowSubmissionNotSent as exc:
            db.rollback()
            run = db.get(ContentVideoRun, run_id)
            if run:
                steps = json.loads(run.steps_json or "[]")
                if not _mark_flow_setup_blocked(run, steps, exc):
                    run.status = "FAILED"
                    run.error_code = "CONTENT_VIDEO_RUN_FAILED"
                    run.error_message = str(exc)[:1000]
                    run.finished_at = _now()
                db.commit()
            logger.warning("Flow generation was not submitted: run_id=%s error=%s", run_id, exc)
        except Exception as exc:
            db.rollback()
            run = db.get(ContentVideoRun, run_id)
            if run:
                steps = json.loads(run.steps_json or "[]")
                active = next((step for step in steps if step.get("state") == "SUBMITTING"), None)
                if active:
                    active["state"] = "NEEDS_RECONCILIATION"
                    run.status = "NEEDS_RECONCILIATION"
                    run.error_code = "PROVIDER_SUBMISSION_UNCERTAIN"
                else:
                    run.status = "FAILED"
                    run.error_code = str(exc) if isinstance(exc, (TTSProviderError, VietsubError)) or str(exc) in {"DUPLICATE_SHOT_MEDIA", "FLOW_AUDIO_MISSING"} else "CONTENT_VIDEO_RUN_FAILED"
                run.error_message = str(exc)[:1000]
                run.steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
                run.finished_at = _now()
                db.commit()
            logger.exception("Content video run failed: run_id=%s", run_id)
        finally:
            heartbeat.stop()
            _release_lease(db, token)


class ContentVideoWorker:
    def __init__(self, poll_seconds: float = 2.0):
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="content-video-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            worked = False
            token = str(uuid.uuid4())
            try:
                with SessionLocal() as db:
                    if _acquire_lease(db, token):
                        run = _claim_next_run(db, token)
                        if run:
                            worked = True
                            process_run(run.id, token)
                        else:
                            _release_lease(db, token)
            except Exception:
                logger.exception("Content video worker poll failed")
            if not worked:
                self._stop.wait(self.poll_seconds)


content_video_worker = ContentVideoWorker()
