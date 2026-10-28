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
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission, founder_workspace_owner
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
        if not resource.creator_id and not resource.owner_id:
            _deny(
                db, actor, "RESOURCE_ATTRIBUTION_REQUIRED",
                action_key="approval.step.decide", resource=resource,
            )
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
        interested_parties = {user_id for user_id in (resource.creator_id, resource.owner_id) if user_id}
        founder_self_approval = actor.user_id in interested_parties and founder_workspace_owner(actor)
        self_approval = actor.membership_id == run.created_by or actor.user_id in interested_parties
        if self_approval and not founder_self_approval:
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
        if founder_self_approval and (stage["kind"] != "role" or stage["assignee"] != "WORKSPACE_OWNER"):
            _deny(db, actor, "SELF_APPROVAL_DENIED", action_key="approval.step.decide", resource=resource, policy_version=str(policy.version))
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
            reason="FOUNDER_SELF_APPROVAL_EXCEPTION" if founder_self_approval else "APPROVAL_DECISION_RECORDED", resource=resource,
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
