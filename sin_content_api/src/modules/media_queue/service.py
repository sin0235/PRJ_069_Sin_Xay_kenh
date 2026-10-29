from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.tenancy import TenantContext, _canonical_auth_modules, authorize_action
from src.config import settings
from src.models.entities import AIGenerationJob

MEDIA_QUEUE_PROVIDERS = {"MEDIA_MUSIC", "MEDIA_VIDEO"}
FLOW_BACKEND_PROVIDERS = {"FLOW_BROWSER_PILOT", "FLOW_MUSIC_ASSISTED", "GOOGLE_FLOW", "GOOGLE_FLOW_ASSISTED"}
TEST_PROVIDERS = {"FAKE_PROVIDER", "LOCAL_TEST_SYNTH", "LOCAL_TEST"}


def is_production() -> bool:
    return (os.getenv("APP_ENV") or settings.app_env).strip().lower() in {"prod", "production"}


def media_idempotency_hash(workspace_id: str, provider: str, key: str) -> str:
    value = f"{workspace_id}\0{provider}\0{key.strip()}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def resolve_profile_id(
    tenant: Any,
    parameters: dict[str, Any] | None = None,
    *,
    workspace_id: str | None = None,
) -> str | None:
    request_workspace_id = workspace_id or getattr(tenant, "workspace_id", None)
    flow_context = getattr(tenant, "flow_context", None)
    if isinstance(flow_context, dict) and flow_context.get("profile_id"):
        return str(flow_context["profile_id"])
    profile_id = getattr(tenant, "profile_id", None) or getattr(tenant, "flow_profile_id", None)
    if profile_id:
        return str(profile_id)
    parameters = parameters or {}
    profile_id = parameters.get("profile_id")
    if not profile_id and isinstance(parameters.get("flow_context"), dict):
        profile_id = parameters["flow_context"].get("profile_id")
    if profile_id:
        return str(profile_id)

    try:
        from src.modules.flow_sessions.context import current_flow_profile

        selected = current_flow_profile()
        if selected and request_workspace_id and selected.workspace_id == request_workspace_id:
            return selected.profile_id
    except ImportError:
        pass
    return None


def enqueue_media_job(
    db: Session,
    *,
    workspace_id: str,
    user_id: str,
    provider: str,
    operation: str,
    backend_provider: str,
    provider_mode: str,
    model_id: str,
    prompt_text: str,
    parameters: dict[str, Any],
    idempotency_key: str,
    project_id: str | None = None,
    profile_id: str | None = None,
    estimated_cost: float = 0.0,
    credits_source: str = "FLOW_MUSIC_PLUS",
) -> AIGenerationJob:
    if provider not in MEDIA_QUEUE_PROVIDERS:
        raise ValueError(f"Unsupported media queue provider: {provider}")
    if is_production() and backend_provider.upper() in TEST_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "TEST_PROVIDER_DISABLED",
                "message": "Nhà cung cấp kiểm thử không được phép trong môi trường production.",
            },
        )

    key = idempotency_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail={"error_code": "IDEMPOTENCY_KEY_REQUIRED", "message": "Thiếu khóa idempotency."})
    key_hash = media_idempotency_hash(workspace_id, provider, key)
    existing = db.query(AIGenerationJob).filter(AIGenerationJob.idempotency_key == key_hash).first()
    if is_production() and backend_provider.upper() in FLOW_BACKEND_PROVIDERS:
        from src.modules.flow_sessions.service import resolve_profile

        # An idempotent retry keeps the original profile even if the owner changed
        # the active profile after enqueueing. Only resume can change that attempt.
        if profile_id is None and existing is not None:
            try:
                saved_request = json.loads(existing.request_payload_json or "{}")
            except (TypeError, ValueError):
                saved_request = {}
            if isinstance(saved_request, dict):
                profile_id = saved_request.get("profile_id")
        profile_id = resolve_profile(db, workspace_id, profile_id).id

    envelope = {
        "provider": provider,
        "operation": operation,
        "backend_provider": backend_provider,
        "prompt_text": prompt_text,
        "parameters": parameters,
        "profile_id": profile_id,
        "idempotency_key": key,
        "idempotency_hash": key_hash,
    }
    request_payload_json = json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if existing:
        if existing.request_payload_json != request_payload_json:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "IDEMPOTENCY_CONFLICT", "message": "Khóa idempotency đã được dùng với yêu cầu khác."},
            )
        return existing

    job = AIGenerationJob(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        project_id=project_id,
        asset_type="MUSIC" if provider == "MEDIA_MUSIC" else "VIDEO",
        provider=provider,
        provider_mode=provider_mode,
        model_id=model_id,
        idempotency_key=key_hash,
        state="QUEUED",
        request_payload_json=request_payload_json,
        estimated_cost=estimated_cost,
        actual_cost=0.0,
        credits_source=credits_source,
        output_asset_ids_json="[]",
        created_by=user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(AIGenerationJob).filter(AIGenerationJob.idempotency_key == key_hash).first()
        if existing and existing.request_payload_json == request_payload_json:
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "IDEMPOTENCY_CONFLICT", "message": "Khóa idempotency đã được dùng với yêu cầu khác."},
        )
    db.refresh(job)
    return job


@contextmanager
def authorized_worker_tenant(
    workspace_id: str,
    user_id: str,
    action: str = "media.upload",
) -> Iterator[TenantContext]:
    auth = _canonical_auth_modules()
    auth_db_generator = auth["get_auth_db"]()
    auth_db = None
    try:
        auth_db = next(auth_db_generator)
        auth["set_tenant_context"](workspace_id, auth_db)
        actor = auth["load_actor_for_user"](
            auth_db,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if actor is None or actor.user_id != user_id or actor.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "WORKER_ACTOR_REVOKED", "message": "Người tạo không còn quyền trong workspace."},
            )
        tenant = TenantContext(
            workspace_id=workspace_id,
            user_id=user_id,
            actor=actor,
            auth_db=auth_db,
            request_id=f"worker-{uuid.uuid4()}",
        )
        authorize_action(tenant, action)
        yield tenant
    finally:
        if auth_db is not None:
            try:
                auth_db.rollback()
            except Exception:
                pass
            try:
                auth["clear_tenant_context"](auth_db)
            except Exception:
                pass
        close = getattr(auth_db_generator, "close", None)
        if close is not None:
            close()
        try:
            auth["clear_tenant_context"]()
        except Exception:
            pass


def process_next_media_job(db: Session, token: str) -> bool:
    """Lazy worker entrypoint shared by the parent runtime poller."""
    from src.modules.media_queue.worker import process_next_media_job as process

    return process(db, token)


