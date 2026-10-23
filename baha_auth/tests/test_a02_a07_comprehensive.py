# Test Suite cho cac Phase A02 -> A07 (Hierarchy, Policy Engine, Roles, Approvals, Workers)
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from baha_auth.src.services.org_service import OrgService
from baha_auth.src.services.role_service import RoleService
from baha_auth.src.services.approval_service import ApprovalService
from baha_auth.src.services.worker_service import WorkerAuthService
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.models.entities import Membership, Role, RoleAssignment


def _actor_chu_workspace(f):
    return ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[],
    )

def test_auth_020_org_cycle_detection_prevented(db, multi_tenant_fixture):
    """
    AUTH-020: Set Team A as parent of its own ancestor (Cycle Detection).
    Expected: Cycle refused; graph remains unchanged.
    """
    f = multi_tenant_fixture
    ws_id = f["ws_a"].id
    actor = _actor_chu_workspace(f)

    unit_a = OrgService.create_org_unit(db, ws_id, "Company Root", "COMPANY", actor=actor)
    unit_b = OrgService.create_org_unit(db, ws_id, "Tech Department", "DEPARTMENT", parent_id=unit_a.id, actor=actor)
    unit_c = OrgService.create_org_unit(db, ws_id, "Backend Team", "TEAM", parent_id=unit_b.id, actor=actor)

    # Co tinh dat Root lam con cua Backend Team (A -> B -> C -> A)
    success = OrgService.set_unit_parent(db, unit_a.id, unit_c.id, actor=actor)
    assert success is False, "He thong bat buoc phat hien va chan vong lap chu trinh to chuc"

def test_auth_021_cross_tenant_reporting_line_refused(db, multi_tenant_fixture):
    """
    AUTH-021: Assign B membership/reporting line into A organization unit.
    Expected: Refused at API and relational constraints.
    """
    f = multi_tenant_fixture
    actor = _actor_chu_workspace(f)
    # Co gang tao reporting line giua Manager A va Report B
    success = OrgService.assign_reporting_line(
        db,
        f["ws_a"].id,
        f["m_a_owner"].id,
        f["m_b_member"].id,
        actor=actor,
    )
    assert success is False, "Khong the tao tuyen bao cao xuyen tenant"

def test_auth_030_unregistered_action_denied_by_default():
    """
    AUTH-030: Unregistered action with otherwise powerful role.
    Expected: Deny by default, no side effects.
    """
    actor = ActorContext(
        user_id="user-123",
        workspace_id="ws-123",
        membership_id="mem-123",
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    decision = evaluate_permission(actor, "malicious.unregistered_backdoor_action")
    assert decision.allowed is False
    assert decision.decision == "DENY"
    assert decision.reason_code == "UNREGISTERED_ACTION"

def test_auth_040_self_privilege_escalation_denied(db, multi_tenant_fixture):
    """
    AUTH-040: Prevent user from assigning higher roles to themselves (No self-escalation).
    Expected: Error raised / denied.
    """
    f = multi_tenant_fixture
    with pytest.raises(ValueError, match="SELF_PRIVILEGE_ESCALATION_DENIED"):
        RoleService.assign_role(
            db,
            f["ws_a"].id,
            grantor_membership_id=f["m_a_member"].id,
            grantee_membership_id=f["m_a_member"].id, # Tu gan cho chinh minh
            role_code="WORKSPACE_OWNER"
        )

def test_auth_044_last_owner_protection_violation(db, multi_tenant_fixture):
    """
    AUTH-044: Last owner deletion/revocation protection.
    Expected: Refused with LAST_OWNER_PROTECTION_VIOLATION.
    """
    f = multi_tenant_fixture
    # Tim assignment cua owner A
    assignment = db.query(RoleAssignment).filter(
        RoleAssignment.membership_id == f["m_a_owner"].id,
        RoleAssignment.status == "ACTIVE"
    ).first()

    with pytest.raises(ValueError, match="LAST_OWNER_PROTECTION_VIOLATION"):
        RoleService.revoke_role(db, f["ws_a"].id, f["m_a_owner"].id, assignment.id)

def test_auth_060_separation_of_duties_anti_self_approval(db, multi_tenant_fixture):
    """
    AUTH-060: Author cannot perform final approval of their own artifact (SoD).
    Expected: Refused with SELF_FINAL_APPROVAL_DENIED.
    """
    import json
    from baha_auth.src.models.entities import ApprovalPolicy, BusinessResource
    from baha_auth.src.services.danh_tinh_service import load_actor

    f = multi_tenant_fixture
    actor = load_actor(db, f["ws_a"].id, f["m_a_member"].id)
    resource = BusinessResource(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id,
        owner_id=f["m_a_member"].user_id, creator_id=f["m_a_member"].user_id,
        artifact_version=1, resource_type="IDEA", title="Ý tưởng của tác giả",
        content_hash="a" * 64,
    )
    policy = ApprovalPolicy(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, version=1,
        stages_json=json.dumps([{"stage_key": "TEAM_REVIEW", "allowed_role": "TEAM_LEAD"}]),
        valid_from=datetime.now(timezone.utc) - timedelta(minutes=1), status="ACTIVE",
    )
    db.add_all([resource, policy])
    db.commit()
    run = ApprovalService.start_approval_run(
        db, actor, artifact_type="IDEA", artifact_id=resource.id, expected_version=1,
    )

    with pytest.raises(ValueError, match="SELF_APPROVAL_DENIED"):
        ApprovalService.record_decision(
            db, actor, step_id=run.steps[0].id, result="APPROVED",
            artifact_version=1, content_hash="a" * 64,
        )

def test_auth_061_stale_artifact_version_rejected(db, multi_tenant_fixture):
    """
    AUTH-061: Approval decision on stale artifact version or altered content hash.
    Expected: Rejected with STALE_ARTIFACT_VERSION.
    """
    import json
    from baha_auth.src.models.entities import ApprovalPolicy, BusinessResource
    from baha_auth.src.services.danh_tinh_service import load_actor

    f = multi_tenant_fixture
    author = load_actor(db, f["ws_a"].id, f["m_a_member"].id)
    reviewer = load_actor(db, f["ws_a"].id, f["m_a_owner"].id)
    resource = BusinessResource(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id,
        owner_id=f["m_a_member"].user_id, creator_id=f["m_a_member"].user_id,
        artifact_version=2, resource_type="IDEA", title="Phiên bản mới",
        content_hash="b" * 64,
    )
    policy = ApprovalPolicy(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, version=1,
        stages_json=json.dumps([{"stage_key": "TEAM_REVIEW", "allowed_role": "TEAM_LEAD"}]),
        valid_from=datetime.now(timezone.utc) - timedelta(minutes=1), status="ACTIVE",
    )
    db.add_all([resource, policy])
    db.commit()
    run = ApprovalService.start_approval_run(
        db, author, artifact_type="IDEA", artifact_id=resource.id, expected_version=2,
    )

    with pytest.raises(ValueError, match="STALE_ARTIFACT_VERSION"):
        ApprovalService.record_decision(
            db, reviewer, step_id=run.steps[0].id, result="APPROVED",
            artifact_version=1, content_hash="b" * 64,
        )

def test_auth_070_worker_expired_grant_rejected(db, multi_tenant_fixture, monkeypatch):
    """
    AUTH-070: Worker job grant expired -> Rejected at runtime.
    """
    f = multi_tenant_fixture
    from baha_auth.src.config import settings

    actor = _actor_chu_workspace(f)
    resource = f["res_a1"]
    resource.content_hash = "c" * 64
    db.flush()
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-test-pool")
    job_id = f"job-exp-{uuid.uuid4().hex[:8]}"
    grant = WorkerAuthService.issue_grant(
        db, actor, job_id=job_id, target_resource=resource.id,
        allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    grant.expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()

    allowed = WorkerAuthService.recheck_runtime_permission(
        db, job_id=job_id, action_key="ideas.read", worker_subject="worker-test-pool",
        expected_workspace_id=f["ws_a"].id,
    )
    assert allowed.allowed is False, "The uy quyen het han phai bi tu choi tai runtime"

def test_auth_071_worker_cancels_on_initiator_revocation(db, multi_tenant_fixture, monkeypatch):
    """
    AUTH-071: When initiating membership is revoked/suspended, background worker cancels.
    """
    f = multi_tenant_fixture
    from baha_auth.src.config import settings

    actor = _actor_chu_workspace(f)
    resource = f["res_a1"]
    resource.content_hash = "d" * 64
    db.flush()
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-test-pool")
    job_id = f"job-act-{uuid.uuid4().hex[:8]}"
    WorkerAuthService.issue_grant(
        db, actor, job_id=job_id, target_resource=resource.id,
        allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    # Thu hồi role hiện tại của người khởi tạo trước thời điểm chạy.
    owner_assignment = db.query(RoleAssignment).filter_by(
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        status="ACTIVE",
    ).first()
    owner_assignment.status = "REVOKED"
    db.commit()

    allowed = WorkerAuthService.recheck_runtime_permission(
        db, job_id=job_id, action_key="ideas.read", worker_subject="worker-test-pool",
        expected_workspace_id=f["ws_a"].id,
    )
    assert allowed.allowed is False, "Khi nguoi khoi tao bi thu hoi quyen, job bat buoc bi huy bo tai runtime"
