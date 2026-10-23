from __future__ import annotations

import json
import hashlib
import logging
import subprocess
import tempfile
import threading
import uuid
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
from src.modules.media_studio.video_processor import video_processor
from src.schemas.contracts import TimelineAudioTrack, TimelineClip, TimelineDocument, TimelineMediaType
from session_manager import FlowLoginRequired, FlowSubmissionNotSent
from .cong_harness import approval_receipt_hash, dispatch_shot, verify_shot_receipt
from .contracts import ReconcileShotRequest
from .planner import Storyboard

logger = logging.getLogger(__name__)
LEASE_NAME = "content-video-flow"
LEASE_SECONDS = 480


def evaluate_video_qc(meta: dict, expected_duration_seconds: int, decode_ok: bool) -> list[str]:
    issues = []
    if (meta.get("width"), meta.get("height")) != (1080, 1920):
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


def evaluate_shot_qc(meta: dict, used_duration_seconds: int) -> list[str]:
    issues = evaluate_video_qc(meta, used_duration_seconds, decode_ok=True)
    if float(meta.get("duration_seconds", 0)) + 0.5 >= used_duration_seconds:
        issues = [issue for issue in issues if issue != "DURATION"]
    return issues


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _verified_asset_path(asset: MediaAsset, error_code: str) -> Path:
    path = (MEDIA_ROOT_DIR / asset.storage_key).resolve()
    if not path.is_relative_to(MEDIA_ROOT_DIR.resolve()) or not path.is_file():
        raise RuntimeError(f"{error_code}_FILE_MISSING")
    if _file_sha256(path) != asset.sha256:
        raise RuntimeError(f"{error_code}_HASH_MISMATCH")
    return path


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
    run.error_code = "FLOW_REQUEST_NOT_SUBMITTED"
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
    if not asset or asset.mime_detected != "video/mp4" or asset.source_product not in {"GOOGLE_FLOW", "UPLOAD"}:
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
        issues = evaluate_shot_qc(video_processor.probe_video(path), shot.duration_seconds)
        if issues:
            raise RuntimeError("SHOT_QC_FAILED:" + ",".join(issues))
        if run.voice_asset_id is None and audio_processor.probe_audio(path).get("codec_name") == "unknown":
            raise RuntimeError("FLOW_NATIVE_AUDIO_MISSING")
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


def _flow_voice_asset(db, run: ContentVideoRun, plan: ContentVideoPlan, asset_ids: list[str]) -> MediaAsset:
    steps = json.loads(run.steps_json or "[]")
    existing_id = next((step.get("flow_audio_asset_id") for step in steps if step.get("flow_audio_asset_id")), None)
    if existing_id:
        asset = db.query(MediaAsset).filter(
            MediaAsset.id == existing_id,
            MediaAsset.workspace_id == run.workspace_id,
            MediaAsset.project_id == run.project_id,
        ).first()
        if not asset:
            raise RuntimeError("FLOW_VOICE_ASSET_NOT_FOUND")
        _verified_asset_path(asset, "FLOW_VOICE_ASSET")
        return asset

    storyboard = Storyboard.model_validate_json(plan.storyboard_json)
    with tempfile.TemporaryDirectory(prefix="content-video-flow-audio-") as tmp:
        audio_path = Path(tmp) / "flow_voice.wav"
        command = [video_processor.ffmpeg_bin, "-y"]
        filters = []
        transition = 0.3
        for index, (shot, asset_id) in enumerate(zip(storyboard.shots, asset_ids, strict=True)):
            asset = db.query(MediaAsset).filter(
                MediaAsset.id == asset_id,
                MediaAsset.workspace_id == run.workspace_id,
                MediaAsset.project_id == run.project_id,
            ).first()
            if not asset:
                raise RuntimeError(f"FLOW_VOICE_SHOT_NOT_FOUND:{shot.shot_id}")
            video_path = _verified_asset_path(asset, "FLOW_VOICE_SHOT")
            audio_meta = audio_processor.probe_audio(video_path)
            if audio_meta.get("codec_name") == "unknown":
                raise RuntimeError(f"FLOW_NATIVE_AUDIO_MISSING:{shot.shot_id}")
            command.extend(["-i", str(video_path)])
            pad = f",apad=pad_dur={transition:.3f}" if index < len(asset_ids) - 1 else ""
            filters.append(
                f"[{index}:a:0]apad,atrim=duration={shot.duration_seconds},asetpts=PTS-STARTPTS,"
                f"aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo{pad}[a{index}]"
            )
        previous = "a0"
        for index in range(1, len(asset_ids)):
            output = f"xf{index}"
            filters.append(f"[{previous}][a{index}]acrossfade=d={transition:.3f}:c1=tri:c2=tri[{output}]")
            previous = output
        filters.append(f"[{previous}]loudnorm=I=-14:LRA=11:TP=-1.5[aout]")
        command.extend([
            "-filter_complex", ";".join(filters), "-map", "[aout]", "-c:a", "pcm_s16le",
            "-t", str(plan.target_duration_seconds), str(audio_path),
        ])
        result = subprocess.run(command, capture_output=True, text=True, timeout=600, check=False)
        if result.returncode != 0 or not audio_path.is_file():
            raise RuntimeError(f"FLOW_NATIVE_AUDIO_ASSEMBLY_FAILED:{result.stderr[-500:]}")
        meta = audio_processor.probe_audio(audio_path)
        if abs(float(meta["duration_seconds"]) - plan.target_duration_seconds) > 0.5:
            raise RuntimeError("FLOW_NATIVE_AUDIO_DURATION_INVALID")
        data = audio_path.read_bytes()

    filename = f"flow_voice_{run.id}.wav"
    output_path = get_workspace_storage_dir(run.workspace_id) / filename
    output_path.write_bytes(data)
    asset = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        storage_key=f"workspaces/{run.workspace_id}/media/{filename}",
        sha256=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        mime_detected="audio/wav",
        duration_ms=int(meta["duration_seconds"] * 1000),
        source_product="FLOW_NATIVE_VOICE",
        original_filename=filename,
        created_by=run.created_by,
        approval_state="UNREVIEWED",
    )
    db.add(asset)
    db.commit()
    steps[0]["flow_audio_asset_id"] = asset.id
    _save_run(db, run, steps)
    return asset


def _write_export_package(
    package_path: Path,
    video_path: Path,
    run: ContentVideoRun,
    plan: ContentVideoPlan,
    timeline: TimelineDocument,
    report: dict,
    shot_asset_hashes: list[dict],
    steps: list[dict],
    voice_asset: MediaAsset,
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
    manifest = {
        "run_id": run.id,
        "plan_id": plan.id,
        "plan_revision": plan.revision,
        "acceptance_mode": "HYBRID",
        "style_snapshot_sha256": plan.style_snapshot_sha256,
        "voice_asset": {
            "id": voice_asset.id,
            "sha256": voice_asset.sha256,
            "source": "UPLOAD" if run.voice_asset_id else "FLOW_NATIVE",
        },
        "shot_assets": shot_asset_hashes,
        "files": {"video/final.mp4": _file_sha256(video_path), **{name: hashlib.sha256(data).hexdigest() for name, data in files.items()}},
        "speech_alignment": "NOT_MEASURED",
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

    voice_input = _voice_input(db, run, plan)
    voice_asset = voice_input[0] if voice_input else _flow_voice_asset(db, run, plan, asset_ids)
    timeline = TimelineDocument(
        width=1080,
        height=1920,
        fps=30,
        clips=clips,
        voice_track=TimelineAudioTrack(asset_id=voice_asset.id, duration_ms=plan.target_duration_seconds * 1000),
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
    video_processor.render_timeline_document(timeline, resolve_asset, output_path, transition_seconds=0.3)
    meta = video_processor.probe_video(output_path)
    decode = subprocess.run(
        [video_processor.ffmpeg_bin, "-v", "error", "-i", str(output_path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    issues = evaluate_video_qc(meta, plan.target_duration_seconds, decode.returncode == 0 and not decode.stderr.strip())
    audio_qc = audio_processor.verify_audio_qc(output_path, expected_duration_sec=plan.target_duration_seconds)
    if not audio_qc.get("passed"):
        issues.append("AUDIO_QC")
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
        "voice_asset_id": voice_asset.id,
        "voice_source": "UPLOAD" if run.voice_asset_id else "FLOW_NATIVE",
        "voice_asset_sha256": voice_asset.sha256,
        "audio_qc": audio_qc,
        "speech_alignment": "NOT_MEASURED",
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
    run.output_asset_ids_json = json.dumps(asset_ids + [voice_asset.id, output.id, export.id])
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
            _voice_input(db, run, plan)
            steps = json.loads(run.steps_json or "[]")
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
                step["state"] = "SUBMITTING"
                step["started_at"] = _now().isoformat()
                run.current_step = shot.shot_id
                _save_run(db, run, steps)
                if not _heartbeat(db, token):
                    raise RuntimeError("WORKER_LEASE_LOST")
                start_image_path = None
                start_image_asset_id = None
                if shot_index:
                    previous_asset_id = steps[shot_index - 1].get("asset_id")
                    previous_asset = db.query(MediaAsset).filter(
                        MediaAsset.id == previous_asset_id,
                        MediaAsset.workspace_id == run.workspace_id,
                        MediaAsset.project_id == run.project_id,
                    ).first()
                    if not previous_asset:
                        raise RuntimeError("CONTINUITY_SOURCE_NOT_FOUND")
                    previous_path = _verified_asset_path(previous_asset, "CONTINUITY_SOURCE")
                    continuity_dir = tempfile.TemporaryDirectory(prefix="content-video-continuity-")
                    start_image_path = Path(continuity_dir.name) / f"{shot.shot_id}.jpg"
                    frame = subprocess.run(
                        [video_processor.ffmpeg_bin, "-y", "-sseof", "-0.1", "-i", str(previous_path), "-frames:v", "1", str(start_image_path)],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                    if frame.returncode != 0 or not start_image_path.is_file():
                        continuity_dir.cleanup()
                        raise RuntimeError("CONTINUITY_FRAME_EXTRACTION_FAILED")
                    start_image_asset_id = previous_asset.id
                try:
                    asset = dispatch_shot(
                        db=db,
                        run=run,
                        plan=plan,
                        shot=shot,
                        step=step,
                        start_image_path=start_image_path,
                        start_image_asset_id=start_image_asset_id,
                    )
                except FlowLoginRequired:
                    if shot_index:
                        continuity_dir.cleanup()
                    step["state"] = "READY"
                    run.status = "BLOCKED_FLOW_LOGIN"
                    run.error_code = "FLOW_LOGIN_REQUIRED"
                    run.error_message = "Đăng nhập Google Flow rồi tiếp tục run."
                    _save_run(db, run, steps)
                    return
                if shot_index:
                    continuity_dir.cleanup()
                if asset.workspace_id != run.workspace_id or asset.project_id != run.project_id:
                    raise RuntimeError("PROVIDER_ASSET_SCOPE_MISMATCH")
                path = _verified_asset_path(asset, "PROVIDER_OUTPUT")
                shot_meta = video_processor.probe_video(path)
                shot_issues = evaluate_shot_qc(shot_meta, shot.duration_seconds)
                if "DIMENSIONS" in shot_issues or "VIDEO_CODEC" in shot_issues or "DURATION" in shot_issues:
                    raise RuntimeError(f"SHOT_QC_FAILED:{shot.shot_id}:{','.join(shot_issues)}")
                step["state"] = "SUCCEEDED"
                step["asset_id"] = asset.id
                step["finished_at"] = _now().isoformat()
                run.output_asset_ids_json = json.dumps([item.get("asset_id") for item in steps if item.get("asset_id")])
                _save_run(db, run, steps)
            asset_ids = [step["asset_id"] for step in steps]
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
                    run.error_code = "CONTENT_VIDEO_RUN_FAILED"
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
