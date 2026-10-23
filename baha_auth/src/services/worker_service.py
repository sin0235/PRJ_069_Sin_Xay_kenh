"""Cấp thẻ worker theo quyền hiện tại và kiểm tra lại trước khi thực thi."""

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from baha_auth.src.config import settings
from baha_auth.src.models.entities import (
    ApprovalPolicy,
    ApprovalRun,
    BusinessResource,
    DelegatedJobGrant,
)
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.policy.registry import registry
from baha_auth.src.services.danh_tinh_service import load_actor
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event


_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_GRANT_TTL = timedelta(minutes=15)
_APPROVAL_REQUIRED_ACTIONS = {"publishing.schedule", "publishing.execute"}


class WorkerServiceError(ValueError):
    """Lỗi từ chối cấp quyền worker cùng mã HTTP an toàn cho router."""

    def __init__(self, code: str, status_code: int = 403):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class WorkerRecheckResult:
    """Kết quả recheck kèm binding tài nguyên canonical khi được phép."""

    allowed: bool
    workspace_id: Optional[str] = None
    target_resource: Optional[str] = None
    resource_type: Optional[str] = None
    artifact_version: Optional[int] = None
    content_hash: Optional[str] = None
    policy_version: Optional[str] = None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _resource_context(resource: BusinessResource) -> ResourceContext:
    return ResourceContext(
        workspace_id=resource.workspace_id or "",
        resource_id=resource.id,
        resource_type=resource.resource_type,
        org_unit_id=resource.org_unit_id,
        owner_id=resource.owner_id,
        creator_id=resource.creator_id,
        artifact_version=resource.artifact_version,
        content_hash=resource.content_hash,
        project_id=resource.project_id,
        brand_id=resource.brand_id,
        channel_id=resource.channel_id,
    )


def _audit(
    db: Session,
    *,
    workspace_id: Optional[str],
    actor_id: Optional[str],
    actor_type: str,
    action_key: str,
    decision: str,
    reason: str,
    resource: Optional[BusinessResource] = None,
    metadata: Optional[dict] = None,
) -> None:
    write_audit_event(
        db,
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action_key=action_key,
        decision=decision,
        reason=reason,
        policy_version=settings.policy_version,
        resource_type=resource.resource_type if resource else None,
        resource_id=resource.id if resource else None,
        safe_metadata=metadata,
    )


def _deny(
    db: Session,
    actor: ActorContext,
    code: str,
    *,
    action_key: str,
    status_code: int = 403,
    resource: Optional[BusinessResource] = None,
) -> None:
    _audit(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        actor_type="USER",
        action_key=action_key,
        decision="DENY",
        reason=code,
        resource=resource,
    )
    db.flush()
    raise WorkerServiceError(code, status_code)


def _has_current_approval(db: Session, resource: BusinessResource) -> bool:
    now = datetime.now(timezone.utc)
    policies = db.query(ApprovalPolicy).filter(
        ApprovalPolicy.workspace_id == resource.workspace_id,
        ApprovalPolicy.brand_id.is_(None),
        ApprovalPolicy.campaign_id.is_(None),
        ApprovalPolicy.status == "ACTIVE",
    ).all()
    current = [
        policy for policy in policies
        if _utc(policy.valid_from) <= now
    ]
    if len(current) != 1:
        return False
    return db.query(ApprovalRun).filter(
        ApprovalRun.workspace_id == resource.workspace_id,
        ApprovalRun.artifact_type == resource.resource_type.upper(),
        ApprovalRun.artifact_id == resource.id,
        ApprovalRun.artifact_version == resource.artifact_version,
        ApprovalRun.content_hash == resource.content_hash,
        ApprovalRun.policy_id == current[0].id,
        ApprovalRun.status == "APPROVED",
    ).first() is not None


class WorkerAuthService:
    """Cấp grant hẹp, có hạn dùng và kiểm tra lại đúng tài nguyên/action."""

    @staticmethod
    def issue_grant(
        db: Session,
        actor: ActorContext,
        *,
        job_id: str,
        target_resource: str,
        allowed_actions: list[str],
        expires_at: datetime,
    ) -> DelegatedJobGrant:
        current_actor = load_actor(db, actor.workspace_id, actor.membership_id)
        if current_actor is None or current_actor.user_id != actor.user_id:
            _deny(db, actor, "ACTIVE_MEMBERSHIP_REQUIRED", action_key="delegation.issue", status_code=403)
        actor = current_actor
        worker_subject = settings.worker_jwt_subject
        if not worker_subject or not worker_subject.strip():
            _deny(db, actor, "WORKER_PRINCIPAL_NOT_CONFIGURED", action_key="delegation.issue", status_code=503)
        if not isinstance(job_id, str) or not job_id.strip() or len(job_id) > 100:
            _deny(db, actor, "INVALID_JOB_ID", action_key="delegation.issue", status_code=422)
        if not isinstance(allowed_actions, list) or not 1 <= len(allowed_actions) <= 10:
            _deny(db, actor, "INVALID_WORKER_ACTIONS", action_key="delegation.issue", status_code=422)
        if any(not isinstance(action, str) or not action.strip() for action in allowed_actions):
            _deny(db, actor, "INVALID_WORKER_ACTIONS", action_key="delegation.issue", status_code=422)
        if len(set(allowed_actions)) != len(allowed_actions):
            _deny(db, actor, "INVALID_WORKER_ACTIONS", action_key="delegation.issue", status_code=422)
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            _deny(db, actor, "WORKER_EXPIRY_REQUIRES_TIMEZONE", action_key="delegation.issue", status_code=422)
        now = datetime.now(timezone.utc)
        expiry = _utc(expires_at)
        if expiry <= now or expiry > now + _MAX_GRANT_TTL:
            _deny(db, actor, "WORKER_TTL_OUT_OF_RANGE", action_key="delegation.issue", status_code=422)

        resource = db.query(BusinessResource).filter(
            BusinessResource.id == target_resource,
            BusinessResource.workspace_id == actor.workspace_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if not resource:
            _deny(db, actor, "RESOURCE_NOT_FOUND", action_key="delegation.issue", status_code=404)
        if (
            not resource.content_hash
            or not _HASH_RE.fullmatch(resource.content_hash)
            or resource.artifact_version is None
        ):
            _deny(db, actor, "RESOURCE_TRUST_FIELDS_MISSING", action_key="delegation.issue", status_code=409, resource=resource)

        resource_context = _resource_context(resource)
        if not evaluate_permission(actor, "delegation.issue", resource_context).allowed:
            _deny(db, actor, "WORKER_GRANT_ISSUE_DENIED", action_key="delegation.issue", resource=resource)
        for action_key in allowed_actions:
            if not isinstance(action_key, str) or not registry.is_action_registered(action_key):
                _deny(db, actor, "UNREGISTERED_WORKER_ACTION", action_key="delegation.issue", resource=resource)
            if not evaluate_permission(actor, action_key, resource_context).allowed:
                _deny(db, actor, "WORKER_ACTION_EXCEEDS_CURRENT_PERMISSION", action_key=action_key, resource=resource)
            if action_key in _APPROVAL_REQUIRED_ACTIONS and not _has_current_approval(db, resource):
                _deny(db, actor, "APPROVAL_REQUIRED_FOR_WORKER_ACTION", action_key=action_key, resource=resource)

        normalized_actions = sorted(allowed_actions)
        existing = db.query(DelegatedJobGrant).filter(DelegatedJobGrant.job_id == job_id).first()
        if existing:
            existing_matches = (
                existing.workspace_id == actor.workspace_id
                and existing.initiating_membership_id == actor.membership_id
                and existing.target_resource == resource.id
                and existing.target_artifact_version == resource.artifact_version
                and existing.target_content_hash == resource.content_hash
                and existing.worker_subject == worker_subject
                and existing.policy_version == settings.policy_version
                and json.loads(existing.allowed_actions_json) == normalized_actions
                and _utc(existing.expires_at) == expiry
                and existing.status == "ACTIVE"
            )
            if existing_matches:
                _audit(
                    db, workspace_id=actor.workspace_id, actor_id=actor.user_id,
                    actor_type="USER", action_key="delegation.issue", decision="ALLOW",
                    reason="IDEMPOTENT_WORKER_GRANT_REPLAY", resource=resource,
                    metadata={"job_id_hash": uuid.uuid5(uuid.NAMESPACE_URL, job_id).hex},
                )
                return existing
            _deny(db, actor, "WORKER_JOB_GRANT_CONFLICT", action_key="delegation.issue", status_code=409, resource=resource)

        grant = DelegatedJobGrant(
            id=str(uuid.uuid4()),
            workspace_id=actor.workspace_id,
            job_id=job_id,
            initiating_membership_id=actor.membership_id,
            target_resource=resource.id,
            target_artifact_version=resource.artifact_version,
            target_content_hash=resource.content_hash,
            worker_subject=worker_subject,
            allowed_actions_json=json.dumps(normalized_actions, separators=(",", ":")),
            expires_at=expiry,
            policy_version=settings.policy_version,
            status="ACTIVE",
        )
        db.add(grant)
        _audit(
            db, workspace_id=actor.workspace_id, actor_id=actor.user_id,
            actor_type="USER", action_key="delegation.issue", decision="ALLOW",
            reason="WORKER_GRANT_CREATED", resource=resource,
            metadata={"job_id_hash": uuid.uuid5(uuid.NAMESPACE_URL, job_id).hex, "action_count": len(normalized_actions)},
        )
        db.flush()
        return grant

    @staticmethod
    def recheck_runtime_permission(
        db: Session,
        *,
        job_id: str,
        action_key: str,
        worker_subject: str,
        expected_workspace_id: str,
    ) -> WorkerRecheckResult:
        configured_subject = settings.worker_jwt_subject
        if not isinstance(expected_workspace_id, str) or not expected_workspace_id.strip():
            raise WorkerServiceError("WORKER_WORKSPACE_REQUIRED", 401)
        workspace_id = expected_workspace_id
        grant = db.query(DelegatedJobGrant).filter(
            DelegatedJobGrant.job_id == job_id,
            DelegatedJobGrant.workspace_id == expected_workspace_id,
        ).first()
        resource = None
        if grant:
            resource = db.query(BusinessResource).filter(
                BusinessResource.id == grant.target_resource,
                BusinessResource.workspace_id == expected_workspace_id,
            ).first()

        def deny(reason: str, *, revoke: bool = False) -> WorkerRecheckResult:
            if grant and revoke and grant.status == "ACTIVE":
                grant.status = "EXPIRED" if reason == "WORKER_GRANT_EXPIRED" else "REVOKED"
            _audit(
                db,
                workspace_id=workspace_id,
                actor_id=worker_subject or None,
                actor_type="WORKER",
                action_key=action_key or "worker.recheck",
                decision="DENY",
                reason=reason,
                resource=resource,
                metadata={"job_id_hash": uuid.uuid5(uuid.NAMESPACE_URL, job_id).hex if job_id else None},
            )
            db.flush()
            return WorkerRecheckResult(allowed=False)

        if not configured_subject or not worker_subject or worker_subject != configured_subject:
            return deny("WORKER_PRINCIPAL_DENIED")
        if not grant or grant.status != "ACTIVE":
            return deny("WORKER_GRANT_NOT_ACTIVE")
        if grant.worker_subject != worker_subject:
            return deny("WORKER_GRANT_PRINCIPAL_MISMATCH")
        if not registry.is_action_registered(action_key):
            return deny("UNREGISTERED_WORKER_ACTION")
        if _utc(grant.expires_at) <= datetime.now(timezone.utc):
            return deny("WORKER_GRANT_EXPIRED", revoke=True)
        if grant.policy_version != settings.policy_version:
            return deny("WORKER_POLICY_CHANGED", revoke=True)
        try:
            actions = json.loads(grant.allowed_actions_json)
        except (TypeError, json.JSONDecodeError):
            return deny("WORKER_GRANT_INVALID", revoke=True)
        if not isinstance(actions, list) or any(not isinstance(item, str) for item in actions):
            return deny("WORKER_GRANT_INVALID", revoke=True)
        if action_key not in actions:
            return deny("WORKER_ACTION_NOT_GRANTED")
        if not resource or resource.is_quarantined:
            return deny("WORKER_RESOURCE_NOT_AVAILABLE", revoke=True)
        if (
            resource.artifact_version != grant.target_artifact_version
            or resource.content_hash != grant.target_content_hash
            or not resource.content_hash
            or not _HASH_RE.fullmatch(resource.content_hash)
        ):
            return deny("WORKER_RESOURCE_VERSION_CHANGED", revoke=True)

        actor = load_actor(db, grant.workspace_id, grant.initiating_membership_id)
        if actor is None:
            return deny("WORKER_INITIATOR_INACTIVE", revoke=True)
        if not evaluate_permission(actor, action_key, _resource_context(resource)).allowed:
            return deny("WORKER_INITIATOR_PERMISSION_REVOKED", revoke=True)
        if action_key in _APPROVAL_REQUIRED_ACTIONS and not _has_current_approval(db, resource):
            return deny("WORKER_APPROVAL_REVOKED", revoke=True)

        _audit(
            db,
            workspace_id=grant.workspace_id,
            actor_id=worker_subject,
            actor_type="WORKER",
            action_key=action_key,
            decision="ALLOW",
            reason="WORKER_RUNTIME_REAUTHORIZED",
            resource=resource,
            metadata={"job_id_hash": uuid.uuid5(uuid.NAMESPACE_URL, job_id).hex},
        )
        db.flush()
        return WorkerRecheckResult(
            allowed=True,
            workspace_id=grant.workspace_id,
            target_resource=grant.target_resource,
            resource_type=resource.resource_type,
            artifact_version=grant.target_artifact_version,
            content_hash=grant.target_content_hash,
            policy_version=grant.policy_version,
        )
