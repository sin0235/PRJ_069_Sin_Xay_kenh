# Gói rà soát nhóm 2 — bản sửa phân quyền
Kho không có HEAD hoặc baseline tracked. Đây là ảnh nguồn để rà soát, không giả lập git diff. Đối chiếu với ra_soat_phan_quyen_2026_10_21.md và ke_hoach_sua_phan_quyen_2026_10_21.md.
## src/services/approval_service.py — SHA256 6583EB420D7FCC2348B906C27530BCE176805D8E2B2F591AF2F7AEBBD7F37087
```python
"""Xử lý phê duyệt theo policy, danh tính và tài nguyên đã phân giải phía máy chủ."""

import json
import re
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from baha_auth.src.config import settings
from baha_auth.src.models.entities import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalRun,
    ApprovalStep,
    BusinessResource,
    Membership,
    Role,
)
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.policy.registry import registry
from baha_auth.src.services.danh_tinh_service import load_actor
from baha_auth.src.services.nhat_ky_kiem_toan import write_audit_event


_ARTIFACT_SUBMIT_ACTION = {
    "IDEA": "ideas.submit",
    "SCRIPT": "script.submit",
    "BRIEF": "brief.edit",
    "MEDIA": "media.edit",
}
_ARTIFACT_STAGE_ACTIONS = {
    "IDEA": {"TEAM": "ideas.approve_team", "FINAL": "ideas.approve_final", "CLIENT": "client.review"},
    "SCRIPT": {"TEAM": "script.approve_team", "FINAL": "script.approve_final", "CLIENT": "client.review"},
    "BRIEF": {"TEAM": "brief.approve", "FINAL": "brief.approve", "CLIENT": "client.review"},
    "MEDIA": {"TEAM": "media.approve", "FINAL": "media.approve", "CLIENT": "client.review"},
}
_HASH_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ApprovalServiceError(ValueError):
    """Lỗi từ chối phê duyệt cùng mã HTTP an toàn cho router."""

    def __init__(self, code: str, status_code: int = 403):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    actor: ActorContext,
    *,
    action_key: str,
    decision: str,
    reason: str,
    resource: Optional[BusinessResource] = None,
    policy_version: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    write_audit_event(
        db,
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        actor_type="USER",
        action_key=action_key,
        decision=decision,
        reason=reason,
        policy_version=policy_version or settings.policy_version,
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
    policy_version: Optional[str] = None,
) -> None:
    _audit(
        db,
        actor,
        action_key=action_key,
        decision="DENY",
        reason=code,
        resource=resource,
        policy_version=policy_version,
    )
    db.flush()
    raise ApprovalServiceError(code, status_code)


def _current_policy(db: Session, workspace_id: str) -> ApprovalPolicy:
    now = _now()
    policies = db.query(ApprovalPolicy).filter(
        ApprovalPolicy.workspace_id == workspace_id,
        ApprovalPolicy.brand_id.is_(None),
        ApprovalPolicy.campaign_id.is_(None),
        ApprovalPolicy.status == "ACTIVE",
    ).all()
    effective = [policy for policy in policies if (_utc(policy.valid_from) or now) <= now]
    if len(effective) != 1:
        raise ApprovalServiceError("APPROVAL_POLICY_UNAVAILABLE", 503)
    return effective[0]


def _policy_stages(db: Session, policy: ApprovalPolicy, workspace_id: str) -> list[dict[str, str]]:
    try:
        raw_stages = json.loads(policy.stages_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503) from exc
    if not isinstance(raw_stages, list) or not 1 <= len(raw_stages) <= 8:
        raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)

    stages: list[dict[str, str]] = []
    for raw in raw_stages:
        if not isinstance(raw, dict):
            raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
        if set(raw) - {"stage_key", "allowed_role", "assigned_membership_id", "action_key"}:
            raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
        stage_key = raw.get("stage_key")
        role_code = raw.get("allowed_role")
        assignee = raw.get("assigned_membership_id")
        action_key = raw.get("action_key")
        if action_key is not None and not isinstance(action_key, str):
            raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
        if not isinstance(stage_key, str) or not stage_key.strip() or len(stage_key) > 50:
            raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
        if bool(role_code) == bool(assignee):
            raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
        if role_code is not None:
            if not isinstance(role_code, str) or len(role_code) > 100:
                raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
            role = db.query(Role).filter(
                Role.code == role_code,
                Role.status == "ACTIVE",
                (Role.workspace_id.is_(None)) | (Role.workspace_id == workspace_id),
            ).first()
            if not role:
                raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
            stages.append({"stage_key": stage_key, "assignee": role_code, "kind": "role", "action_key": action_key or ""})
        else:
            if not isinstance(assignee, str) or len(assignee) > 100:
                raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
            membership = db.query(Membership).filter(
                Membership.id == assignee,
                Membership.workspace_id == workspace_id,
                Membership.status == "ACTIVE",
            ).first()
            if not membership:
                raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
            stages.append({"stage_key": stage_key, "assignee": assignee, "kind": "membership", "action_key": action_key or ""})

    return stages


def _stage_action(artifact_type: str, stage_key: str, configured_action: str = "") -> str:
    artifact_actions = _ARTIFACT_STAGE_ACTIONS.get(artifact_type)
    if not artifact_actions:
        raise ApprovalServiceError("UNSUPPORTED_APPROVAL_ARTIFACT", 422)
    stage_name = stage_key.upper()
    stage_kind = "TEAM" if "TEAM" in stage_name else (
        "CLIENT" if "CLIENT" in stage_name else "FINAL" if "FINAL" in stage_name else None
    )
    if stage_kind is None and artifact_type in {"BRIEF", "MEDIA"}:
        stage_kind = "FINAL"
    if stage_kind is None:
        raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
    expected = artifact_actions[stage_kind]
    if configured_action and configured_action != expected:
        raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
    if not registry.is_action_registered(expected):
        raise ApprovalServiceError("APPROVAL_POLICY_INVALID", 503)
    return expected


def _resolve_resource(
    db: Session, actor: ActorContext, artifact_type: str, artifact_id: str
) -> Optional[BusinessResource]:
    resource = db.query(BusinessResource).filter(
        BusinessResource.id == artifact_id,
        BusinessResource.workspace_id == actor.workspace_id,
        BusinessResource.is_quarantined.is_(False),
    ).first()
    if not resource or (resource.resource_type or "").upper() != artifact_type:
        return None
    return resource


def _validate_resource(resource: BusinessResource) -> bool:
    return (
        bool(resource.workspace_id)
        and resource.artifact_version is not None
        and isinstance(resource.content_hash, str)
        and bool(_HASH_RE.fullmatch(resource.content_hash))
        and bool(resource.creator_id or resource.owner_id)
    )


def _authorize_stage(
    actor: ActorContext,
    resource: BusinessResource,
    stage: dict[str, str],
    action_key: str,
) -> bool:
    if stage["kind"] == "membership" and stage["assignee"] != actor.membership_id:
        return False
    scoped_actor = actor
    if stage["kind"] == "role":
        matching_roles = [role for role in actor.roles if role.get("role_code") == stage["assignee"]]
        if not matching_roles:
            return False
        scoped_actor = replace(actor, roles=matching_roles)
    return evaluate_permission(scoped_actor, action_key, _resource_context(resource)).allowed


def _same_decision(
    decision: Optional[ApprovalDecision], actor: ActorContext, result: str,
    artifact_version: int, content_hash: str, reason: Optional[str],
) -> bool:
    return bool(
        decision
        and decision.reviewer_membership_id == actor.membership_id
        and decision.result == result
        and decision.artifact_version == artifact_version
        and decision.content_hash == content_hash
        and decision.reason == reason
    )


class ApprovalService:
    """Chọn policy phía máy chủ và chuyển trạng thái nguyên tử theo chặng."""

    @staticmethod
    def start_approval_run(
        db: Session,
        actor: ActorContext,
        *,
        artifact_type: str,
        artifact_id: str,
        expected_version: int,
    ) -> ApprovalRun:
        current_actor = load_actor(db, actor.workspace_id, actor.membership_id)
        if current_actor is None or current_actor.user_id != actor.user_id:
            _deny(db, actor, "ACTIVE_MEMBERSHIP_REQUIRED", action_key="approval.run.create", status_code=403)
        actor = current_actor
        artifact_type = artifact_type.upper()
        action_key = _ARTIFACT_SUBMIT_ACTION.get(artifact_type, "approval.run.create")
        resource = _resolve_resource(db, actor, artifact_type, artifact_id)
        if not resource:
            _deny(db, actor, "RESOURCE_NOT_FOUND", action_key=action_key, status_code=404)
        if not _validate_resource(resource):
            _deny(db, actor, "RESOURCE_TRUST_FIELDS_MISSING", action_key=action_key, status_code=409, resource=resource)
        if resource.artifact_version != expected_version:
            _deny(db, actor, "STALE_ARTIFACT_VERSION", action_key=action_key, status_code=412, resource=resource)
        if artifact_type not in _ARTIFACT_SUBMIT_ACTION:
            _deny(db, actor, "UNSUPPORTED_APPROVAL_ARTIFACT", action_key=action_key, status_code=422, resource=resource)
        if not evaluate_permission(actor, action_key, _resource_context(resource)).allowed:
            _deny(db, actor, "APPROVAL_SUBMISSION_DENIED", action_key=action_key, resource=resource)

        try:
            policy = _current_policy(db, actor.workspace_id)
            stages = _policy_stages(db, policy, actor.workspace_id)
            for stage in stages:
                _stage_action(artifact_type, stage["stage_key"], stage["action_key"])
        except ApprovalServiceError as exc:
            _deny(
                db, actor, exc.code, action_key=action_key,
                status_code=exc.status_code, resource=resource,
            )

        existing = db.query(ApprovalRun).filter(
            ApprovalRun.workspace_id == actor.workspace_id,
            ApprovalRun.artifact_type == artifact_type,
            ApprovalRun.artifact_id == resource.id,
            ApprovalRun.artifact_version == resource.artifact_version,
            ApprovalRun.policy_id == policy.id,
        ).options(joinedload(ApprovalRun.steps)).first()
        if existing:
            if existing.created_by == actor.membership_id and existing.content_hash == resource.content_hash:
                _audit(
                    db, actor, action_key=action_key, decision="ALLOW",
                    reason="IDEMPOTENT_APPROVAL_RUN_REPLAY", resource=resource,
                    policy_version=str(policy.version), metadata={"run_id": existing.id},
                )
                return existing
            _deny(db, actor, "APPROVAL_RUN_ALREADY_EXISTS", action_key=action_key, status_code=409, resource=resource)

        run = ApprovalRun(
            id=str(uuid.uuid4()),
            workspace_id=actor.workspace_id,
            artifact_type=artifact_type,
            artifact_id=resource.id,
            artifact_version=resource.artifact_version,
            content_hash=resource.content_hash,
            policy_id=policy.id,
            status="PENDING",
            created_by=actor.membership_id,
        )
        db.add(run)
        db.flush()
        for ordinal, stage in enumerate(stages, start=1):
            db.add(ApprovalStep(
                id=str(uuid.uuid4()),
                workspace_id=actor.workspace_id,
                run_id=run.id,
                stage_key=stage["stage_key"],
                allowed_role_or_assignee=stage["assignee"],
                status="PENDING",
                ordinal=ordinal,
            ))
        _audit(
            db, actor, action_key=action_key, decision="ALLOW",
            reason="APPROVAL_RUN_CREATED", resource=resource,
            policy_version=str(policy.version), metadata={"run_id": run.id},
        )
        db.flush()
        return run

    @staticmethod
    def record_decision(
        db: Session,
        actor: ActorContext,
        *,
        step_id: str,
        result: str,
        artifact_version: int,
        content_hash: str,
        reason: Optional[str] = None,
    ) -> ApprovalDecision:
        current_actor = load_actor(db, actor.workspace_id, actor.membership_id)
        if current_actor is None or current_actor.user_id != actor.user_id:
            _deny(db, actor, "ACTIVE_MEMBERSHIP_REQUIRED", action_key="approval.step.decide", status_code=403)
        actor = current_actor
        if result not in {"APPROVED", "REJECTED", "CHANGES_REQUESTED"}:
            _deny(db, actor, "INVALID_APPROVAL_RESULT", action_key="approval.step.decide", status_code=422)
        step = db.query(ApprovalStep).filter(
            ApprovalStep.id == step_id,
            ApprovalStep.workspace_id == actor.workspace_id,
        ).options(joinedload(ApprovalStep.run)).first()
        if not step or not step.run:
            _deny(db, actor, "APPROVAL_STEP_NOT_FOUND", action_key="approval.step.decide", status_code=404)
        run = step.run
        resource = _resolve_resource(db, actor, run.artifact_type, run.artifact_id)
        if not resource:
            _deny(db, actor, "RESOURCE_NOT_FOUND", action_key="approval.step.decide", status_code=404)
        try:
            policy = _current_policy(db, actor.workspace_id)
            stages = _policy_stages(db, policy, actor.workspace_id)
        except ApprovalServiceError as exc:
            _deny(
                db, actor, exc.code, action_key="approval.step.decide",
                status_code=exc.status_code, resource=resource,
            )
        if policy.id != run.policy_id:
            _deny(db, actor, "APPROVAL_POLICY_CHANGED", action_key="approval.step.decide", status_code=409, resource=resource, policy_version=str(policy.version))
        if not _validate_resource(resource) or (
            resource.artifact_version != run.artifact_version
            or resource.content_hash != run.content_hash
            or artifact_version != resource.artifact_version
            or content_hash != resource.content_hash
        ):
            _deny(db, actor, "STALE_ARTIFACT_VERSION", action_key="approval.step.decide", status_code=412, resource=resource, policy_version=str(policy.version))
        if actor.membership_id == run.created_by or actor.user_id == (resource.creator_id or resource.owner_id):
            _deny(db, actor, "SELF_APPROVAL_DENIED", action_key="approval.step.decide", resource=resource, policy_version=str(policy.version))

        ordered_steps = db.query(ApprovalStep).filter(
            ApprovalStep.workspace_id == actor.workspace_id,
            ApprovalStep.run_id == run.id,
        ).order_by(ApprovalStep.ordinal.asc()).all()
        if len(ordered_steps) != len(stages) or any(
            stored.stage_key != configured["stage_key"]
            or stored.allowed_role_or_assignee != configured["assignee"]
            for stored, configured in zip(ordered_steps, stages)
        ):
            _deny(db, actor, "APPROVAL_POLICY_CHANGED", action_key="approval.step.decide", status_code=409, resource=resource, policy_version=str(policy.version))
        stage = stages[step.ordinal - 1] if 1 <= step.ordinal <= len(stages) else None
        if not stage:
            _deny(db, actor, "APPROVAL_POLICY_INVALID", action_key="approval.step.decide", status_code=503, resource=resource, policy_version=str(policy.version))
        try:
            action_key = _stage_action(run.artifact_type, stage["stage_key"], stage["action_key"])
        except ApprovalServiceError as exc:
            _deny(db, actor, exc.code, action_key="approval.step.decide", status_code=exc.status_code, resource=resource, policy_version=str(policy.version))
        if stage["assignee"] != step.allowed_role_or_assignee or not _authorize_stage(actor, resource, stage, action_key):
            _deny(db, actor, "APPROVAL_STAGE_PERMISSION_DENIED", action_key=action_key, resource=resource, policy_version=str(policy.version))

        existing = db.query(ApprovalDecision).filter(ApprovalDecision.step_id == step.id).first()
        if existing:
            if _same_decision(existing, actor, result, artifact_version, content_hash, reason):
                _audit(
                    db, actor, action_key=action_key, decision="ALLOW",
                    reason="IDEMPOTENT_APPROVAL_DECISION_REPLAY", resource=resource,
                    policy_version=str(policy.version), metadata={"run_id": run.id, "step_id": step.id},
                )
                return existing
            _deny(db, actor, "APPROVAL_STEP_ALREADY_DECIDED", action_key=action_key, status_code=409, resource=resource, policy_version=str(policy.version))

        if run.status != "PENDING" or step.status != "PENDING":
            _deny(db, actor, "APPROVAL_STEP_ALREADY_DECIDED", action_key=action_key, status_code=409, resource=resource, policy_version=str(policy.version))
        current_step = next((candidate for candidate in ordered_steps if candidate.status == "PENDING"), None)
        if not current_step or current_step.id != step.id:
            _deny(db, actor, "APPROVAL_STAGE_ORDER_DENIED", action_key="approval.step.decide", status_code=409, resource=resource, policy_version=str(policy.version))

        next_step_status = "APPROVED" if result == "APPROVED" else "REJECTED"
        changed = db.query(ApprovalStep).filter(
            ApprovalStep.id == step.id,
            ApprovalStep.workspace_id == actor.workspace_id,
            ApprovalStep.run_id == run.id,
            ApprovalStep.status == "PENDING",
        ).update({ApprovalStep.status: next_step_status}, synchronize_session=False)
        if changed != 1:
            db.expire_all()
            current = db.query(ApprovalDecision).filter(ApprovalDecision.step_id == step.id).first()
            if _same_decision(current, actor, result, artifact_version, content_hash, reason):
                return current
            _deny(db, actor, "APPROVAL_STEP_ALREADY_DECIDED", action_key=action_key, status_code=409, resource=resource, policy_version=str(policy.version))

        decision = ApprovalDecision(
            id=str(uuid.uuid4()),
            workspace_id=actor.workspace_id,
            step_id=step.id,
            reviewer_membership_id=actor.membership_id,
            result=result,
            reason=reason,
            artifact_version=resource.artifact_version,
            content_hash=resource.content_hash,
            decided_at=_now(),
        )
        db.add(decision)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            current = db.query(ApprovalDecision).filter(ApprovalDecision.step_id == step.id).first()
            if _same_decision(current, actor, result, artifact_version, content_hash, reason):
                return current
            _audit(
                db, actor, action_key=action_key, decision="DENY",
                reason="APPROVAL_STEP_ALREADY_DECIDED", resource=resource,
                policy_version=str(policy.version),
            )
            db.flush()
            raise ApprovalServiceError("APPROVAL_STEP_ALREADY_DECIDED", 409)

        if result == "APPROVED":
            pending_count = db.query(ApprovalStep).filter(
                ApprovalStep.workspace_id == actor.workspace_id,
                ApprovalStep.run_id == run.id,
                ApprovalStep.status == "PENDING",
            ).count()
            if pending_count == 0:
                changed_run = db.query(ApprovalRun).filter(
                    ApprovalRun.id == run.id,
                    ApprovalRun.workspace_id == actor.workspace_id,
                    ApprovalRun.status == "PENDING",
                ).update({ApprovalRun.status: "APPROVED"}, synchronize_session=False)
                if changed_run != 1:
                    _deny(db, actor, "APPROVAL_RUN_STATE_CONFLICT", action_key=action_key, status_code=409, resource=resource, policy_version=str(policy.version))
        else:
            new_status = "REWORK" if result == "CHANGES_REQUESTED" else "REJECTED"
            changed_run = db.query(ApprovalRun).filter(
                ApprovalRun.id == run.id,
                ApprovalRun.workspace_id == actor.workspace_id,
                ApprovalRun.status == "PENDING",
            ).update({ApprovalRun.status: new_status}, synchronize_session=False)
            if changed_run != 1:
                _deny(db, actor, "APPROVAL_RUN_STATE_CONFLICT", action_key=action_key, status_code=409, resource=resource, policy_version=str(policy.version))

        _audit(
            db, actor, action_key=action_key, decision="ALLOW",
            reason="APPROVAL_DECISION_RECORDED", resource=resource,
            policy_version=str(policy.version), metadata={"run_id": run.id, "step_id": step.id, "result": result},
        )
        db.flush()
        db.refresh(decision)
        return decision

    @staticmethod
    def list_review_inbox(db: Session, actor: ActorContext) -> list[ApprovalRun]:
        current_actor = load_actor(db, actor.workspace_id, actor.membership_id)
        if current_actor is None or current_actor.user_id != actor.user_id:
            return []
        actor = current_actor
        try:
            policy = _current_policy(db, actor.workspace_id)
            stages = _policy_stages(db, policy, actor.workspace_id)
        except ApprovalServiceError:
            return []
        runs = db.query(ApprovalRun).filter(
            ApprovalRun.workspace_id == actor.workspace_id,
            ApprovalRun.status == "PENDING",
            ApprovalRun.policy_id == policy.id,
        ).options(joinedload(ApprovalRun.steps)).order_by(ApprovalRun.created_at.asc()).all()
        authorized = []
        for run in runs:
            if run.artifact_type not in _ARTIFACT_STAGE_ACTIONS:
                continue
            resource = _resolve_resource(db, actor, run.artifact_type, run.artifact_id)
            if not resource or not _validate_resource(resource):
                continue
            if (resource.artifact_version, resource.content_hash) != (run.artifact_version, run.content_hash):
                continue
            ordered_steps = sorted(run.steps, key=lambda item: item.ordinal)
            current = next((item for item in ordered_steps if item.status == "PENDING"), None)
            if current is None or current.ordinal < 1 or current.ordinal > len(stages):
                continue
            stage = stages[current.ordinal - 1]
            if current.stage_key != stage["stage_key"] or current.allowed_role_or_assignee != stage["assignee"]:
                continue
            try:
                action_key = _stage_action(run.artifact_type, stage["stage_key"], stage["action_key"])
            except ApprovalServiceError:
                continue
            if _authorize_stage(actor, resource, stage, action_key):
                authorized.append(run)
        return authorized

```
## src/services/worker_service.py — SHA256 3327D3CB26878EB8866B657A5A0610BA4E8674F3B27D2D4D9491268A11D1E017
```python
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
    ) -> WorkerRecheckResult:
        configured_subject = settings.worker_jwt_subject
        grant = db.query(DelegatedJobGrant).filter(DelegatedJobGrant.job_id == job_id).first()
        resource = None
        workspace_id = grant.workspace_id if grant else None
        if grant:
            resource = db.query(BusinessResource).filter(
                BusinessResource.id == grant.target_resource,
                BusinessResource.workspace_id == grant.workspace_id,
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

```
## src/api/approval_router.py — SHA256 9CC946C6D2E7609160533DE1A36FEAC8F6F6C1CA251CAF860CB7C2821E52CDA6
```python
"""API phê duyệt; actor và tài nguyên luôn được phân giải phía máy chủ."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from baha_auth.src.api.deps import ActorContext, get_current_actor
from baha_auth.src.database import get_db
from baha_auth.src.models.entities import ApprovalRun
from baha_auth.src.schemas.contracts import (
    ApprovalDecisionRequest,
    ApprovalRunCreate,
    ApprovalRunOut,
    ApprovalStepOut,
)
from baha_auth.src.services.approval_service import ApprovalService, ApprovalServiceError


router = APIRouter(prefix="/authz/v1/approvals", tags=["Phê duyệt"])


def _run_output(run: ApprovalRun) -> ApprovalRunOut:
    steps = sorted(run.steps, key=lambda item: item.ordinal)
    return ApprovalRunOut(
        id=run.id,
        workspace_id=run.workspace_id,
        artifact_type=run.artifact_type,
        artifact_id=run.artifact_id,
        artifact_version=run.artifact_version,
        content_hash=run.content_hash,
        status=run.status,
        created_by=run.created_by,
        created_at=run.created_at,
        steps=[
            ApprovalStepOut(
                id=step.id,
                stage_key=step.stage_key,
                allowed_role_or_assignee=step.allowed_role_or_assignee,
                status=step.status,
                ordinal=step.ordinal,
            )
            for step in steps
        ],
    )


def _raise_service_error(db: Session, error: ApprovalServiceError) -> None:
    # Các từ chối đã được ghi audit trong cùng session; commit riêng sự kiện đó.
    db.commit()
    raise HTTPException(
        status_code=error.status_code,
        detail={"error_code": error.code},
    )


@router.post("/runs", response_model=ApprovalRunOut, status_code=status.HTTP_201_CREATED)
def create_approval_run(
    payload: ApprovalRunCreate,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    try:
        run = ApprovalService.start_approval_run(
            db,
            actor,
            artifact_type=payload.artifact_type,
            artifact_id=payload.artifact_id,
            expected_version=payload.expected_version,
        )
        db.commit()
        db.refresh(run)
        return _run_output(run)
    except ApprovalServiceError as exc:
        _raise_service_error(db, exc)
    except Exception:
        db.rollback()
        raise


@router.get("/inbox", response_model=List[ApprovalRunOut])
def list_review_inbox(
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    runs = ApprovalService.list_review_inbox(db, actor)
    return [_run_output(run) for run in runs]


@router.post("/decisions", response_model=dict)
def submit_decision(
    payload: ApprovalDecisionRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    try:
        decision = ApprovalService.record_decision(
            db,
            actor,
            step_id=payload.step_id,
            result=payload.result,
            artifact_version=payload.artifact_version,
            content_hash=payload.content_hash,
            reason=payload.reason,
        )
        db.commit()
        return {
            "status": "success",
            "decision_id": decision.id,
            "result": decision.result,
            "decided_at": decision.decided_at.isoformat(),
        }
    except ApprovalServiceError as exc:
        _raise_service_error(db, exc)
    except Exception:
        db.rollback()
        raise

```
## src/api/worker_router.py — SHA256 95FF69729BCFC3A6F8D7B6AA1E33E7266E8E77392FF61181409A83B5B66B8EF8
```python
"""API grant/recheck worker có xác thực service principal và grant hẹp."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from baha_auth.src.api.deps import ActorContext, get_current_actor
from baha_auth.src.config import settings
from baha_auth.src.database import get_db
from baha_auth.src.models.entities import BusinessResource
from baha_auth.src.schemas.contracts import (
    DelegatedJobGrantOut,
    DelegatedJobGrantRequest,
    WorkerRecheckRequest,
    WorkerRecheckResponse,
)
from baha_auth.src.services.worker_service import WorkerAuthService, WorkerServiceError
from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, verify_bearer_token


router = APIRouter(prefix="/authz/v1/workers", tags=["Worker"])
_bearer = HTTPBearer(auto_error=False)


def _verified_worker_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    required = (
        settings.jwt_secret_key,
        settings.jwt_issuer,
        settings.worker_jwt_audience,
        settings.worker_jwt_subject,
    )
    if any(not value or not value.strip() for value in required):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "WORKER_AUTH_NOT_CONFIGURED"},
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "WORKER_BEARER_REQUIRED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        identity = verify_bearer_token(
            credentials.credentials,
            secret=settings.jwt_secret_key,
            issuer=settings.jwt_issuer,
            audience=settings.worker_jwt_audience,
        )
    except InvalidBearerToken:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_WORKER_BEARER"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if identity.subject != settings.worker_jwt_subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "WORKER_SUBJECT_DENIED"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return identity.subject


def _raise_service_error(db: Session, error: WorkerServiceError) -> None:
    db.commit()
    raise HTTPException(status_code=error.status_code, detail={"error_code": error.code})


@router.post("/grants", response_model=DelegatedJobGrantOut, status_code=status.HTTP_201_CREATED)
def issue_worker_grant(
    payload: DelegatedJobGrantRequest,
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
):
    try:
        grant = WorkerAuthService.issue_grant(
            db,
            actor,
            job_id=payload.job_id,
            target_resource=payload.target_resource,
            allowed_actions=payload.allowed_actions,
            expires_at=payload.expires_at,
        )
        resource = db.query(BusinessResource).filter(
            BusinessResource.id == grant.target_resource,
            BusinessResource.workspace_id == grant.workspace_id,
            BusinessResource.is_quarantined.is_(False),
        ).first()
        if (
            resource is None
            or resource.artifact_version != grant.target_artifact_version
            or resource.content_hash != grant.target_content_hash
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_code": "WORKER_RESOURCE_NOT_AVAILABLE"})
        db.commit()
        db.refresh(grant)
        return DelegatedJobGrantOut(
            id=grant.id,
            workspace_id=grant.workspace_id,
            job_id=grant.job_id,
            initiating_membership_id=grant.initiating_membership_id,
            target_resource=grant.target_resource,
            resource_type=resource.resource_type,
            artifact_version=grant.target_artifact_version,
            content_hash=grant.target_content_hash,
            policy_version=grant.policy_version,
            allowed_actions=json.loads(grant.allowed_actions_json),
            expires_at=grant.expires_at,
            status=grant.status,
        )
    except WorkerServiceError as exc:
        _raise_service_error(db, exc)
    except Exception:
        db.rollback()
        raise


@router.post("/recheck", response_model=WorkerRecheckResponse)
def recheck_worker_runtime(
    payload: WorkerRecheckRequest,
    worker_subject: str = Depends(_verified_worker_subject),
    db: Session = Depends(get_db),
):
    try:
        result = WorkerAuthService.recheck_runtime_permission(
            db,
            job_id=payload.job_id,
            action_key=payload.action_key,
            worker_subject=worker_subject,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return WorkerRecheckResponse(
        allowed=result.allowed,
        job_id=payload.job_id,
        action_key=payload.action_key,
        status="AUTHORIZED" if result.allowed else "DENIED",
        reason=(
            "Đã xác minh lại quyền thực thi."
            if result.allowed
            else "Grant không còn hợp lệ hoặc quyền hiện tại không cho phép."
        ),
        workspace_id=result.workspace_id,
        target_resource=result.target_resource,
        resource_type=result.resource_type,
        artifact_version=result.artifact_version,
        content_hash=result.content_hash,
        policy_version=result.policy_version,
    )

```
## src/schemas/contracts.py — SHA256 A42C3ECCC52D8A79E1374F67B62E92F317F57504E596AAB042DAD81AD7B1730E
```python
# Hợp đồng DTO và schema Pydantic V2 cho phân quyền doanh nghiệp Baha Group.
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

# --- Nền tảng và trường chung ---
class ErrorPayload(BaseModel):
    error_code: str
    message: str
    correlation_id: Optional[str] = None
    policy_version: str = "1.0.0"


class StrictRequest(BaseModel):
    """Từ chối trường lạ để ngăn gửi thừa dữ liệu đặc quyền."""

    model_config = ConfigDict(extra="forbid")

# --- Không gian làm việc và thành viên ---
class WorkspaceCreate(StrictRequest):
    name: StrictStr
    slug: StrictStr
    type: Literal["ENTERPRISE", "AGENCY", "SUBSIDIARY"] = "ENTERPRISE"

class WorkspaceOut(BaseModel):
    id: str
    name: str
    slug: str
    type: str
    status: str
    created_at: datetime

class MemberInviteRequest(StrictRequest):
    email: StrictStr
    full_name: StrictStr
    initial_role_code: StrictStr = "GUEST"
    scope_type: Literal["WORKSPACE", "DEPARTMENT", "TEAM", "PROJECT", "OWN"] = "WORKSPACE"
    scope_id: Optional[StrictStr] = None

class MemberOut(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    email: str
    full_name: Optional[str] = None
    status: str
    joined_at: datetime
    roles: List[str] = []

# --- Cơ cấu tổ chức ---
class OrgUnitCreate(StrictRequest):
    name: StrictStr
    type: Literal["COMPANY", "DEPARTMENT", "TEAM"] = "DEPARTMENT"
    parent_id: Optional[StrictStr] = None

class OrgUnitOut(BaseModel):
    id: str
    workspace_id: str
    parent_id: Optional[str] = None
    type: str
    name: str
    status: str
    created_at: datetime

class ReportingLineCreate(StrictRequest):
    manager_membership_id: StrictStr
    report_membership_id: StrictStr
    org_unit_id: Optional[StrictStr] = None

class ReportingLineOut(BaseModel):
    id: str
    workspace_id: str
    manager_membership_id: str
    report_membership_id: str
    org_unit_id: Optional[str] = None
    valid_from: datetime
    valid_until: Optional[datetime] = None

# --- Vai trò và quyền ---
class RoleOut(BaseModel):
    id: str
    code: str
    name: str
    is_template: bool
    is_custom: bool
    status: str

class PermissionOut(BaseModel):
    id: str
    action_key: str
    risk_tier: str
    is_immutable: bool
    description: Optional[str] = None

class RoleAssignmentRequest(StrictRequest):
    grantee_membership_id: StrictStr
    role_code: StrictStr
    scope_type: Literal["WORKSPACE", "DEPARTMENT", "TEAM", "PROJECT", "OWN"] = "WORKSPACE"
    scope_id: Optional[StrictStr] = None
    valid_until: Optional[datetime] = None
    reason: Optional[StrictStr] = None

    @field_validator("valid_until")
    @classmethod
    def valid_until_must_have_timezone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Thời hạn phải có múi giờ rõ ràng.")
        return value

class RoleAssignmentOut(BaseModel):
    id: str
    workspace_id: str
    membership_id: str
    role_code: str
    scope_type: str
    scope_id: Optional[str] = None
    valid_from: datetime
    valid_until: Optional[datetime] = None
    status: str

class DelegationRequest(StrictRequest):
    grantee_membership_id: StrictStr
    allowed_actions: List[StrictStr] = Field(min_length=1, max_length=10)
    expires_at: datetime
    reason: Optional[StrictStr] = None

    @field_validator("expires_at")
    @classmethod
    def expires_at_must_have_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời hạn phải có múi giờ rõ ràng.")
        return value

class DelegationOut(BaseModel):
    id: str
    workspace_id: str
    grantor_membership_id: str
    grantee_membership_id: str
    allowed_actions: List[str]
    starts_at: datetime
    expires_at: datetime
    status: str

# --- Đánh giá chính sách ---
class EvaluateRequest(StrictRequest):
    action_key: StrictStr
    resource_id: Optional[StrictStr] = None

class EvaluateResponse(BaseModel):
    allowed: bool
    decision: str  # "ALLOW" | "DENY".
    reason_code: str
    internal_reason: str
    policy_version: str

# --- Phê duyệt nhiều cấp ---
class ApprovalRunCreate(StrictRequest):
    artifact_type: StrictStr
    artifact_id: StrictStr
    expected_version: StrictInt = Field(gt=0)


class ApprovalDecisionRequest(StrictRequest):
    step_id: StrictStr
    result: Literal["APPROVED", "REJECTED", "CHANGES_REQUESTED"]
    artifact_version: StrictInt = Field(gt=0)
    content_hash: StrictStr = Field(min_length=64, max_length=64)
    reason: Optional[StrictStr] = Field(default=None, max_length=2000)

class ApprovalStepOut(BaseModel):
    id: str
    stage_key: str
    allowed_role_or_assignee: str
    status: str
    ordinal: int

class ApprovalRunOut(BaseModel):
    id: str
    workspace_id: str
    artifact_type: str
    artifact_id: str
    artifact_version: int
    content_hash: str
    status: str
    created_by: str
    created_at: datetime
    steps: List[ApprovalStepOut] = []

# --- Grant tác vụ worker ---
class DelegatedJobGrantRequest(StrictRequest):
    job_id: StrictStr = Field(min_length=1, max_length=100)
    target_resource: StrictStr = Field(min_length=1, max_length=255)
    allowed_actions: List[StrictStr] = Field(min_length=1, max_length=10)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def expires_at_must_have_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời hạn phải có múi giờ rõ ràng.")
        return value

class DelegatedJobGrantOut(BaseModel):
    id: str
    workspace_id: str
    job_id: str
    initiating_membership_id: str
    target_resource: str
    resource_type: str
    artifact_version: int
    content_hash: str
    policy_version: str
    allowed_actions: List[str]
    expires_at: datetime
    status: str

class WorkerRecheckRequest(StrictRequest):
    job_id: StrictStr = Field(min_length=1, max_length=100)
    action_key: StrictStr = Field(min_length=1, max_length=100)

class WorkerRecheckResponse(BaseModel):
    allowed: bool
    job_id: str
    action_key: str
    status: str
    reason: str
    workspace_id: Optional[StrictStr] = None
    target_resource: Optional[StrictStr] = None
    resource_type: Optional[StrictStr] = None
    artifact_version: Optional[StrictInt] = None
    content_hash: Optional[StrictStr] = None
    policy_version: Optional[StrictStr] = None

# --- Sự kiện kiểm toán ---
class AuditEventOut(BaseModel):
    id: str
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_type: str
    action_key: str
    resource_type: Optional[str] = None
    decision: str
    internal_reason: str
    policy_version: str
    timestamp: datetime

```
## tests/test_kiem_thu_duyet_tac_vu_nen.py — SHA256 DB667E764E9B5E56B0CA742C403BA41E29CC413C8454A1E450C720C666172AD0
```python
"""Kiểm thử cô lập cho phân quyền duyệt và worker, chỉ dùng SQLite trong RAM."""

import base64
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BAHA_AUTH_ROOT = Path(__file__).resolve().parents[2]
if str(BAHA_AUTH_ROOT) not in sys.path:
    sys.path.insert(0, str(BAHA_AUTH_ROOT))

from baha_auth.src.config import settings
from baha_auth.src.database import Base, get_db
from baha_auth.src.models.entities import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalRun,
    AuthorizationAuditEvent,
    BusinessResource,
    DelegatedJobGrant,
    GlobalUser,
    Membership,
    OrgAssignment,
    OrgUnit,
    Role,
    RoleAssignment,
    Workspace,
)
from baha_auth.src.services.approval_service import ApprovalService
from baha_auth.src.services.danh_tinh_service import load_actor
from baha_auth.src.services.worker_service import WorkerAuthService
from baha_auth.src.api.worker_router import router as worker_router


@pytest.fixture
def du_lieu_rbac():
    """Tạo toàn bộ dữ liệu kiểm thử bằng một engine SQLite riêng trong RAM."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = session_factory()

    workspace = Workspace(id="ws-test", name="Không gian thử", slug="ws-test")
    users = [
        GlobalUser(id=f"user-{name}", email=f"{name}@example.invalid", status="ACTIVE")
        for name in ("author", "reviewer", "lead", "worker_author", "project")
    ]
    memberships = [
        Membership(
            id=f"member-{user.id.removeprefix('user-')}",
            workspace_id=workspace.id,
            user_id=user.id,
            status="ACTIVE",
        )
        for user in users
    ]
    role_owner = Role(
        id="role-owner", workspace_id=workspace.id, code="WORKSPACE_OWNER",
        name="Chủ không gian", status="ACTIVE",
    )
    role_lead = Role(
        id="role-lead", workspace_id=workspace.id, code="TEAM_LEAD",
        name="Trưởng nhóm", status="ACTIVE",
    )
    role_researcher = Role(
        id="role-researcher", workspace_id=workspace.id, code="RESEARCHER",
        name="Nghiên cứu viên", status="ACTIVE",
    )
    role_strategist = Role(
        id="role-strategist", workspace_id=workspace.id, code="STRATEGIST",
        name="Chiến lược gia", status="ACTIVE",
    )
    team = OrgUnit(
        id="team-test", workspace_id=workspace.id, type="TEAM",
        name="Nhóm thử", status="ACTIVE",
    )
    db.add_all([workspace, *users, *memberships, role_owner, role_lead, role_researcher, role_strategist, team])
    db.flush()
    for membership in memberships:
        role = role_lead if membership.id == "member-lead" else (
            role_researcher if membership.id == "member-worker_author" else (
                role_strategist if membership.id == "member-project" else role_owner
            )
        )
        is_team_lead = membership.id == "member-lead"
        is_project_actor = membership.id == "member-project"
        db.add(RoleAssignment(
            workspace_id=workspace.id,
            membership_id=membership.id,
            role_id=role.id,
            scope_type="TEAM" if is_team_lead else "PROJECT" if is_project_actor else "WORKSPACE",
            scope_id=team.id if is_team_lead else "project-a" if is_project_actor else None,
            status="ACTIVE",
            valid_from=datetime.now(timezone.utc) - timedelta(minutes=1),
        ))
        if is_team_lead:
            db.add(OrgAssignment(
                workspace_id=workspace.id,
                membership_id=membership.id,
                org_unit_id=team.id,
            ))

    resource = BusinessResource(
        id="idea-test",
        workspace_id=workspace.id,
        org_unit_id=team.id,
        owner_id="user-author",
        creator_id="user-author",
        artifact_version=1,
        project_id="project-a",
        resource_type="IDEA",
        title="Ý tưởng thử nghiệm",
        content_hash="a" * 64,
        is_quarantined=False,
    )
    policy = ApprovalPolicy(
        id="policy-current",
        workspace_id=workspace.id,
        version=7,
        stages_json=json.dumps([
            {"stage_key": "TEAM_REVIEW", "allowed_role": "TEAM_LEAD"},
            {"stage_key": "FINAL_REVIEW", "allowed_role": "WORKSPACE_OWNER"},
        ]),
        valid_from=datetime.now(timezone.utc) - timedelta(minutes=1),
        status="ACTIVE",
    )
    db.add_all([resource, policy])
    db.commit()
    yield db, session_factory, workspace, memberships, resource, policy
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _actor(db, workspace, membership_id):
    actor = load_actor(db, workspace.id, membership_id)
    assert actor is not None
    return actor


def _tao_run(db, workspace, memberships, resource):
    return ApprovalService.start_approval_run(
        db,
        _actor(db, workspace, "member-author"),
        artifact_type="IDEA",
        artifact_id=resource.id,
        expected_version=resource.artifact_version,
    )


def test_approval_khong_nhan_policy_hoac_hash_tu_client(du_lieu_rbac):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    run = _tao_run(db, workspace, memberships, resource)
    assert run.policy_id == "policy-current"
    assert run.content_hash == resource.content_hash
    assert run.created_by == "member-author"


def test_approval_tu_choi_nguoi_duyet_khong_dung_role_chang(du_lieu_rbac):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    run = _tao_run(db, workspace, memberships, resource)
    with pytest.raises(ValueError):
        ApprovalService.record_decision(
            db,
            _actor(db, workspace, "member-reviewer"),
            step_id=run.steps[0].id,
            result="APPROVED",
            artifact_version=1,
            content_hash="a" * 64,
        )


def test_approval_chan_tac_gia_that_cua_tai_nguyen(du_lieu_rbac):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    resource.creator_id = "user-worker_author"
    resource.owner_id = "user-worker_author"
    db.commit()
    run = _tao_run(db, workspace, memberships, resource)
    with pytest.raises(ValueError):
        ApprovalService.record_decision(
            db,
            _actor(db, workspace, "member-worker_author"),
            step_id=run.steps[0].id,
            result="APPROVED",
            artifact_version=1,
            content_hash="a" * 64,
        )


def test_approval_tu_choi_tai_nguyen_da_doi_phien_ban(du_lieu_rbac):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    run = _tao_run(db, workspace, memberships, resource)
    resource.artifact_version = 2
    resource.content_hash = "b" * 64
    db.commit()
    with pytest.raises(ValueError):
        ApprovalService.record_decision(
            db,
            _actor(db, workspace, "member-lead"),
            step_id=run.steps[0].id,
            result="APPROVED",
            artifact_version=1,
            content_hash="a" * 64,
        )


def test_worker_grant_tu_choi_action_ngoai_quyen_hien_tai(du_lieu_rbac, monkeypatch):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    with pytest.raises(ValueError):
        WorkerAuthService.issue_grant(
            db,
            _actor(db, workspace, "member-author"),
            job_id="job-fake-action",
            target_resource=resource.id,
            allowed_actions=["fake.action"],
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )


def test_worker_recheck_that_quyen_sau_khi_role_bi_thu_hoi(du_lieu_rbac, monkeypatch):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    grant = WorkerAuthService.issue_grant(
        db,
        _actor(db, workspace, "member-author"),
        job_id="job-revoke-role",
        target_resource=resource.id,
        allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.commit()
    assignment = db.query(RoleAssignment).filter_by(membership_id="member-author").one()
    assignment.status = "REVOKED"
    db.commit()
    result = WorkerAuthService.recheck_runtime_permission(
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-pool"
    )
    assert result.allowed is False
    assert result.workspace_id is None
    assert result.target_resource is None


def _jwt(secret, subject, audience="worker-test-audience"):
    def segment(value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    header = segment({"alg": "HS256", "typ": "JWT"})
    payload = segment({
        "sub": subject,
        "iss": "unit-test-issuer",
        "aud": audience,
        "exp": int(time.time()) + 120,
    })
    signing_input = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{signing_input}.{signature}"


def test_worker_recheck_can_bi_toi_han_yeu_cau_da_xac_minh(du_lieu_rbac, monkeypatch):
    db, _, _, _, _, _ = du_lieu_rbac
    secret = "test-only-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()
    monkeypatch.setattr(settings, "jwt_secret_key", secret)
    monkeypatch.setattr(settings, "jwt_issuer", "unit-test-issuer")
    monkeypatch.setattr(settings, "worker_jwt_audience", "worker-test-audience")
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")

    app = FastAPI()
    app.include_router(worker_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    token = _jwt(secret, "worker-pool")
    response = TestClient(app).post(
        "/authz/v1/workers/recheck",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_id": "unknown-job", "action_key": "ideas.read"},
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is False


def test_worker_recheck_tu_choi_token_dung_subject_khac(du_lieu_rbac, monkeypatch):
    db, _, _, _, _, _ = du_lieu_rbac
    secret = "test-only-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()
    monkeypatch.setattr(settings, "jwt_secret_key", secret)
    monkeypatch.setattr(settings, "jwt_issuer", "unit-test-issuer")
    monkeypatch.setattr(settings, "worker_jwt_audience", "worker-test-audience")
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    app = FastAPI()
    app.include_router(worker_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).post(
        "/authz/v1/workers/recheck",
        headers={"Authorization": f"Bearer {_jwt(secret, 'other-service')}"},
        json={"job_id": "unknown-job", "action_key": "ideas.read"},
    )
    assert response.status_code == 401


def test_worker_recheck_that_khi_thieu_cau_hinh_xac_thuc(du_lieu_rbac, monkeypatch):
    db, _, _, _, _, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "jwt_secret_key", None)
    monkeypatch.setattr(settings, "jwt_issuer", "unit-test-issuer")
    monkeypatch.setattr(settings, "worker_jwt_audience", "worker-test-audience")
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    app = FastAPI()
    app.include_router(worker_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).post(
        "/authz/v1/workers/recheck",
        json={"job_id": "unknown-job", "action_key": "ideas.read"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "WORKER_AUTH_NOT_CONFIGURED"


def test_approval_transition_flushed_and_idempotent(du_lieu_rbac):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    run = _tao_run(db, workspace, memberships, resource)
    step_id = run.steps[0].id
    reviewer = _actor(db, workspace, "member-lead")
    for _ in range(2):
        ApprovalService.record_decision(
            db, reviewer, step_id=step_id, result="APPROVED",
            artifact_version=1, content_hash="a" * 64,
        )
        db.commit()
    db.expire_all()
    assert db.query(ApprovalRun).filter_by(id=run.id).one().status == "PENDING"
    assert db.query(ApprovalDecision).filter_by(step_id=step_id).count() == 1


def test_approval_chi_chuyen_run_sang_approved_sau_chang_cuoi(du_lieu_rbac):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    run = _tao_run(db, workspace, memberships, resource)
    lead = _actor(db, workspace, "member-lead")
    owner = _actor(db, workspace, "member-reviewer")
    ordered_steps = sorted(run.steps, key=lambda item: item.ordinal)

    ApprovalService.record_decision(
        db, lead, step_id=ordered_steps[0].id, result="APPROVED",
        artifact_version=1, content_hash="a" * 64,
    )
    db.commit()
    db.expire_all()
    assert db.query(ApprovalRun).filter_by(id=run.id).one().status == "PENDING"

    ApprovalService.record_decision(
        db, owner, step_id=ordered_steps[1].id, result="APPROVED",
        artifact_version=1, content_hash="a" * 64,
    )
    db.commit()
    db.expire_all()
    assert db.query(ApprovalRun).filter_by(id=run.id).one().status == "APPROVED"
    assert db.query(ApprovalDecision).filter(
        ApprovalDecision.step_id.in_([step.id for step in ordered_steps])
    ).count() == 2


def test_approval_tu_choi_bo_qua_chang_dau(du_lieu_rbac):
    db, _, workspace, memberships, resource, _ = du_lieu_rbac
    run = _tao_run(db, workspace, memberships, resource)
    final_step = max(run.steps, key=lambda item: item.ordinal)
    with pytest.raises(ValueError, match="APPROVAL_STAGE_ORDER_DENIED"):
        ApprovalService.record_decision(
            db, _actor(db, workspace, "member-reviewer"), step_id=final_step.id,
            result="APPROVED", artifact_version=1, content_hash="a" * 64,
        )


def test_worker_grant_pin_server_version_subject_va_audit(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    grant = WorkerAuthService.issue_grant(
        db, _actor(db, workspace, "member-author"), job_id="job-pinned",
        target_resource=resource.id, allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    assert grant.target_artifact_version == resource.artifact_version
    assert grant.target_content_hash == resource.content_hash
    assert grant.worker_subject == "worker-pool"
    audit = db.query(AuthorizationAuditEvent).filter_by(
        action_key="delegation.issue", decision="ALLOW",
    ).one()
    assert audit.resource_id_hash != resource.id
    assert len(audit.resource_id_hash) == 64


def test_worker_recheck_tu_choi_sau_khi_tai_nguyen_doi_version(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    grant = WorkerAuthService.issue_grant(
        db, _actor(db, workspace, "member-author"), job_id="job-resource-changed",
        target_resource=resource.id, allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.commit()
    resource.artifact_version = 2
    resource.content_hash = "b" * 64
    db.commit()
    result = WorkerAuthService.recheck_runtime_permission(
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-pool"
    )
    assert result.allowed is False
    assert grant.status == "REVOKED"


def test_worker_grant_tu_choi_ttl_qua_15_phut(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    with pytest.raises(ValueError, match="WORKER_TTL_OUT_OF_RANGE"):
        WorkerAuthService.issue_grant(
            db, _actor(db, workspace, "member-author"), job_id="job-too-long",
            target_resource=resource.id, allowed_actions=["ideas.read"],
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
        )


def test_worker_recheck_that_khi_policy_version_thay_doi(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    grant = WorkerAuthService.issue_grant(
        db, _actor(db, workspace, "member-author"), job_id="job-policy-changed",
        target_resource=resource.id, allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.commit()
    monkeypatch.setattr(settings, "policy_version", "next-version")
    result = WorkerAuthService.recheck_runtime_permission(
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-pool"
    )
    assert result.allowed is False
    assert grant.status == "REVOKED"


def test_approval_resolver_cho_phep_actor_trong_project_duoc_gan(du_lieu_rbac):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    actor = _actor(db, workspace, "member-project")
    run = ApprovalService.start_approval_run(
        db, actor, artifact_type="IDEA", artifact_id=resource.id, expected_version=1,
    )
    assert run.artifact_id == resource.id


def test_approval_resolver_tu_choi_actor_ngoai_project_duoc_gan(du_lieu_rbac):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    resource.project_id = "project-b"
    db.commit()
    with pytest.raises(ValueError, match="APPROVAL_SUBMISSION_DENIED"):
        ApprovalService.start_approval_run(
            db, _actor(db, workspace, "member-project"),
            artifact_type="IDEA", artifact_id=resource.id, expected_version=1,
        )


def test_worker_recheck_ap_dung_project_scope_canonical(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-project-pool")
    grant = DelegatedJobGrant(
        id="grant-project",
        workspace_id=workspace.id,
        job_id="job-project-scope",
        initiating_membership_id="member-project",
        target_resource=resource.id,
        target_artifact_version=resource.artifact_version,
        target_content_hash=resource.content_hash,
        worker_subject="worker-project-pool",
        allowed_actions_json='["ideas.read"]',
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        policy_version=settings.policy_version,
        status="ACTIVE",
    )
    db.add(grant)
    db.commit()

    result = WorkerAuthService.recheck_runtime_permission(
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-project-pool"
    )
    assert result.allowed is True
    assert result.workspace_id == grant.workspace_id
    assert result.target_resource == resource.id
    assert result.resource_type == resource.resource_type
    assert result.artifact_version == grant.target_artifact_version
    assert result.content_hash == grant.target_content_hash
    assert result.policy_version == grant.policy_version
    resource.project_id = "project-b"
    db.commit()
    denied = WorkerAuthService.recheck_runtime_permission(
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-project-pool"
    )
    assert denied.allowed is False
    assert denied.workspace_id is None
    assert denied.target_resource is None
    assert denied.artifact_version is None
    assert denied.content_hash is None
    assert denied.policy_version is None

```
## tests/test_api_endpoints.py — SHA256 398C3C7E63B85CBFF3ED4B751122D67B765BBCBB9BB898B82354EC0E83F73BEC
```python
"""Kiểm thử API tích hợp bằng bearer giả lập và cơ sở dữ liệu SQLite RAM."""

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from baha_auth.src.config import settings
from baha_auth.src.main import app
from baha_auth.src.models.entities import (
    ApprovalPolicy,
    BusinessResource,
    GlobalUser,
    Membership,
    RoleAssignment,
)


# Bí mật ngẫu nhiên chỉ tồn tại trong tiến trình kiểm thử; không phải credential thật.
_TEST_SECRET = secrets.token_urlsafe(32)
settings.jwt_secret_key = _TEST_SECRET
settings.jwt_issuer = "baha-auth-test-issuer"
settings.jwt_audience = "baha-auth-test-api"
settings.worker_jwt_audience = "baha-auth-test-worker"
settings.worker_jwt_subject = "baha-auth-test-worker-pool"
client = TestClient(app)


def _segment(value):
    encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _token(subject, audience):
    header = _segment({"alg": "HS256", "typ": "JWT"})
    payload = _segment({
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": audience,
        "exp": int(time.time()) + 300,
    })
    signing_input = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(
        hmac.new(_TEST_SECRET.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return f"{signing_input}.{signature}"


def _user_headers(workspace_id, user_id):
    return {
        "Authorization": f"Bearer {_token(user_id, settings.jwt_audience)}",
        "X-Workspace-Id": workspace_id,
    }


def _worker_headers():
    return {"Authorization": f"Bearer {_token(settings.worker_jwt_subject, settings.worker_jwt_audience)}"}


def test_api_healthz():
    res = client.get("/authz/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_org_units_lifecycle(multi_tenant_fixture):
    f = multi_tenant_fixture
    headers = _user_headers(f["ws_a"].id, f["m_a_owner"].user_id)

    res = client.post("/authz/v1/org/units", headers=headers, json={
        "name": "Finance & Accounting",
        "type": "DEPARTMENT",
    })
    assert res.status_code == 201
    unit_id = res.json()["id"]

    res = client.get("/authz/v1/org/units", headers=headers)
    assert res.status_code == 200
    assert any(unit["id"] == unit_id for unit in res.json())


def test_api_roles_and_permissions_catalog(multi_tenant_fixture):
    f = multi_tenant_fixture
    headers = _user_headers(f["ws_a"].id, f["m_a_owner"].user_id)

    res = client.get("/authz/v1/permissions", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 50

    res = client.get("/authz/v1/roles", headers=headers)
    assert res.status_code == 200


def test_api_member_invite_and_assignment(multi_tenant_fixture):
    f = multi_tenant_fixture
    headers = _user_headers(f["ws_a"].id, f["m_a_owner"].user_id)

    res = client.post("/authz/v1/members/invite", headers=headers, json={
        "email": f"new_hire_{uuid.uuid4().hex[:8]}@example.test",
        "full_name": "New Hire",
        "initial_role_code": "RESEARCHER",
        "scope_type": "WORKSPACE",
    })
    assert res.status_code == 201
    new_membership_id = res.json()["id"]

    res = client.post("/authz/v1/assignments", headers=headers, json={
        "grantee_membership_id": new_membership_id,
        "role_code": "STRATEGIST",
        "scope_type": "WORKSPACE",
        "reason": "Promotion",
    })
    assert res.status_code == 201
    assignment_id = res.json()["id"]

    res = client.delete(f"/authz/v1/assignments/{assignment_id}", headers=headers)
    assert res.status_code == 200


def test_api_evaluate_engine_decision(multi_tenant_fixture):
    f = multi_tenant_fixture
    headers = _user_headers(f["ws_a"].id, f["m_a_owner"].user_id)

    res = client.post("/authz/v1/evaluate", headers=headers, json={"action_key": "workspace.read"})
    assert res.status_code == 200
    assert res.json()["allowed"] is True
    assert res.json()["decision"] == "ALLOW"

    res = client.post("/authz/v1/evaluate", headers=headers, json={
        "action_key": "fake.action.does_not_exist",
    })
    assert res.status_code == 200
    assert res.json()["allowed"] is False
    assert res.json()["reason_code"] == "UNREGISTERED_ACTION"


def test_api_approvals_and_sod_enforcement(multi_tenant_fixture, db):
    f = multi_tenant_fixture
    reviewer = GlobalUser(
        id=str(uuid.uuid4()),
        email=f"reviewer_{uuid.uuid4().hex[:8]}@example.test",
        full_name="Người duyệt",
    )
    db.add(reviewer)
    db.flush()
    reviewer_membership = Membership(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, user_id=reviewer.id, status="ACTIVE",
    )
    db.add(reviewer_membership)
    db.flush()
    db.add(RoleAssignment(
        workspace_id=f["ws_a"].id,
        membership_id=reviewer_membership.id,
        role_id=f["roles"]["WORKSPACE_OWNER"].id,
        scope_type="WORKSPACE",
        status="ACTIVE",
    ))
    resource = BusinessResource(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id,
        owner_id=f["m_a_owner"].user_id, creator_id=f["m_a_owner"].user_id,
        artifact_version=1, resource_type="BRIEF", title="Brief thử nghiệm",
        content_hash="a" * 64, is_quarantined=False,
    )
    policy = ApprovalPolicy(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id,
        version=1,
        stages_json=json.dumps([{"stage_key": "FINAL_REVIEW", "allowed_role": "WORKSPACE_OWNER"}]),
        valid_from=datetime.now(timezone.utc) - timedelta(minutes=1), status="ACTIVE",
    )
    db.add_all([resource, policy])
    db.commit()

    headers_owner = _user_headers(f["ws_a"].id, f["m_a_owner"].user_id)
    headers_reviewer = _user_headers(f["ws_a"].id, reviewer.id)
    res = client.post("/authz/v1/approvals/runs", headers=headers_owner, json={
        "artifact_type": "BRIEF",
        "artifact_id": resource.id,
        "expected_version": 1,
    })
    assert res.status_code == 201
    step_id = res.json()["steps"][0]["id"]

    decision_body = {
        "step_id": step_id,
        "result": "APPROVED",
        "artifact_version": 1,
        "content_hash": "a" * 64,
    }
    res = client.post("/authz/v1/approvals/decisions", headers=headers_owner, json=decision_body)
    assert res.status_code == 403

    res = client.post("/authz/v1/approvals/decisions", headers=headers_reviewer, json=decision_body)
    assert res.status_code == 200
    assert res.json()["result"] == "APPROVED"


def test_api_worker_grants_and_recheck(multi_tenant_fixture, db):
    f = multi_tenant_fixture
    headers = _user_headers(f["ws_a"].id, f["m_a_owner"].user_id)
    resource = f["res_a1"]
    resource.content_hash = "c" * 64
    db.commit()

    job_id = f"job-render-{uuid.uuid4().hex}"
    exp = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    res = client.post("/authz/v1/workers/grants", headers=headers, json={
        "job_id": job_id,
        "target_resource": resource.id,
        "allowed_actions": ["ideas.read"],
        "expires_at": exp,
    })
    assert res.status_code == 201
    grant_out = res.json()
    assert grant_out["workspace_id"] == f["ws_a"].id
    assert grant_out["target_resource"] == resource.id
    assert grant_out["resource_type"] == resource.resource_type
    assert grant_out["artifact_version"] == resource.artifact_version
    assert grant_out["content_hash"] == resource.content_hash

    res = client.post(
        "/authz/v1/workers/recheck",
        headers=_worker_headers(),
        json={"job_id": job_id, "action_key": "ideas.read"},
    )
    assert res.status_code == 200
    allowed = res.json()
    assert allowed["allowed"] is True
    assert allowed["workspace_id"] == grant_out["workspace_id"]
    assert allowed["target_resource"] == grant_out["target_resource"]
    assert allowed["resource_type"] == grant_out["resource_type"]
    assert allowed["artifact_version"] == grant_out["artifact_version"]
    assert allowed["content_hash"] == grant_out["content_hash"]
    assert allowed["policy_version"] == grant_out["policy_version"]

    res = client.post(
        "/authz/v1/workers/recheck",
        headers=_worker_headers(),
        json={"job_id": job_id, "action_key": "unauthorized.publish"},
    )
    assert res.status_code == 200
    assert res.json()["allowed"] is False
    assert res.json()["workspace_id"] is None
    assert res.json()["target_resource"] is None
    assert res.json()["artifact_version"] is None
    assert res.json()["content_hash"] is None
    assert res.json()["policy_version"] is None


def test_api_worker_recheck_requires_verified_service_token(multi_tenant_fixture):
    response = client.post(
        "/authz/v1/workers/recheck",
        json={"job_id": "guessed-job", "action_key": "ideas.read"},
    )
    assert response.status_code == 401

```
