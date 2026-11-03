from __future__ import annotations
from src.modules.tac_vu_tu_xa.client import offload, pipeline

import json
import hashlib
import math
import logging
import os
import re
import subprocess
import threading
import tempfile
import uuid
import wave
import zipfile
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import or_, update

from src.database import SessionLocal
from src.media_process import run_media_command
from src.worker_fencing import fence_session, WorkerLeaseLost
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
from src.modules.media_studio.video_processor import (
    VIETSUB_FONT_PATH, VOICE_SPEED_MAX, VOICE_SPEED_MIN, fit_voice_speed, video_processor,
)
from src.schemas.contracts import TimelineAudioTrack, TimelineCaption, TimelineClip, TimelineDocument, TimelineMediaType
from session_manager import FlowLoginRequired, FlowSubmissionNotSent, FlowQuotaExceeded
from .cong_harness import approval_receipt_hash, dispatch_shot, verify_shot_receipt
from .contracts import ReconcileShotRequest
from .sfx import plan_sfx_cues, transition_sfx_cues
from .planner import DIAGRAM_LAYOUTS, PORTRAIT_DIAGRAM_LAYOUTS, Storyboard
from .brand import restore_display_words, to_spoken
from .render_engines import assembly_mode, render_placeholder, render_scene
from .tts_provider import TTSProviderError, tts_provider_manager
from .vietsub import MODEL_SIZE as VIETSUB_MODEL_SIZE, VietsubError, align_script_words, karaoke_cues, to_srt, transcribe_cached, transcribe_words_cached

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
    # Luồng hình ngắn hơn file nghĩa là hình đứng ở frame cuối trong khi âm thanh vẫn chạy.
    if float(meta.get("video_stream_duration_seconds", meta.get("duration_seconds", 0))) < float(meta.get("duration_seconds", 0)) - 0.5:
        issues.append("VIDEO_STREAM_SHORT")
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


@offload("probe_qc", "QC")
def _probe_shot_with_qc(path: Path, used_duration_seconds: int, aspect_ratio: str = "9:16") -> tuple[dict, list[str]]:
    meta = video_processor.probe_video(path)
    decode = run_media_command(
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


def _hashes_for_duplicate_check(steps: list[dict], assets: list) -> list[str]:
    """Hash media của từng shot để phát hiện hai shot dùng cùng một clip. Clip giữ chỗ của cảnh dựng ở bước ghép HyperFrames
    (render_engine hyperframes_assembly) giống hệt nhau từng byte khi cùng độ dài nên không tính vào kiểm tra này."""
    sha_by_id = {asset.id: asset.sha256 for asset in assets}
    return [sha_by_id[step["asset_id"]] for step in steps
            if step.get("render_engine") != "hyperframes_assembly" and step.get("asset_id") in sha_by_id]


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
    from src.modules.tac_vu_tu_xa.stages import extract_frame
    try:
        extract_frame(path, frame_path)
    except Exception:
        temp_dir.cleanup()
        raise
    if not frame_path.is_file() or frame_path.stat().st_size == 0:
        temp_dir.cleanup()
        raise RuntimeError("CONTINUITY_FRAME_EXTRACTION_FAILED")
    # Flow tìm ảnh trong thư viện theo tên file; tên cố định làm shot sau dùng nhầm ảnh cũ cùng tên, nên gắn mã băm nội dung vào tên.
    frame_path.rename(frame_path.with_name(f"khung_hinh_cuoi_{_file_sha256(frame_path)[:12]}.png"))
    return temp_dir


def _save_run(db, run: ContentVideoRun, steps: list[dict]) -> None:
    run.steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
    db.commit()
    db.refresh(run)


def _flow_project_target(steps: list[dict]) -> dict:
    return next((step for step in steps if step.get("state") == "SUBMITTING"), steps[0])


def _mark_flow_setup_blocked(run: ContentVideoRun, steps: list[dict], error: Exception) -> bool:
    active = next((step for step in steps if step.get("state") == "SUBMITTING"), None)
    if not active:
        return False
    active["state"] = "READY"
    quota = "FLOW_QUOTA_LIMITED" in str(error)
    run.status = "BLOCKED_FLOW_QUOTA" if quota else "BLOCKED_FLOW_SETUP"
    run.error_code = "FLOW_QUOTA_LIMITED" if quota else "FLOW_CREDITS_INSUFFICIENT" if "FLOW_CREDITS_INSUFFICIENT" in str(error) else "FLOW_REQUEST_NOT_SUBMITTED"
    run.error_message = str(error)[:1000]
    run.finished_at = None
    run.steps_json = json.dumps(steps, ensure_ascii=False, separators=(",", ":"))
    return True


def _mark_flow_quota_blocked(run: ContentVideoRun, step: dict, *, submitted: bool) -> None:
    step["state"] = "NEEDS_RECONCILIATION" if submitted else "READY"
    run.status = "NEEDS_RECONCILIATION" if submitted else "BLOCKED_FLOW_QUOTA"
    run.error_code = "FLOW_QUOTA_LIMITED"
    run.error_message = (
        "Flow báo hết hạn mức sau khi gửi; hãy đối soát cảnh trước khi đổi tài khoản và gửi lại."
        if submitted else "Flow đã hết hạn mức. Chọn hồ sơ tài khoản khác để tiếp tục trong project Flow mới."
    )


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
        or_(ContentVideoRun.lease_expires_at < _now(), ContentVideoRun.lease_expires_at.is_(None)),
    )
    if os.getenv("SIN_WORKSPACE_ID"):
        stale_runs = stale_runs.filter(ContentVideoRun.workspace_id == os.environ["SIN_WORKSPACE_ID"])
    stale_runs = stale_runs.all()
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
    query = db.query(ContentVideoRun).filter(ContentVideoRun.status == "QUEUED")
    if os.getenv("SIN_WORKSPACE_ID"):
        query = query.filter(ContentVideoRun.workspace_id == os.environ["SIN_WORKSPACE_ID"])
    run = query.order_by(ContentVideoRun.created_at).first()
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
    if (
        getattr(asset, "source_product", None) != "CONTENT_VIDEO_TTS"
        and abs(float(meta.get("duration_seconds", 0)) - plan.target_duration_seconds) > 0.5
    ):
        raise RuntimeError("VOICE_ASSET_DURATION_MISMATCH")
    return asset, path


def _tts_reference_path(db, run: ContentVideoRun) -> str | None:
    config = json.loads(run.tts_config_json) if run.tts_config_json else None
    if not config or not config.get("reference_asset_id"):
        return None
    reference = db.query(MediaAsset).filter(
        MediaAsset.id == config["reference_asset_id"],
        MediaAsset.workspace_id == run.workspace_id,
        MediaAsset.project_id == run.project_id,
    ).first()
    if not reference or not (reference.mime_detected or "").startswith("audio/"):
        raise TTSProviderError("TTS_REFERENCE_NOT_FOUND")
    return str(_verified_asset_path(reference, "TTS_REFERENCE"))


# Engine đọc BAHA từng chữ cái và Baha thành một từ lạ; Ba-ha được chuẩn hóa thành "ba ha".
_BAHA_WORD = re.compile(r"(?<!\w)ba-?ha(?!\w)", re.IGNORECASE)


def _pause_pad_samples(previous, current, rate: int, pause_seconds: float) -> int:
    """Số mẫu im lặng cần chèn giữa hai câu. Dùng hàm của gói VieNeu nếu có; máy điều phối không cài gói đó nên tự tính:
    khoảng lặng sẵn có ở cuối câu trước và đầu câu sau được trừ vào thời gian nghỉ cần có."""
    try:
        from vieneu_utils.core_utils import pause_pad_samples
        return int(pause_pad_samples(previous, current, rate, pause_seconds))
    except ImportError:
        import numpy as np

        def silent_edge(samples, from_end: bool) -> int:
            values = np.abs(np.asarray(samples, dtype=np.float32).reshape(-1))
            if from_end:
                values = values[::-1]
            loud = np.flatnonzero(values > 1e-3)
            return int(loud[0]) if loud.size else int(values.size)

        wanted = round(max(0.0, pause_seconds) * rate)
        return max(0, wanted - silent_edge(previous, True) - silent_edge(current, False))


def _prepare_run_tts(db, run: ContentVideoRun, shots: list, config: dict, token: str):
    """Lưu từng đoạn đã hoàn tất; restart không phải sinh lại toàn bộ giọng đọc."""
    import numpy as np
    # Ghi rõ mặc định hiệu lực vào hash để không dùng lại cache khử nhiễu cũ.
    config = {**config, "advanced": {"denoise_reference": False, "max_chars": 128, **(config.get("advanced") or {})}}
    reference = _tts_reference_path(db, run)
    reference_hash = _file_sha256(Path(reference)) if reference else None
    steps = json.loads(run.steps_json or "[]")
    samples, rate = [], None
    for index, shot in enumerate(shots):
        fingerprint = hashlib.sha256(json.dumps([config, to_spoken(shot.narration), reference_hash],
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        # Tên tệp ngắn (32 ký tự băm): đường dẫn đầy đủ phải dưới 260 ký tự của Windows (thư mục dự án nằm sâu).
        key = hashlib.sha256(f"{run.id}:{index}:{fingerprint}".encode()).hexdigest()[:32]
        directory = f"workspaces/{run.workspace_id}/media/.tts/"
        storage_key = f"{directory}{key}_{token[:8]}.npz"
        checkpoint = steps[index].get("tts_audio", {})
        cached_key = checkpoint.get("storage_key", "")
        if checkpoint.get("input_hash") == fingerprint and isinstance(cached_key, str) and cached_key.startswith(f"{directory}{key}_"):
            storage_key = cached_key
        path = (MEDIA_ROOT_DIR / storage_key).resolve()
        if not path.is_relative_to((MEDIA_ROOT_DIR / directory).resolve()):
            raise TTSProviderError("TTS_CHECKPOINT_PATH_INVALID")
        valid = (checkpoint.get("input_hash") == fingerprint and path.is_file()
            and checkpoint.get("sha256") == _file_sha256(path))
        if not valid:
            storage_key = f"{directory}{key}_{token[:8]}.npz"
            path = (MEDIA_ROOT_DIR / storage_key).resolve()
        if valid:
            with np.load(path, allow_pickle=False) as data:
                audio, source_rate = data["audio"].copy(), int(data["sample_rate"])
        else:
            run.current_step = f"TTS:{shot.shot_id}"
            db.commit()
            audio, source_rate = tts_provider_manager.synthesize(config, to_spoken(shot.narration), reference)
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            if not audio.size or source_rate <= 0 or not np.isfinite(audio).all():
                raise TTSProviderError("TTS_AUDIO_INVALID")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(f".{token[:8]}.tmp")
            try:
                with temporary.open("wb") as stream:
                    np.savez(stream, audio=audio, sample_rate=int(source_rate))
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            steps[index]["tts_audio"] = {"storage_key": storage_key, "sha256": _file_sha256(path),
                "input_hash": fingerprint, "sample_rate": int(source_rate),
                "duration_ms": round(len(audio) * 1000 / source_rate)}
            _save_run(db, run, steps)
        if not audio.size or source_rate <= 0 or not np.isfinite(audio).all():
            raise TTSProviderError("TTS_AUDIO_INVALID")
        if rate is not None and rate != source_rate:
            raise TTSProviderError("TTS_SAMPLE_RATE_MISMATCH")
        steps[index]["tts_audio"]["pause_after_ms"] = 0
        if samples:
            previous_text = shots[index - 1].narration.rstrip().rstrip('"\'”’)]')
            pause_seconds = 0.5 if previous_text.endswith((".", "!", "?", "…")) else 0.3 if previous_text.endswith((",", ";", ":")) else 0.0
            padding = _pause_pad_samples(samples[-1], audio, int(source_rate), pause_seconds)
            if padding:
                samples.append(np.zeros(padding, dtype=np.float32))
            steps[index - 1]["tts_audio"]["pause_after_ms"] = round(padding * 1000 / source_rate)
        samples.append(audio)
        rate = int(source_rate)
    if not samples:
        raise TTSProviderError("TTS_AUDIO_INVALID")
    _save_run(db, run, steps)
    return np.concatenate(samples), rate


DIAGRAM_LEAD_S, DIAGRAM_TAIL_S = 0.15, 0.35


def _is_diagram_run(storyboard) -> bool:
    """Toàn bộ shot là cảnh giấy dựng bằng mã: mỗi cảnh có thể dài đúng bằng giọng của shot (clip Flow thì cố định 10 giây)."""
    return all(shot.shot_kind == "UI_SIM" and shot.ui_scene and shot.ui_scene.layout in DIAGRAM_LAYOUTS for shot in storyboard.shots)


def _fit_diagram_voice(db, run: ContentVideoRun, audio, sample_rate: int):
    """Run toàn cảnh giấy: mỗi clip dài đúng bằng giọng của shot (gồm khoảng nghỉ sau shot) cộng đệm đầu và đuôi, nên hình luôn khớp giọng,
    không tua hình, không có đuôi im lặng. Ghi `clip_seconds` vào từng bước và trả về giọng đã đệm cho khớp từng clip."""
    import numpy as np
    steps = json.loads(run.steps_json or "[]")
    lengths = [round((step["tts_audio"]["duration_ms"] + step["tts_audio"].get("pause_after_ms", 0)) * sample_rate / 1000) for step in steps]
    lengths[-1] = len(audio) - sum(lengths[:-1])   # phần dư do làm tròn dồn vào shot cuối
    if lengths[-1] <= 0:
        raise TTSProviderError("TTS_AUDIO_INVALID")
    lead, pieces, start = round(DIAGRAM_LEAD_S * sample_rate), [], 0
    for step, length in zip(steps, lengths):
        chunk = audio[start:start + length]
        start += length
        seconds = max(4, math.ceil(length / sample_rate + DIAGRAM_LEAD_S + DIAGRAM_TAIL_S))
        if seconds > 20:
            error = TTSProviderError("TTS_DURATION_OUT_OF_RANGE")
            error.detail = f"Giọng của một shot dài {length / sample_rate:.1f}s, vượt giới hạn 19s của cảnh giấy; rút gọn lời shot đó."
            raise error
        step["clip_seconds"] = seconds
        pieces += [np.zeros(lead, dtype=np.float32), chunk, np.zeros(seconds * sample_rate - lead - len(chunk), dtype=np.float32)]
    _save_run(db, run, steps)
    return np.concatenate(pieces)


def _check_voice_fits(audio, sample_rate: int, shots: list) -> None:
    """Giọng lệch quá xa tổng thời lượng shot thì renderer không co giãn hình kịp (còn đuôi im lặng hoặc đứng hình); chặn trước khi tốn tín dụng Flow."""
    voice_seconds = len(audio) / sample_rate
    video_seconds = sum(shot.duration_seconds for shot in shots)
    if video_seconds / VOICE_SPEED_MAX <= voice_seconds <= video_seconds / VOICE_SPEED_MIN:
        return
    error = TTSProviderError("TTS_DURATION_OUT_OF_RANGE")
    error.detail = (
        f"Giọng đọc dài {voice_seconds:.1f}s so với video {video_seconds:.0f}s, ngoài khoảng "
        f"{video_seconds / VOICE_SPEED_MAX:.0f}s đến {video_seconds / VOICE_SPEED_MIN:.0f}s. "
        + ("Lời thoại quá ngắn: bổ sung lời cho mỗi shot." if voice_seconds < video_seconds else "Lời thoại quá dài: rút gọn lời mỗi shot.")
    )
    raise error


def _save_tts_voice(db, run: ContentVideoRun, audio, sample_rate: int) -> None:
    import numpy as np
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if (
        samples.size == 0 or sample_rate <= 0
        or not np.isfinite(samples).all()
    ):
        raise TTSProviderError("TTS_AUDIO_INVALID")
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    token = (getattr(run, "lease_token", None) or uuid.uuid4().hex)[:8]
    filename = f"content_video_{run.id}_tts_{token}.wav"
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
    meta = audio_processor.probe_audio(output_path)
    if meta.get("codec_name") not in {"pcm_s16le", "wav"} or float(meta.get("duration_seconds", 0)) <= 0:
        output_path.unlink(missing_ok=True)
        raise TTSProviderError("TTS_AUDIO_QC_FAILED")
    asset = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}", workspace_id=run.workspace_id,
        project_id=run.project_id, storage_key=storage_key,
        sha256=_file_sha256(output_path), byte_size=output_path.stat().st_size,
        mime_detected="audio/wav", duration_ms=int(meta["duration_seconds"] * 1000),
        source_product="CONTENT_VIDEO_TTS", original_filename=filename,
        created_by=run.created_by, approval_state="UNREVIEWED",
    )
    db.add(asset)
    run.voice_asset_id = asset.id
    run.output_asset_ids_json = json.dumps([*json.loads(run.output_asset_ids_json or "[]"), asset.id])
    db.commit()
    db.refresh(run)


def _karaoke_captions(words: list[dict], height: int, width: int, speed: float = 1.0) -> list[TimelineCaption]:
    """Cụm phụ đề karaoke; mốc theo giọng thật được co giãn cùng video trước khi retime."""
    scaled = [
        {"text": w["text"], "start_ms": round(w["start_ms"] * speed), "end_ms": max(round(w["end_ms"] * speed), round(w["start_ms"] * speed) + 1)}
        for w in words
    ]
    return [
        TimelineCaption(
            caption_id=f"karaoke_{index:04d}", text=cue["text"], start_ms=cue["start_ms"], duration_ms=cue["duration_ms"],
            font_size=52 if height > width else 36, safe_zone=True, words=cue["words"],
        )
        for index, cue in enumerate(karaoke_cues(scaled), start=1)
    ]


def _word_cache_path(run, voice_asset, voice_path: Path) -> Path:
    audio_sha256 = voice_asset.sha256 or _file_sha256(voice_path)
    key = hashlib.sha256(f"{run.workspace_id}:{audio_sha256}:{VIETSUB_MODEL_SIZE}:words".encode("utf-8")).hexdigest()
    return MEDIA_ROOT_DIR / ".cache" / "vietsub" / f"{key}.json"


def _tts_captions(shots: list, height: int = 1920, width: int = 1080, durations_ms: list[int] | None = None) -> list[TimelineCaption]:
    captions = []
    start_ms = 0
    for index, shot in enumerate(shots, start=1):
        duration_ms = durations_ms[index - 1] if durations_ms is not None else shot.duration_seconds * 1000
        captions.append(TimelineCaption(
            caption_id=f"tts_{index:03d}",
            text=shot.narration,
            start_ms=start_ms,
            duration_ms=duration_ms,
            font_size=52 if height > width else 36,
            safe_zone=True,
        ))
        start_ms += duration_ms
    return captions


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


def _diagram_word_times(shots: list, steps: list[dict], index: int, per_clip: bool = False) -> list[float] | None:
    """Mốc bắt đầu từng từ lời đọc của shot, quy về giây trên clip hình (đã tính tốc độ co giãn toàn video).
    None khi chưa có giọng TTS từng shot hoặc nhận dạng lỗi; khi đó cảnh neo theo vị trí âm tiết."""
    import numpy as np
    if 0 <= index < len(steps) and steps[index].get("word_times") is not None:
        return steps[index]["word_times"]
    shot = shots[index]
    try:
        durations = [step.get("tts_audio", {}).get("duration_ms", 0) + step.get("tts_audio", {}).get("pause_after_ms", 0) for step in steps]
        if not all(isinstance(item, (int, float)) and item > 0 for item in durations):
            return None
        checkpoint = steps[index]["tts_audio"]
        path = (MEDIA_ROOT_DIR / checkpoint["storage_key"]).resolve()
        if not path.is_relative_to(MEDIA_ROOT_DIR.resolve()) or _file_sha256(path) != checkpoint.get("sha256"):
            return None
        with np.load(path, allow_pickle=False) as data:
            audio, rate = np.asarray(data["audio"], dtype=np.float32).reshape(-1), int(data["sample_rate"])
        with tempfile.TemporaryDirectory(prefix="diagram_words_") as tmp:
            wav_path = Path(tmp) / "shot.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                wav.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes())
            asr_words = transcribe_words_cached(wav_path, MEDIA_ROOT_DIR / ".cache" / "diagram_words" / f"{checkpoint['sha256']}.json")
        words = to_spoken(shot.narration).split()
        aligned = align_script_words(words, asr_words)
        if per_clip:   # clip dài đúng bằng giọng của shot: giọng bắt đầu sau đệm đầu, không cần quy đổi tốc độ
            times = [DIAGRAM_LEAD_S + item["start_ms"] / 1000 for item in aligned]
            return times if len(times) == len(words) else None
        speed = fit_voice_speed(sum(item.duration_seconds for item in shots), sum(durations) / 1000)
        voice_start, clip_start = sum(durations[:index]) / 1000, sum(item.duration_seconds for item in shots[:index])
        times = [(voice_start + item["start_ms"] / 1000) * speed - clip_start for item in aligned]
        return times if len(times) == len(words) else None
    except Exception:
        logger.warning("DIAGRAM_WORD_TIMES_UNAVAILABLE shot=%s", shot.shot_id, exc_info=True)
        return None


def _use_hyperframes_assembly(storyboard, style: dict) -> bool:
    """Ghép project HyperFrames khi mọi shot là video Flow hoặc sơ đồ UI_SIM được hỗ trợ."""
    aspect_ratio = style.get("aspect_ratio", "9:16")
    if assembly_mode(style) != "hyperframes" or aspect_ratio not in {"9:16", "16:9"} or not storyboard.shots:
        return False
    return all(
        shot.shot_kind == "FLOW_ORIGAMI"
        or (shot.shot_kind == "UI_SIM" and shot.ui_scene and shot.ui_scene.layout in DIAGRAM_LAYOUTS
            and (aspect_ratio == "16:9" or shot.ui_scene.layout in PORTRAIT_DIAGRAM_LAYOUTS))
        for shot in storyboard.shots
    )


@offload("render_project", "RENDER_FINAL", output="output_path")
def _render_with_hyperframes(
    storyboard, steps: list[dict], voice_path: Path | None, words: list[dict] | None, output_path: Path,
    music_path: Path | None = None, sfx_cues: list[dict] | None = None, aspect_ratio: str = "16:9",
    shot_media: list[dict | None] | None = None,
) -> dict:
    """Dựng bằng HyperFrames; shot_media bổ sung các clip Flow cho cảnh đồ họa xen kẽ."""
    import shutil
    from . import hf_project
    from .planner import resolve_diagram_times

    if sfx_cues:
        sfx_cues = [{**cue, "path": Path(cue["path"])} for cue in sfx_cues if cue.get("path") and Path(cue["path"]).is_file()]

    shots = []
    for index, shot in enumerate(storyboard.shots):
        seconds = steps[index].get("clip_seconds") or shot.duration_seconds
        media = shot_media[index] if shot_media else None
        if shot.shot_kind == "FLOW_ORIGAMI":
            if not media:
                raise RuntimeError("HYPERFRAMES_VIDEO_ASSET_MISSING")
            shots.append({"shot_id": shot.shot_id, "scene": None, "media_path": media["path"],
                          "media_start_seconds": media.get("media_start_seconds", 0), "narration": shot.narration,
                          "seconds": seconds})
            continue
        word_times = None if shot_media is not None else _diagram_word_times(storyboard.shots, steps, index, per_clip=True)
        shots.append({"shot_id": shot.shot_id, "scene": shot.ui_scene, "narration": shot.narration, "seconds": seconds,
                      "events": resolve_diagram_times(shot.ui_scene, shot.narration, seconds, word_times), "word_times": word_times})
    work = Path(tempfile.mkdtemp(prefix="hf_run_", dir=output_path.parent))
    try:
        project = work / "du_an"
        info = hf_project.build_project(project, shots, voice_path, words, music_path=music_path, sfx_cues=sfx_cues, aspect_ratio=aspect_ratio)
        if os.environ.get("CONTENT_VIDEO_HF_CHECK") == "1":   # cổng check mất thêm vài phút trên NAS nên mặc định tắt
            lint = hf_project.check_project(project)["data"].get("lint", {})
            if lint.get("errorCount"):
                raise RuntimeError("HYPERFRAMES_CHECK_FAILED: " + json.dumps(lint.get("findings", [])[:3], ensure_ascii=False)[:600])
        hf_project.render_project(project, output_path)
    except Exception as exc:
        logger.exception("HYPERFRAMES_ASSEMBLY_FAILED")
        raise RuntimeError("HYPERFRAMES_ASSEMBLY_FAILED: " + str(exc)[:600]) from exc
    finally:
        shutil.rmtree(work, ignore_errors=True)
    meta = video_processor.probe_video(output_path)
    return {**meta, "video_content_duration_seconds": meta["duration_seconds"], "voice_audio_duration_seconds": meta["duration_seconds"],
            "silent_tail_seconds": 0, "frozen_tail_seconds": 0, "assembly": "hyperframes", "native_scenes": info["native_scenes"], "legacy_scenes": info["legacy_scenes"]}


def _render_ui_asset(db, run: ContentVideoRun, plan: ContentVideoPlan, shot, step: dict, word_times: list[float] | None = None, clip_seconds: int | None = None, placeholder: bool = False) -> MediaAsset:
    verify_shot_receipt(run, plan, shot, step)
    asset_id = str(uuid.uuid4())
    path = get_workspace_storage_dir(run.workspace_id) / f"ui_sim_{asset_id}.mp4"
    style = json.loads(plan.style_snapshot_json)
    aspect_ratio = style.get("aspect_ratio", "9:16")
    seconds = clip_seconds or shot.duration_seconds
    try:
        meta = render_placeholder(path, seconds, aspect_ratio) if placeholder else render_scene(shot.ui_scene, style, seconds, aspect_ratio, path, narration=shot.narration, word_times=word_times)
        _, issues = _probe_shot_with_qc(path, seconds, aspect_ratio)
        if issues:
            raise RuntimeError(f"SHOT_QC_FAILED:{shot.shot_id}:{','.join(issues)}")
        asset = MediaAsset(
            id=asset_id, workspace_id=run.workspace_id, project_id=run.project_id,
            storage_key=path.relative_to(MEDIA_ROOT_DIR).as_posix(), sha256=_file_sha256(path),
            byte_size=path.stat().st_size, mime_detected="video/mp4", duration_ms=seconds * 1000,
            source_product="CONTENT_VIDEO_UI_SIM", created_by=run.created_by,
        )
        db.add(asset)
        # Asset và receipt hoàn tất cùng transaction, có thể render lại nếu worker bị ngắt.
        step.update(state="SUCCEEDED", raw_asset_id=asset.id, asset_id=asset.id,
                    watermark_removed=False, finished_at=_now().isoformat(), render_engine=meta.get("render_engine", "playwright"))
        return asset
    except Exception:
        path.unlink(missing_ok=True)
        raise


@offload("brand_end", "RENDER_FINAL", output="video_path")
def _add_brand_end_card(video_path: Path) -> float:
    meta = video_processor.probe_video(video_path)
    duration = float(meta.get("duration_seconds", 0))
    width, height = int(meta.get("width", 0)), int(meta.get("height", 0))
    portrait = height >= width
    brand_dir = Path(__file__).resolve().parent / "brand"
    shot_name = "shot_ket_baha_midnight_doc_3s.mp4" if portrait else "shot_ket_baha_midnight_ngang_3s.mp4"
    shot = brand_dir / shot_name
    if duration <= 0 or width <= 0 or height <= 0 or not shot.is_file():
        raise RuntimeError("BRAND_END_CARD_INPUT_INVALID")
    shot_meta = video_processor.probe_video(shot)
    expected_shot_size = (1080, 1920) if portrait else (1920, 1080)
    if (shot_meta.get("width"), shot_meta.get("height")) != expected_shot_size or float(shot_meta.get("duration_seconds", 0)) < 2.9:
        raise RuntimeError("BRAND_END_CARD_ASSET_INVALID")
    start = max(0, duration - 3)
    card_seconds = min(3.0, duration)
    filters = (
        f"[1:v]fps=30,scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,"
        f"trim=duration={card_seconds:.3f},setpts=PTS-STARTPTS+{start:.3f}/TB[brand];"
        "[0:v][brand]overlay=x=0:y=0:eof_action=pass:shortest=0,format=yuv420p[v]"
    )
    temporary = video_path.with_name(f".{video_path.stem}.brand.tmp.mp4")
    try:
        result = run_media_command([
            video_processor.ffmpeg_bin, "-y", "-i", str(video_path), "-i", str(shot),
            "-filter_complex", filters, "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "copy", "-movflags", "+faststart", str(temporary),
        ], capture_output=True, text=True, timeout=120, check=False)
        if result.returncode != 0:
            raise RuntimeError("BRAND_END_CARD_RENDER_FAILED")
        os.replace(temporary, video_path)
        return min(3.0, duration)
    finally:
        temporary.unlink(missing_ok=True)


def _render_and_qc(db, run: ContentVideoRun, plan: ContentVideoPlan, storyboard: Storyboard, asset_ids: list[str]) -> None:
    clips = []
    shot_asset_hashes = []
    start_ms = 0
    step_clip_seconds = [step.get("clip_seconds") for step in json.loads(run.steps_json or "[]")]
    variable_clips = len(step_clip_seconds) == len(storyboard.shots) and all(step_clip_seconds)   # run toàn cảnh giấy: clip dài theo giọng
    for shot_index, (shot, asset_id) in enumerate(zip(storyboard.shots, asset_ids, strict=True)):
        duration_ms = step_clip_seconds[shot_index] * 1000 if variable_clips else shot.duration_seconds * 1000
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
    target_seconds = start_ms // 1000 if variable_clips else plan.target_duration_seconds

    aspect_ratio = json.loads(plan.style_snapshot_json).get("aspect_ratio", "9:16")
    width, height = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)
    voice_input = _voice_input(db, run, plan)
    voice_asset = voice_input[0] if voice_input else None
    caption_cues = []
    include_subtitles = getattr(run, "include_subtitles", True)
    is_tts_voice = bool(voice_asset and getattr(voice_asset, "source_product", None) == "CONTENT_VIDEO_TTS")
    word_aligned = False
    karaoke_words = None
    style = json.loads(plan.style_snapshot_json)
    hyperframes_eligible = _use_hyperframes_assembly(storyboard, style)
    hyperframes_has_flow = any(shot.shot_kind == "FLOW_ORIGAMI" for shot in storyboard.shots)
    use_hf = bool(hyperframes_eligible and (hyperframes_has_flow or (voice_input and is_tts_voice and variable_clips)))
    if voice_input and include_subtitles and is_tts_voice:
        speed = fit_voice_speed(target_seconds * 1000, voice_asset.duration_ms)
        measured = [
            (step["clip_seconds"] * 1000 if variable_clips else step["tts_audio"]["duration_ms"] + step["tts_audio"].get("pause_after_ms", 0))
            if step.get("tts_audio", {}).get("duration_ms") is not None else None
            for step in json.loads(run.steps_json or "[]")
        ]
        durations = None
        if len(measured) == len(storyboard.shots) and all(isinstance(item, (int, float)) and item > 0 for item in measured):
            # Captions burn before the renderer retimes video; undo that scale here.
            durations = [max(1, round(item * speed)) for item in measured]
        caption_cues = _tts_captions(storyboard.shots, height=height, width=width, durations_ms=durations)
        try:
            script_text = " ".join(shot.narration for shot in storyboard.shots)
            asr_words = transcribe_words_cached(voice_input[1], _word_cache_path(run, voice_asset, voice_input[1]))
            # Căn mốc theo chữ ĐỌC (Ba-ha, Gờ-rúp) rồi trả về chữ HIỂN THỊ (BAHA, Group) cho phụ đề.
            aligned = align_script_words(to_spoken(script_text).split(), asr_words)
            karaoke_words = restore_display_words(script_text.split(), aligned)
            caption_cues = _karaoke_captions(karaoke_words, height, width, speed)
            word_aligned = True
        except (VietsubError, ValueError, RuntimeError):
            logger.warning("Karaoke alignment unavailable for run %s; using per-shot captions", run.id)
    elif voice_input and include_subtitles:
        audio_sha256 = voice_asset.sha256 or _file_sha256(voice_input[1])
        cache_key = hashlib.sha256(f"{run.workspace_id}:{audio_sha256}:{VIETSUB_MODEL_SIZE}".encode("utf-8")).hexdigest()
        cache_path = MEDIA_ROOT_DIR / ".cache" / "vietsub" / f"{cache_key}.json"
        target_duration_ms = target_seconds * 1000
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
    vietsub_status = (
        "NO_AUDIO_FOR_VIETSUB" if not voice_asset else
        "DISABLED" if not include_subtitles else
        "GENERATED_FROM_TTS_SCRIPT" if is_tts_voice else
        "GENERATED_UNREVIEWED" if caption_cues else "NO_SPEECH_DETECTED"
    )
    timeline = TimelineDocument(
        width=width,
        height=height,
        fps=30,
        clips=clips,
        voice_track=TimelineAudioTrack(
            asset_id=voice_asset.id,
            duration_ms=voice_asset.duration_ms if is_tts_voice else target_seconds * 1000,
        ) if voice_asset else None,
        music_track=TimelineAudioTrack(
            asset_id=run.music_asset_id,
            duration_ms=target_seconds * 1000,
            gain_db=-18.0,
        ) if getattr(run, "music_asset_id", None) else None,
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

    fallback_paths: dict[str, Path] = {}   # clip dựng lại bằng Playwright khi ghép HyperFrames lỗi

    def resolve_asset(asset_id: str) -> Path:
        if asset_id in fallback_paths:
            return fallback_paths[asset_id]
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
    steps_now = json.loads(run.steps_json or "[]")
    render_meta = None
    clip_durations = [clip.duration_ms / 1000 for clip in clips]
    sfx_cues = plan_sfx_cues(storyboard.shots, clip_durations)
    if use_hf and os.getenv("CONTENT_VIDEO_HF_TRANSITIONS", "1") != "0":
        sfx_cues.extend(transition_sfx_cues(
            [clips[index].start_ms / 1000 for index in range(1, len(clips), 2)], "xe_giay",
        ))
    elif not use_hf and len(clips) > 1:
        sfx_cues.extend(transition_sfx_cues([clip.start_ms / 1000 for clip in clips[1:]]))
    if sfx_cues:
        sfx_cues = [{**cue, "path": Path(cue["path"])} for cue in sfx_cues if cue.get("path") and Path(cue["path"]).is_file()]
    music_path = None
    if getattr(run, "music_asset_id", None):
        music_asset = db.query(MediaAsset).filter(
            MediaAsset.id == run.music_asset_id,
            MediaAsset.workspace_id == run.workspace_id,
            MediaAsset.project_id == run.project_id,
        ).first()
        if not music_asset:
            raise RuntimeError("MUSIC_ASSET_NOT_FOUND")
        music_path = _verified_asset_path(music_asset, "MUSIC_ASSET")
    if use_hf:
        try:
            if hyperframes_has_flow:
                shot_media = [
                    {"path": resolve_asset(asset_ids[index]), "media_start_seconds": clips[index].trim_in_ms / 1000}
                    if shot.shot_kind == "FLOW_ORIGAMI" else None
                    for index, shot in enumerate(storyboard.shots)
                ]
                with tempfile.TemporaryDirectory(prefix="hf_visual_", dir=output_path.parent) as visual_dir:
                    visual_path = Path(visual_dir) / "visual.mp4"
                    _render_with_hyperframes(
                        storyboard, steps_now, None, None, visual_path,
                        aspect_ratio=style.get("aspect_ratio", "9:16"), shot_media=shot_media,
                    )
                    visual_asset_id = f"hf-visual-{uuid.uuid4().hex}"
                    audio_timeline = TimelineDocument(
                        width=width, height=height, fps=30,
                        clips=[TimelineClip(
                            clip_id="hyperframes-visual", asset_id=visual_asset_id,
                            media_type=TimelineMediaType.VIDEO, start_ms=0,
                            duration_ms=target_seconds * 1000, trim_in_ms=0,
                            trim_out_ms=target_seconds * 1000,
                        )],
                        voice_track=timeline.voice_track, music_track=timeline.music_track, captions=caption_cues,
                    )

                    def resolve_hf_asset(asset_id: str) -> Path:
                        return visual_path if asset_id == visual_asset_id else resolve_asset(asset_id)

                    render_meta = video_processor.render_timeline_document(
                        audio_timeline, resolve_hf_asset, output_path, transition_seconds=0,
                        caption_style="vietsub_karaoke_v2", preserve_voice_audio=is_tts_voice,
                        sfx_cues=sfx_cues,
                    )
                if not is_tts_voice:
                    audio_specs = [
                        (resolve_asset(asset_id), "video", clip.trim_in_ms / 1000, clip.duration_ms / 1000)
                        for asset_id, clip in zip(asset_ids, clips, strict=True)
                    ]
                    with tempfile.TemporaryDirectory(prefix="hf_flow_audio_", dir=output_path.parent) as audio_dir:
                        flow_audio_present = video_processor._preserve_native_clip_audio(
                            output_path, audio_specs, Path(audio_dir),
                            bool(voice_asset or getattr(run, "music_asset_id", None) or sfx_cues), target_seconds,
                        )
                    render_meta["flow_native_audio"] = flow_audio_present
                    if flow_audio_present:
                        levels = audio_processor.measure_loudness(output_path)
                        render_meta["audio_loudness_lufs"] = levels.get("measured_i_lufs")
                        render_meta["audio_true_peak_dbtp"] = levels.get("measured_tp_dbtp")
                        render_meta["audio_lra_lu"] = levels.get("measured_lra_lu")
                        render_meta["audio_normalization"] = "EBU_R128"
            else:
                render_meta = _render_with_hyperframes(
                    storyboard, steps_now, voice_input[1], karaoke_words if include_subtitles else None,
                    output_path, music_path=music_path, sfx_cues=sfx_cues, aspect_ratio=style.get("aspect_ratio", "9:16"),
                )
        except Exception as exc:
            if os.getenv("CONTENT_VIDEO_RENDER_FALLBACK", "1") == "0":
                raise
            # Đường lùi: dựng lại từng cảnh bằng Playwright rồi ghép kiểu cũ, run vẫn ra video.
            logger.warning("Ghép HyperFrames lỗi, quay về ghép cũ: %s", str(exc)[:300])
            output_path.unlink(missing_ok=True)
            style_now = json.loads(plan.style_snapshot_json)
            ratio = style_now.get("aspect_ratio", "9:16")
            for shot_index, (shot, asset_id) in enumerate(zip(storyboard.shots, asset_ids, strict=True)):
                if shot.shot_kind != "UI_SIM":
                    continue
                path = out_dir / f"hf_fallback_{run.id}_{shot_index}.mp4"
                duration = step_clip_seconds[shot_index] or shot.duration_seconds
                word_times = None if hyperframes_has_flow else _diagram_word_times(storyboard.shots, steps_now, shot_index, per_clip=True)
                render_scene(shot.ui_scene, {**style_now, "render_engine": "playwright"}, duration, ratio, path, narration=shot.narration, word_times=word_times)
                fallback_paths[asset_id] = path
    if render_meta is None:
        try:
            render_meta = video_processor.render_timeline_document(
                timeline, resolve_asset, output_path, transition_seconds=0.3,
                caption_style="vietsub_karaoke_v2", preserve_voice_audio=is_tts_voice,
                sfx_cues=sfx_cues,
            )
        finally:
            for path in fallback_paths.values():
                path.unlink(missing_ok=True)
    if is_tts_voice:
        time_scale = float(render_meta.get("video_content_duration_seconds", render_meta["duration_seconds"])) / target_seconds
        if abs(time_scale - 1.0) > 0.001:
            for clip in timeline.clips:
                clip.start_ms = round(clip.start_ms * time_scale)
                clip.duration_ms = max(1, round(clip.duration_ms * time_scale))
            for caption in timeline.captions:
                caption.start_ms = round(caption.start_ms * time_scale)
                caption.duration_ms = max(1, round(caption.duration_ms * time_scale))
                for word in caption.words:
                    word.start_ms = round(word.start_ms * time_scale)
                    word.end_ms = max(word.start_ms + 1, round(word.end_ms * time_scale))
            timeline_version.tracks_json = timeline.model_dump_json()
            db.commit()
    brand_end_card_seconds = _add_brand_end_card(output_path)
    meta = video_processor.probe_video(output_path)
    meta["flow_native_audio"] = bool(render_meta.get("flow_native_audio"))
    for key in (
        "audio_loudness_lufs", "audio_true_peak_dbtp", "audio_lra_lu",
        "audio_normalization", "video_playback_speed",
        "video_content_duration_seconds", "voice_audio_duration_seconds",
        "silent_tail_seconds", "frozen_tail_seconds",
    ):
        if key in render_meta:
            meta[key] = render_meta[key]
    from src.modules.tac_vu_tu_xa.stages import verify_decode
    decode_ok = verify_decode(output_path)["decode_ok"]
    issues = evaluate_video_qc(
        meta,
        render_meta.get("duration_seconds", target_seconds) if is_tts_voice else target_seconds,
        decode_ok,
        aspect_ratio=aspect_ratio,
    )
    if is_tts_voice and max(meta.get("silent_tail_seconds", 0), meta.get("frozen_tail_seconds", 0)) > 1.0:
        # Với giọng TTS, QC trên so độ dài với chính bản vừa render nên không bắt được hình/giọng lệch; kiểm riêng ở đây.
        issues.append("VOICE_VIDEO_DURATION_MISMATCH")
    if is_tts_voice:
        audio_meta = audio_processor.probe_audio(output_path)
        audio_qc = {
            "status": "RAW_TTS_PRESERVED",
            "reason": "LOUDNESS_NORMALIZATION_DISABLED",
            "passed": (
                audio_meta.get("codec_name") == "aac"
                and float(audio_meta.get("duration_seconds", 0)) > 0
                and abs(float(audio_meta.get("duration_seconds", 0)) - float(render_meta.get("duration_seconds", 0))) <= 0.5
            ),
        }
    elif voice_asset:
        audio_qc = audio_processor.verify_audio_qc(
            output_path, expected_duration_sec=target_seconds,
        )
    elif render_meta.get("audio_normalization") == "SFX_ONLY_PEAK_LIMITED":
        peak = meta.get("audio_true_peak_dbtp")
        audio_qc = {
            "status": "SFX_ONLY_PEAK_LIMITED",
            "reason": "SPARSE_SFX_HAS_NO_RELIABLE_INTEGRATED_LUFS",
            "passed": peak is not None and float(peak) <= -1.5,
        }
    else:
        audio_qc = {
            "status": "SKIPPED",
            "reason": "FLOW_NATIVE_AUDIO" if meta.get("flow_native_audio") else "NO_AUDIO_SELECTED",
            "passed": True,
        }
    if not audio_qc.get("passed"):
        issues.append("AUDIO_QC")
    tts_config = json.loads(run.tts_config_json) if getattr(run, "tts_config_json", None) else None
    report = {
        "status": "PASS" if not issues else "FAIL",
        "acceptance_mode": "HYBRID",
        "issues": issues,
        "expected_duration_seconds": target_seconds,
        "measured": meta,
        "timeline_version_id": timeline_version.id,
        "shot_asset_ids": asset_ids,
        "shot_asset_hashes": shot_asset_hashes,
        "style_snapshot_sha256": plan.style_snapshot_sha256,
        "voice_asset_id": voice_asset.id if voice_asset else None,
        "voice_source": "TTS" if voice_asset and getattr(voice_asset, "source_product", None) == "CONTENT_VIDEO_TTS" else "UPLOAD" if voice_asset else "FLOW_NATIVE" if meta.get("flow_native_audio") else "NONE",
        "flow_native_audio": bool(meta.get("flow_native_audio")),
        "brand_end_card": {
            "logo_asset": "logo_ngang_am_ban.png",
            "shot_asset": "shot_ket_baha_midnight_doc_3s.mp4" if aspect_ratio == "9:16" else "shot_ket_baha_midnight_ngang_3s.mp4",
            "duration_seconds": brand_end_card_seconds,
        },
        "voice_asset_sha256": voice_asset.sha256 if voice_asset else None,
        "tts_provider": tts_config.get("provider") if tts_config and voice_asset else None,
        "tts_model": {"GWEN_TTS": "g-group-ai-lab/gwen-tts-0.6B", "VIE_NEU_V3_TURBO": "pnnbao-ump/VieNeu-TTS-v3-Turbo"}.get(tts_config.get("provider")) if tts_config and voice_asset else None,
        "audio_qc": audio_qc,
        "vietsub_status": vietsub_status,
        "caption_count": len(caption_cues),
        "vietsub": {
            "status": vietsub_status,
            "provider": "storyboard" if is_tts_voice and include_subtitles else "faster-whisper" if voice_asset and include_subtitles else None,
            "model": VIETSUB_MODEL_SIZE if voice_asset and include_subtitles and not is_tts_voice else None,
            "language": "vi" if voice_asset and include_subtitles else None,
            "audio_sha256": voice_asset.sha256 if voice_asset else None,
            "style": "be_vietnam_pro_karaoke_v2" if caption_cues else None,
            "font_sha256": _file_sha256(VIETSUB_FONT_PATH) if caption_cues else None,
            "caption_count": len(caption_cues),
            "asr_quality_status": "NOT_RUN_TTS_SCRIPT" if is_tts_voice and include_subtitles else "UNVERIFIED" if voice_asset and include_subtitles else None,
        },
        "speech_alignment": ("TTS_ASR_WORD_ALIGNED" if word_aligned else "TTS_SHOT_TIMELINE") if is_tts_voice and include_subtitles else "WHISPER_ASR_TIMESTAMPS" if caption_cues else vietsub_status,
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
    output = MediaAsset(
        id=f"asset-{uuid.uuid4().hex[:12]}",
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        storage_key=f"workspaces/{run.workspace_id}/media/{filename}",
        sha256=_file_sha256(output_path),
        byte_size=output_path.stat().st_size,
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


@pipeline("AI_VIDEO")
def process_run(run_id: str, token: str | None = None) -> None:
    token = token or str(uuid.uuid4())
    with SessionLocal() as db:
        run = db.get(ContentVideoRun, run_id)
        if not run or run.lease_token != token or run.status != "RUNNING":
            return
        fence_session(db, token)
        heartbeat = _RunHeartbeat(run_id, token)
        heartbeat.start()
        try:
            if os.getenv("APP_ENV", "").lower() == "production":
                from src.modules.media_queue.service import authorized_worker_tenant
                with authorized_worker_tenant(run.workspace_id, run.created_by):
                    pass
            plan, _ = _plan_and_project(db, run)
            storyboard = Storyboard.model_validate_json(plan.storyboard_json)
            if os.getenv("APP_ENV", "").lower() == "production":
                steps = json.loads(run.steps_json or "[]")
                from src.modules.flow_sessions.service import resolve_profile
                for step, shot in zip(steps, storyboard.shots, strict=True):
                    if step.get("state") != "READY" or shot.shot_kind == "UI_SIM":
                        continue
                    try:
                        selected = resolve_profile(db, run.workspace_id, step.get("flow_profile_id"))
                    except HTTPException:
                        run.status = "BLOCKED_FLOW_SETUP"
                        run.error_code = "FLOW_PROFILE_REQUIRED"
                        run.error_message = "Chọn profile Flow rồi tiếp tục run."
                        db.commit()
                        return
                    step["flow_profile_id"] = selected.id
                _save_run(db, run, steps)
            tts_config = json.loads(run.tts_config_json) if run.tts_config_json else None
            if tts_config and not run.voice_asset_id:
                run.current_step = "TTS"
                db.commit()
                audio, sample_rate = _prepare_run_tts(db, run, storyboard.shots, tts_config, token)
                if _is_diagram_run(storyboard):
                    audio = _fit_diagram_voice(db, run, audio, sample_rate)
                else:
                    _check_voice_fits(audio, sample_rate, storyboard.shots)
                _save_tts_voice(db, run, audio, sample_rate)
            _voice_input(db, run, plan)
            steps = json.loads(run.steps_json or "[]")
            for s_idx, (s_step, s_shot) in enumerate(zip(steps, storyboard.shots, strict=True)):
                if s_step.get("word_times") is None and getattr(s_shot, "ui_scene", None) and s_shot.ui_scene.layout in DIAGRAM_LAYOUTS:
                    computed = _diagram_word_times(storyboard.shots, steps, s_idx, per_clip=bool(s_step.get("clip_seconds")))
                    if computed is not None:
                        s_step["word_times"] = computed
            _save_run(db, run, steps)
            steps = json.loads(run.steps_json or "[]")
            pending_profile = next((step.get("flow_profile_id") for step in steps if step.get("state") == "READY"), None)
            flow_project_url = next((step.get("flow_project_url") for step in steps
                if step.get("flow_project_url") and step.get("flow_profile_id") == pending_profile), None)

            def save_flow_project_url(project_url: str) -> None:
                nonlocal flow_project_url
                if flow_project_url and flow_project_url != project_url:
                    raise RuntimeError("FLOW_PROJECT_CHANGED_WITHIN_RUN")
                flow_project_url = project_url
                _flow_project_target(steps)["flow_project_url"] = project_url
                _save_run(db, run, steps)

            if not _heartbeat(db, token):
                raise RuntimeError("WORKER_LEASE_LOST")

            for shot_index, (step, shot) in enumerate(zip(steps, storyboard.shots, strict=True)):
                verify_shot_receipt(run, plan, shot, step)
                if step.get("state") == "SUCCEEDED":
                    continue
                if shot.shot_kind == "UI_SIM":
                    run.current_step = shot.shot_id
                    step["started_at"] = _now().isoformat()
                    _save_run(db, run, steps)
                    clip_seconds = step.get("clip_seconds")
                    hf_assembly = _use_hyperframes_assembly(storyboard, json.loads(plan.style_snapshot_json)) and (
                        bool(clip_seconds) or any(item.shot_kind == "FLOW_ORIGAMI" for item in storyboard.shots)
                    )
                    word_times = None if hf_assembly else (_diagram_word_times(storyboard.shots, steps, shot_index, per_clip=bool(clip_seconds)) if shot.ui_scene.layout in DIAGRAM_LAYOUTS else None)
                    _render_ui_asset(db, run, plan, shot, step, word_times, clip_seconds, placeholder=hf_assembly)
                    run.output_asset_ids_json = json.dumps([item["asset_id"] for item in steps if item.get("asset_id")])
                    _save_run(db, run, steps)
                    continue
                if step.get("state") == "CLEANING":
                    raw_asset_id = step.get("raw_asset_id") or step.get("asset_id")
                    raw_asset = db.query(MediaAsset).filter(
                        MediaAsset.id == raw_asset_id,
                        MediaAsset.workspace_id == run.workspace_id,
                        MediaAsset.project_id == run.project_id,
                    ).first()
                    if not raw_asset:
                        raise RuntimeError("WATERMARK_SOURCE_ASSET_MISSING")
                    _verified_asset_path(raw_asset, "FLOW_SOURCE")
                    # shortcut: Flow clips retain their watermark until a Linux remover is available.
                    step.update({
                        "state": "SUCCEEDED", "raw_asset_id": raw_asset.id, "asset_id": raw_asset.id,
                        "watermark_removed": False, "finished_at": _now().isoformat(),
                    })
                    run.output_asset_ids_json = json.dumps([item.get("asset_id") for item in steps if item.get("asset_id")])
                    _save_run(db, run, steps)
                    continue
                if step.get("state") == "SUBMITTING":
                    run.status = "NEEDS_RECONCILIATION"
                    run.error_code = "PROVIDER_SUBMISSION_UNCERTAIN"
                    run.error_message = f"Không gửi lại shot {shot.shot_id} vì trạng thái nhà cung cấp chưa rõ."
                    db.commit()
                    return
                if os.getenv("APP_ENV", "").lower() == "production":
                    with authorized_worker_tenant(run.workspace_id, run.created_by):
                        pass
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
                    reference_path = next(Path(reference_temp.name).glob("khung_hinh_cuoi*.png"))
                    reference_asset_id = previous_asset.id
                step["state"] = "SUBMITTING"
                step["started_at"] = _now().isoformat()
                step["provider_attempt_id"] = step["operation_id"]
                run.current_step = shot.shot_id
                _save_run(db, run, steps)
                if not _heartbeat(db, token):
                    raise RuntimeError("WORKER_LEASE_LOST")
                try:
                    try:
                        from src.modules.flow_sessions.context import profile_context
                        selected = step.get("flow_profile_id")
                        if selected:
                            from src.modules.flow_sessions.service import resolve_profile
                            resolve_profile(db, run.workspace_id, selected)
                        context = profile_context(run.workspace_id, selected, flow_project_url) if selected else nullcontext()
                        with context:
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
                except FlowQuotaExceeded as exc:
                    if step.get("flow_profile_id"):
                        from src.modules.flow_sessions.service import resolve_profile
                        profile = resolve_profile(db, run.workspace_id, step["flow_profile_id"])
                        profile.state = "QUOTA_LIMITED"
                        profile.google_flow_state = "QUOTA_LIMITED"
                        profile.error_code = "FLOW_QUOTA_LIMITED"
                        profile.last_checked_at = _now()
                    _mark_flow_quota_blocked(run, step, submitted=exc.submitted)
                    _save_run(db, run, steps)
                    return
                except FlowLoginRequired:
                    step["state"] = "READY"
                    run.status = "BLOCKED_FLOW_LOGIN"
                    run.error_code = "FLOW_LOGIN_REQUIRED"
                    run.error_message = "Đăng nhập Google Flow rồi tiếp tục run."
                    if step.get("flow_profile_id"):
                        from src.modules.flow_sessions.service import resolve_profile
                        profile = resolve_profile(db, run.workspace_id, step["flow_profile_id"])
                        profile.state = "LOGIN_REQUIRED"
                        profile.google_flow_state = "LOGIN_REQUIRED"
                    _save_run(db, run, steps)
                    return
                if asset.workspace_id != run.workspace_id or asset.project_id != run.project_id:
                    raise RuntimeError("PROVIDER_ASSET_SCOPE_MISMATCH")
                path = _verified_asset_path(asset, "PROVIDER_OUTPUT")
                aspect_ratio = json.loads(plan.style_snapshot_json).get("aspect_ratio", "9:16")
                shot_meta, shot_issues = _probe_shot_with_qc(path, shot.duration_seconds, aspect_ratio)
                if shot_issues:
                    raise RuntimeError(f"SHOT_QC_FAILED:{shot.shot_id}:{','.join(shot_issues)}")
                step.update({
                    "state": "SUCCEEDED",
                    "raw_asset_id": asset.id,
                    "asset_id": asset.id,
                    "watermark_removed": False,
                    "finished_at": _now().isoformat(),
                })
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
            if _has_duplicate_shot_media(_hashes_for_duplicate_check(steps, shot_assets)):
                raise RuntimeError("DUPLICATE_SHOT_MEDIA")
            _render_and_qc(db, run, plan, storyboard, asset_ids)
        except WorkerLeaseLost:
            db.rollback()
            logger.warning("Discarding expired worker result: run_id=%s", run_id)
        except FlowSubmissionNotSent as exc:
            db.rollback()
            run = db.get(ContentVideoRun, run_id)
            if run and run.lease_token == token and _heartbeat(db, token):
                steps = json.loads(run.steps_json or "[]")
                if _mark_flow_setup_blocked(run, steps, exc):
                    active = next((step for step in steps if step.get("state") == "READY" and step.get("flow_profile_id")), None)
                    if active and run.error_code in {"FLOW_CREDITS_INSUFFICIENT", "FLOW_QUOTA_LIMITED"}:
                        from src.modules.flow_sessions.service import resolve_profile
                        profile = resolve_profile(db, run.workspace_id, active["flow_profile_id"])
                        profile.state = "QUOTA_LIMITED"
                        profile.google_flow_state = "QUOTA_LIMITED"
                else:
                    run.status = "FAILED"
                    run.error_code = "CONTENT_VIDEO_RUN_FAILED"
                    run.error_message = str(exc)[:1000]
                    run.finished_at = _now()
                db.commit()
            logger.warning("Flow generation was not submitted: run_id=%s error=%s", run_id, exc)
        except Exception as exc:
            db.rollback()
            run = db.get(ContentVideoRun, run_id)
            if run and run.lease_token == token and _heartbeat(db, token):
                steps = json.loads(run.steps_json or "[]")
                active = next((step for step in steps if step.get("state") == "SUBMITTING"), None)
                if active:
                    active["state"] = "NEEDS_RECONCILIATION"
                    run.status = "NEEDS_RECONCILIATION"
                    run.error_code = "PROVIDER_SUBMISSION_UNCERTAIN"
                else:
                    run.status = "FAILED"
                    run.error_code = str(exc) if isinstance(exc, (TTSProviderError, VietsubError)) or str(exc) == "DUPLICATE_SHOT_MEDIA" else "CONTENT_VIDEO_RUN_FAILED"
                    if any(step.get("shot_kind") == "UI_SIM" and step.get("shot_id") == run.current_step
                           and step.get("state") == "READY" for step in steps):
                        run.error_code = "UI_SIM_RENDER_FAILED"
                run.error_message = (getattr(exc, "detail", "") or str(exc))[:1000]
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
                    from src.modules.tac_vu_tu_xa.queue_scope import restrict_dev_queue
                    restrict_dev_queue(db)
                    if _acquire_lease(db, token):
                        run = _claim_next_run(db, token)
                        if run:
                            worked = True
                            process_run(run.id, token)
                        else:
                            from src.modules.voice_studio.worker import claim_next_voice_job, process_voice_studio_job
                            voice_job = claim_next_voice_job(db, token)
                            if voice_job:
                                worked = True
                                process_voice_studio_job(voice_job.id, token)
                            else:
                                from src.modules.media_queue.service import process_next_media_job
                                worked = process_next_media_job(db, token)
                                if not worked:
                                    _release_lease(db, token)
            except Exception:
                logger.exception("Content video worker poll failed")
            if not worked:
                self._stop.wait(self.poll_seconds)


content_video_worker = ContentVideoWorker()
