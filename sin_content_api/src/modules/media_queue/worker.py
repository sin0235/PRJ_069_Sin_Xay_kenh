from __future__ import annotations
from src.modules.tac_vu_tu_xa.client import offload, pipeline

import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models.entities import AIGenerationJob, ContentVideoWorkerLease, MediaAsset, WorkspaceBudget
from src.modules.media_queue.contracts import DeferredMediaJob, GIOI_HAN_TAC_VU_DIEN_HOA
from src.modules.media_queue.service import FLOW_BACKEND_PROVIDERS, MEDIA_QUEUE_PROVIDERS, TEST_PROVIDERS, authorized_worker_tenant, is_production

logger = logging.getLogger(__name__)
LEASE_NAME = "content-video-flow"
LEASE_SECONDS = 480
_IN_FLIGHT = ("RUNNING", "SUBMITTING")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owns_worker_lease(db: Session, token: str) -> bool:
    return db.query(ContentVideoWorkerLease.name).filter(
        ContentVideoWorkerLease.name == LEASE_NAME,
        ContentVideoWorkerLease.token == token,
        ContentVideoWorkerLease.expires_at > _now(),
    ).first() is not None


def _worker_lease_exists(token: str):
    return exists(select(1).where(
        ContentVideoWorkerLease.name == LEASE_NAME,
        ContentVideoWorkerLease.token == token,
        ContentVideoWorkerLease.expires_at > _now(),
    ))


def _release_shared_lease(db: Session, token: str) -> None:
    try:
        result = db.execute(update(ContentVideoWorkerLease).where(
            ContentVideoWorkerLease.name == LEASE_NAME,
            ContentVideoWorkerLease.token == token,
        ).values(token=None, expires_at=None))
        db.commit()
        if result.rowcount != 1:
            logger.warning("Media worker shared lease was not released for token %s", token)
    except Exception:
        db.rollback()
        logger.exception("Failed to release media worker shared lease for token %s", token)


class _MediaJobHeartbeat:
    def __init__(self, token: str, job_id: str):
        self.token = token
        self.job_id = job_id
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="media-queue-heartbeat", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)

    def refresh_once(self) -> bool:
        with SessionLocal() as db:
            now = _now()
            shared = db.execute(update(ContentVideoWorkerLease).where(
                ContentVideoWorkerLease.name == LEASE_NAME,
                ContentVideoWorkerLease.token == self.token,
                ContentVideoWorkerLease.expires_at > now,
            ).values(expires_at=now + timedelta(seconds=LEASE_SECONDS)))
            if shared.rowcount != 1:
                db.rollback()
                return False
            job = db.execute(update(AIGenerationJob).where(
                AIGenerationJob.id == self.job_id,
                AIGenerationJob.lease_token == self.token,
                AIGenerationJob.state.in_(_IN_FLIGHT),
            ).values(lease_expires_at=now + timedelta(seconds=LEASE_SECONDS)))
            if job.rowcount != 1:
                db.rollback()
                return False
            db.commit()
            return True

    def _loop(self) -> None:
        while not self.stop_event.wait(LEASE_SECONDS / 4):
            try:
                if not self.refresh_once():
                    logger.warning("Media job lease lost for %s", self.job_id)
                    return
            except Exception:
                logger.exception("Media queue heartbeat failed for %s", self.job_id)


def _recover_expired_jobs(db: Session, token: str) -> int:
    now = _now()
    expired_ids = [row[0] for row in db.query(AIGenerationJob.id).filter(
        AIGenerationJob.provider.in_(MEDIA_QUEUE_PROVIDERS),
        AIGenerationJob.state.in_(_IN_FLIGHT),
        AIGenerationJob.lease_expires_at.is_not(None),
        AIGenerationJob.lease_expires_at < now,
    ).all()]
    recovered = 0
    for job_id in expired_ids:
        claimed = db.execute(update(AIGenerationJob).where(
            AIGenerationJob.id == job_id,
            AIGenerationJob.provider.in_(MEDIA_QUEUE_PROVIDERS),
            AIGenerationJob.state.in_(_IN_FLIGHT),
            AIGenerationJob.lease_expires_at < now,
        ).values(lease_token=token, lease_expires_at=now + timedelta(seconds=LEASE_SECONDS)))
        if claimed.rowcount != 1:
            continue
        fenced = db.execute(update(AIGenerationJob).where(
            AIGenerationJob.id == job_id,
            AIGenerationJob.lease_token == token,
            AIGenerationJob.state.in_(_IN_FLIGHT),
            _worker_lease_exists(token),
        ).values(
            state="NEEDS_RECONCILIATION",
            error_code="NEEDS_RECONCILIATION",
            error_message="Worker lease expired after provider submission may have started. Check the provider before retrying.",
            finished_at=now,
            lease_token=None,
            lease_expires_at=None,
        ))
        recovered += int(fenced.rowcount == 1)
    db.commit()
    return recovered


def _claim_next_job(db: Session, token: str) -> AIGenerationJob | None:
    job_id = db.query(AIGenerationJob.id).filter(
        AIGenerationJob.provider.in_(MEDIA_QUEUE_PROVIDERS),
        AIGenerationJob.state == "QUEUED",
    ).order_by(AIGenerationJob.created_at, AIGenerationJob.id).limit(1).scalar()
    if not job_id:
        return None
    claimed = db.execute(update(AIGenerationJob).where(
        AIGenerationJob.id == job_id,
        AIGenerationJob.provider.in_(MEDIA_QUEUE_PROVIDERS),
        AIGenerationJob.state == "QUEUED",
        _worker_lease_exists(token),
    ).values(
        state="RUNNING",
        lease_token=token,
        lease_expires_at=_now() + timedelta(seconds=LEASE_SECONDS),
    ))
    db.commit()
    if claimed.rowcount != 1:
        return None
    db.expire_all()
    return db.get(AIGenerationJob, job_id)


def _resume_waiting_auto_edit_jobs(db: Session, token: str) -> int:
    if not _owns_worker_lease(db, token):
        return 0
    terminal_states = {"SUCCEEDED", "FAILED", "CANCELLED", "EXPIRED", "BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_QUOTA"}
    resumed = 0
    parents = db.query(AIGenerationJob).filter(
        AIGenerationJob.provider == "MEDIA_VIDEO",
        AIGenerationJob.state == "WAITING_FOR_FLOW",
    ).all()
    for parent in parents:
        try:
            request = json.loads(parent.request_payload_json or "{}")
            parameters = request.get("parameters") or {}
            child_ids = parameters.get("flow_job_ids")
        except (TypeError, ValueError, AttributeError):
            continue
        if (
            request.get("operation") != "auto_edit_video"
            or parameters.get("phase") not in {"waiting_for_flow", "render"}
            or not isinstance(child_ids, list)
            or not child_ids
            or len(child_ids) > GIOI_HAN_TAC_VU_DIEN_HOA
            or any(not isinstance(child_id, str) or not child_id for child_id in child_ids)
            or len(child_ids) != len(set(child_ids))
        ):
            continue
        children = db.query(AIGenerationJob.id, AIGenerationJob.state).filter(
            AIGenerationJob.id.in_(child_ids),
            AIGenerationJob.workspace_id == parent.workspace_id,
            AIGenerationJob.project_id == parent.project_id,
        ).all()
        if len(children) != len(child_ids) or any(state not in terminal_states for _, state in children):
            continue
        parameters["phase"] = "render"
        request["parameters"] = parameters
        result = db.execute(update(AIGenerationJob).where(
            AIGenerationJob.id == parent.id,
            AIGenerationJob.provider == "MEDIA_VIDEO",
            AIGenerationJob.state == "WAITING_FOR_FLOW",
            _worker_lease_exists(token),
        ).values(
            state="QUEUED",
            request_payload_json=json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            error_code=None,
            error_message=None,
            finished_at=None,
            lease_token=None,
            lease_expires_at=None,
        ))
        resumed += int(result.rowcount == 1)
    db.commit()
    return resumed


def _mark_submitting(db: Session, job_id: str, token: str) -> bool:
    result = db.execute(update(AIGenerationJob).where(
        AIGenerationJob.id == job_id,
        AIGenerationJob.lease_token == token,
        AIGenerationJob.state == "RUNNING",
        _worker_lease_exists(token),
    ).values(state="SUBMITTING", lease_expires_at=_now() + timedelta(seconds=LEASE_SECONDS)))
    db.commit()
    return result.rowcount == 1


def _execute_job(db: Session, job: AIGenerationJob, request: dict) -> MediaAsset | list[MediaAsset] | DeferredMediaJob | None:
    operation = request.get("operation")
    backend_provider = str(request.get("backend_provider", ""))
    if is_production() and backend_provider.upper() in TEST_PROVIDERS:
        raise HTTPException(403, detail={"error_code": "TEST_PROVIDER_DISABLED", "message": "Nhà cung cấp kiểm thử bị chặn trong production."})
    parameters = request.get("parameters") or {}

    if operation == "generate_music_track":
        from src.modules.media_studio.music_provider import music_orchestrator
        from src.schemas.contracts import MusicGenerationMode, MusicProviderType

        return music_orchestrator.generate_music_track(
            db=db,
            workspace_id=job.workspace_id,
            user_id=job.created_by,
            prompt=request["prompt_text"],
            genre=parameters.get("genre", "Pop"),
            mood=parameters.get("mood", "Upbeat"),
            lyrics=parameters.get("lyrics"),
            duration_sec=int(parameters.get("duration_sec", 30)),
            provider=MusicProviderType(backend_provider),
            mode=MusicGenerationMode(parameters.get("mode", "CLIP_30S")),
            project_id=job.project_id,
            idempotency_key=request.get("idempotency_key"),
        )

    if operation == "generate_video_scene":
        from src.modules.media_studio.security import MEDIA_ROOT_DIR
        from src.modules.media_studio.video_provider import video_orchestrator

        start_image_id = parameters.get("start_image_asset_id")
        start_image_path = None
        if start_image_id:
            image = db.query(MediaAsset).filter(
                MediaAsset.id == start_image_id,
                MediaAsset.workspace_id == job.workspace_id,
            ).first()
            if not image or not (image.mime_detected or "").startswith("image/"):
                raise ValueError("IMAGE_NOT_FOUND: Ảnh tham chiếu không còn hợp lệ trong workspace.")
            path = (MEDIA_ROOT_DIR / image.storage_key).resolve()
            if not path.is_relative_to(MEDIA_ROOT_DIR.resolve()) or not path.is_file():
                raise ValueError("IMAGE_NOT_FOUND: Không tìm thấy tệp ảnh tham chiếu.")
            start_image_path = path
        expected_lease = getattr(job, "lease_token", None)
        def remember_flow_project(project_url):
            from src.modules.flow_sessions.context import validate_flow_project_url
            project_url = validate_flow_project_url(project_url)
            if not project_url:
                raise ValueError("FLOW_PROJECT_URL_INVALID")
            payload = {**request, "flow_project_url": project_url}
            saved = db.execute(update(AIGenerationJob).where(
                AIGenerationJob.id == job.id,
                AIGenerationJob.workspace_id == job.workspace_id,
                AIGenerationJob.state == "SUBMITTING",
                AIGenerationJob.lease_token == expected_lease,
                AIGenerationJob.lease_expires_at > _now(),
            ).values(request_payload_json=json.dumps(payload, ensure_ascii=False))
                .execution_options(synchronize_session="fetch"))
            if not expected_lease or saved.rowcount != 1:
                db.rollback()
                raise RuntimeError("MEDIA_JOB_LEASE_LOST_BEFORE_FLOW_SUBMISSION")
            db.commit()
            request["flow_project_url"] = project_url
        return video_orchestrator.generate_video_scene(
            db=db,
            workspace_id=job.workspace_id,
            user_id=job.created_by,
            prompt=request["prompt_text"],
            aspect_ratio=parameters.get("aspect_ratio", "9:16"),
            include_audio=bool(parameters.get("include_audio", True)),
            use_official_omni=bool(parameters.get("use_official_omni", False)),
            start_image_path=start_image_path,
            start_image_asset_id=start_image_id,
            project_id=job.project_id,
            remove_watermark=bool(parameters.get("remove_watermark", False)),
            flow_project_url=request.get("flow_project_url"),
            on_flow_project_created=remember_flow_project,
        )

    if operation == "generate_flow_job":
        from src.modules.media_studio.job_engine import job_engine

        return job_engine._execute_flow_payload(db, job, request)
    if operation == "render_auto_edit_diagram":
        from src.modules.dieu_phoi_dung.dung_video_dai import render_auto_edit_diagram

        return render_auto_edit_diagram(db, job, request)
    if operation == "auto_edit_video":
        from src.modules.dieu_phoi_dung.dung_video_dai import dung_video_dai

        return dung_video_dai(
            db,
            source_asset_id=parameters["source_asset_id"],
            workspace_id=job.workspace_id,
            user_id=job.created_by,
            project_id=job.project_id,
            job_id=job.id,
            phase=parameters.get("phase", "plan"),
            flow_job_ids=parameters.get("flow_job_ids"),
            plan_storage_key=parameters.get("plan_storage_key"),
            manifest_asset_id=parameters.get("manifest_asset_id"),
        )
    if operation == "create_content_video_storyboard":
        from src.modules.tao_video_noi_dung.contracts import CreatePlanRequest
        from src.modules.tao_video_noi_dung.service import create_plan

        create_plan(
            db,
            job.project_id,
            job.workspace_id,
            job.created_by,
            CreatePlanRequest(
                content=parameters.get("content"),
                target_duration_seconds=parameters.get("target_duration_seconds"),
                aspect_ratio=parameters.get("aspect_ratio", "9:16"),
                generate_flow_music=parameters.get("generate_flow_music", False),
            ),
            plan_id=job.id,
        )
        return None
    raise ValueError("INVALID_JOB_OPERATION: Unsupported media queue operation.")


@pipeline("MEDIA_JOB")
def _execute_with_profile_context(db: Session, job: AIGenerationJob, request: dict) -> MediaAsset:
    if str(request.get("backend_provider", "")).upper() not in FLOW_BACKEND_PROVIDERS:
        return _execute_job(db, job, request)
    profile_id = request.get("profile_id")
    if not profile_id:
        if is_production():
            raise HTTPException(
                status_code=409,
                detail={
                    "error_code": "FLOW_ACTIVE_PROFILE_REQUIRED",
                    "message": "Production Flow jobs require a saved workspace profile before execution.",
                },
            )
        return _execute_job(db, job, request)
    from src.modules.flow_sessions.context import profile_context
    from src.modules.flow_sessions.service import resolve_profile

    profile = resolve_profile(db, job.workspace_id, str(profile_id))
    with profile_context(job.workspace_id, profile.id):
        return _execute_job(db, job, request)


def _error_state(exc: Exception) -> tuple[str, str, str]:
    message = str(exc).strip() or "Media provider execution failed."
    error_name = exc.__class__.__name__
    detail = getattr(exc, "detail", None)
    code = str(getattr(exc, "error_code", "") or "")
    if isinstance(detail, dict):
        code = code or str(detail.get("error_code") or "")
        message = str(detail.get("message") or message)
    if not code:
        code = message.split(":", 1)[0]
    code = code.strip().upper()

    submitted = bool(getattr(exc, "submitted", False))
    if error_name == "FlowQuotaExceeded" and submitted:
        quota_code = code if code in {"FLOW_QUOTA_LIMITED", "FLOW_CREDITS_INSUFFICIENT"} else "FLOW_QUOTA_LIMITED"
        return "NEEDS_RECONCILIATION", quota_code, message
    if error_name in {"FlowLoginRequired", "FlowSubmissionNotSent"} and submitted:
        return "NEEDS_RECONCILIATION", "NEEDS_RECONCILIATION", message

    login_codes = {"FLOW_LOGIN_REQUIRED", "LOGIN_REQUIRED"}
    quota_codes = {"FLOW_QUOTA_LIMITED", "FLOW_CREDITS_INSUFFICIENT", "QUOTA_LIMITED"}
    if error_name == "FlowLoginRequired":
        return "BLOCKED_FLOW_LOGIN", "FLOW_LOGIN_REQUIRED", message
    if error_name == "FlowQuotaExceeded":
        canonical_code = "FLOW_CREDITS_INSUFFICIENT" if code == "FLOW_CREDITS_INSUFFICIENT" else "FLOW_QUOTA_LIMITED"
        return "BLOCKED_FLOW_QUOTA", canonical_code, message
    if error_name == "FlowSubmissionNotSent":
        if code in login_codes:
            return "BLOCKED_FLOW_LOGIN", "FLOW_LOGIN_REQUIRED", message
        if code in quota_codes:
            canonical_code = "FLOW_CREDITS_INSUFFICIENT" if code == "FLOW_CREDITS_INSUFFICIENT" else "FLOW_QUOTA_LIMITED"
            return "BLOCKED_FLOW_QUOTA", canonical_code, message
        return "FAILED", code if code and code != message.upper() else "FLOW_SUBMISSION_NOT_SENT", message

    if isinstance(detail, dict) and code:
        return "FAILED", code, message
    if isinstance(exc, (ValueError, KeyError)) or code in {
        "INVALID_JOB_OPERATION", "IMAGE_NOT_FOUND", "PROJECT_NOT_FOUND", "TEST_PROVIDER_DISABLED",
        "PROMPT_SAFETY_VIOLATION", "CREDENTIALS_MISSING", "CREDENTIALS_INVALID", "UNSUPPORTED_PROVIDER",
        "QUOTA_EXCEEDED", "MODEL_UNAVAILABLE", "REGION_UNAVAILABLE", "AUDIO_QC_FAILED",
        "FLOW_ASPECT_RATIO_UNSUPPORTED",
    }:
        return "FAILED", code if code.isupper() else "INVALID_JOB_PAYLOAD", message
    if "TIMEOUT" in message.upper() or "TIMED OUT" in message.upper():
        return "NEEDS_RECONCILIATION", "NEEDS_RECONCILIATION", message
    return "NEEDS_RECONCILIATION", "NEEDS_RECONCILIATION", message


def _record_typed_provider_error(
    db: Session,
    job: AIGenerationJob,
    request: dict,
    exc: Exception,
    state: str,
    code: str,
) -> None:
    if (
        exc.__class__.__name__ not in {"FlowLoginRequired", "FlowQuotaExceeded", "FlowSubmissionNotSent"}
        or (
            bool(getattr(exc, "submitted", False))
            and not (exc.__class__.__name__ == "FlowQuotaExceeded" and code in {"FLOW_QUOTA_LIMITED", "FLOW_CREDITS_INSUFFICIENT"})
        )
        or state not in {"BLOCKED_FLOW_LOGIN", "BLOCKED_FLOW_QUOTA", "NEEDS_RECONCILIATION"}
        or code not in {"FLOW_LOGIN_REQUIRED", "FLOW_QUOTA_LIMITED", "FLOW_CREDITS_INSUFFICIENT"}
    ):
        return
    profile_id = request.get("profile_id")
    if not profile_id:
        return
    try:
        from src.modules.flow_sessions.service import record_provider_error

        record_provider_error(db, job.workspace_id, str(profile_id), code)
    except Exception:
        db.rollback()
        logger.exception("Could not update Flow profile state for media job %s", job.id)


def _finish_job(db: Session, job: AIGenerationJob, token: str, *, state: str, error_code: str | None = None, error_message: str | None = None, asset: MediaAsset | list[MediaAsset] | None = None) -> bool:
    now = _now()
    values = {
        "state": state,
        "error_code": error_code,
        "error_message": error_message,
        "finished_at": now,
        "lease_token": None,
        "lease_expires_at": None,
    }
    if asset is not None:
        assets = asset if isinstance(asset, list) else [asset]
        values["output_asset_ids_json"] = json.dumps([item.id for item in assets])
        values["actual_cost"] = job.estimated_cost if job.credits_source == "API_BILLING" else 0.0
    result = db.execute(update(AIGenerationJob).where(
        AIGenerationJob.id == job.id,
        AIGenerationJob.provider.in_(MEDIA_QUEUE_PROVIDERS),
        AIGenerationJob.lease_token == token,
        AIGenerationJob.state.in_(_IN_FLIGHT),
        _worker_lease_exists(token),
    ).values(**values))
    if result.rowcount != 1:
        db.rollback()
        return False
    if asset is not None and job.credits_source == "API_BILLING" and job.estimated_cost > 0:
        budget = db.query(WorkspaceBudget).filter(WorkspaceBudget.workspace_id == job.workspace_id).first()
        if budget:
            budget.spent_units += job.estimated_cost
    db.commit()
    return True


def _defer_job(db: Session, job: AIGenerationJob, token: str, deferred: DeferredMediaJob) -> bool:
    result = db.execute(update(AIGenerationJob).where(
        AIGenerationJob.id == job.id,
        AIGenerationJob.provider.in_(MEDIA_QUEUE_PROVIDERS),
        AIGenerationJob.lease_token == token,
        AIGenerationJob.state.in_(_IN_FLIGHT),
        _worker_lease_exists(token),
    ).values(
        state="WAITING_FOR_FLOW",
        request_payload_json=deferred.request_payload_json,
        error_code=None,
        error_message=None,
        finished_at=None,
        lease_token=None,
        lease_expires_at=None,
    ))
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


def _cleanup_auto_edit_plan(job: AIGenerationJob, request: dict) -> None:
    parameters = request.get("parameters") or {}
    if request.get("operation") != "auto_edit_video" or parameters.get("phase") != "render":
        return
    try:
        from src.modules.media_studio.security import MEDIA_ROOT_DIR

        expected_key = Path(".cache") / "auto_edit" / f"{job.id}.json"
        if not isinstance(parameters.get("plan_storage_key"), str) or Path(parameters["plan_storage_key"]) != expected_key:
            return
        plan = MEDIA_ROOT_DIR / expected_key
        if not plan.is_symlink() and plan.resolve().is_relative_to(MEDIA_ROOT_DIR.resolve()):
            plan.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove auto-edit plan for media job %s", job.id, exc_info=True)


def process_next_media_job(db: Session, token: str) -> bool:
    heartbeat = None
    should_release_lease = True
    try:
        should_release_lease = _owns_worker_lease(db, token)
        if not should_release_lease:
            return False
        recovered = _recover_expired_jobs(db, token)
        resumed = _resume_waiting_auto_edit_jobs(db, token)
        job = _claim_next_job(db, token)
        if job is None:
            return recovered > 0 or resumed > 0

        heartbeat = _MediaJobHeartbeat(token, job.id)
        heartbeat.start()
        request = json.loads(job.request_payload_json)
        try:
            with authorized_worker_tenant(job.workspace_id, job.created_by, action="media.upload"):
                pass
        except Exception as exc:
            detail = getattr(exc, "detail", None)
            code = detail.get("error_code") if isinstance(detail, dict) else None
            message = detail.get("message") if isinstance(detail, dict) else detail
            if not code:
                code = "WORKER_PERMISSION_REVOKED" if getattr(exc, "status_code", None) in (401, 403) else "WORKER_AUTH_CHECK_FAILED"
            finished = _finish_job(
                db,
                job,
                token,
                state="FAILED",
                error_code=str(code),
                error_message=str(message or "Worker could not recheck current workspace permission."),
            )
            if finished:
                _cleanup_auto_edit_plan(job, request)
            return True
        if not _mark_submitting(db, job.id, token):
            return True
        asset = _execute_with_profile_context(db, job, request)
        if isinstance(asset, DeferredMediaJob):
            _defer_job(db, job, token, asset)
            return True
        if asset is None and request.get("operation") == "create_content_video_storyboard":
            pass
        elif isinstance(asset, list):
            if not asset or any(not getattr(item, "id", None) for item in asset):
                raise ValueError("INVALID_PROVIDER_RESULT: Provider returned no media asset.")
        elif not asset or not getattr(asset, "id", None):
            raise ValueError("INVALID_PROVIDER_RESULT: Provider returned no media asset.")
        if _finish_job(db, job, token, state="SUCCEEDED", asset=asset):
            _cleanup_auto_edit_plan(job, request)
    except Exception as exc:
        state, code, message = _error_state(exc)
        _record_typed_provider_error(
            db,
            job,
            request if "request" in locals() else {},
            exc,
            state,
            code,
        )
        if _finish_job(db, job, token, state=state, error_code=code, error_message=message):
            _cleanup_auto_edit_plan(job, request if "request" in locals() else {})
    finally:
        try:
            if heartbeat is not None:
                heartbeat.stop()
        finally:
            if should_release_lease:
                _release_shared_lease(db, token)
    return True
