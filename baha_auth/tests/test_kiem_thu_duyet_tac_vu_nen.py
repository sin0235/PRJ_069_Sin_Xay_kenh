"""Kiểm thử cô lập cho phân quyền duyệt và worker, chỉ dùng SQLite trong RAM."""

import base64
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

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
from baha_auth.src import database as database_module
from baha_auth.src.database import Base, get_db, get_tenant_context
from baha_auth.src.models.entities import (
    ApprovalDecision,
    ApprovalPolicy,
    ApprovalRun,
    ApprovalStep,
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
from baha_auth.src.policy.evaluator import ResourceContext, evaluate_permission
from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, verify_bearer_token
from baha_auth.src.api import worker_router as worker_router_module
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


def test_owner_khong_duoc_tu_duyet_khi_creator_khac_owner(du_lieu_rbac):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    resource.creator_id = "user-author"
    resource.owner_id = "user-reviewer"
    db.commit()
    run = _tao_run(db, workspace, [], resource)
    ordered_steps = sorted(run.steps, key=lambda item: item.ordinal)
    lead = _actor(db, workspace, "member-lead")
    owner = _actor(db, workspace, "member-reviewer")

    decision = evaluate_permission(owner, "ideas.approve_final", ResourceContext(
        workspace_id=resource.workspace_id,
        resource_id=resource.id,
        resource_type=resource.resource_type,
        owner_id=resource.owner_id,
        creator_id=resource.creator_id,
    ))
    assert decision.allowed is False

    ApprovalService.record_decision(
        db, lead, step_id=ordered_steps[0].id, result="APPROVED",
        artifact_version=1, content_hash=resource.content_hash,
    )
    db.commit()
    db.expire_all()
    before = db.query(ApprovalDecision).count()
    with pytest.raises(ValueError, match="SELF_APPROVAL_DENIED|SELF_FINAL_APPROVAL_DENIED"):
        ApprovalService.record_decision(
            db, owner, step_id=ordered_steps[1].id, result="APPROVED",
            artifact_version=1, content_hash=resource.content_hash,
        )
    db.commit()
    db.expire_all()
    assert db.query(ApprovalDecision).count() == before
    assert db.query(ApprovalRun).filter_by(id=run.id).one().status == "PENDING"
    assert db.query(ApprovalStep).filter_by(id=ordered_steps[1].id).one().status == "PENDING"

    independent_user = GlobalUser(
        id="user-independent-reviewer", email="independent@example.invalid", status="ACTIVE",
    )
    independent_membership = Membership(
        id="member-independent-reviewer", workspace_id=workspace.id,
        user_id=independent_user.id, status="ACTIVE",
    )
    db.add_all([independent_user, independent_membership])
    db.flush()
    db.add(RoleAssignment(
        workspace_id=workspace.id,
        membership_id=independent_membership.id,
        role_id="role-owner",
        scope_type="WORKSPACE",
        status="ACTIVE",
        valid_from=datetime.now(timezone.utc) - timedelta(minutes=1),
    ))
    db.commit()
    independent = _actor(db, workspace, independent_membership.id)
    ApprovalService.record_decision(
        db, independent, step_id=ordered_steps[1].id, result="APPROVED",
        artifact_version=1, content_hash=resource.content_hash,
    )
    db.commit()
    db.expire_all()
    assert db.query(ApprovalDecision).filter_by(step_id=ordered_steps[1].id).one().reviewer_membership_id == independent_membership.id
    assert db.query(ApprovalRun).filter_by(id=run.id).one().status == "APPROVED"


def test_founder_workspace_owner_duoc_tu_duyet_va_ghi_ly_do(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    monkeypatch.setenv("FOUNDER_EMAIL", "author@example.invalid")
    run = _tao_run(db, workspace, [], resource)
    ordered_steps = sorted(run.steps, key=lambda item: item.ordinal)
    lead = _actor(db, workspace, "member-lead")
    founder = _actor(db, workspace, "member-author")

    ApprovalService.record_decision(
        db, lead, step_id=ordered_steps[0].id, result="APPROVED",
        artifact_version=1, content_hash=resource.content_hash,
    )
    db.commit()
    db.expire_all()
    decision = ApprovalService.record_decision(
        db, founder, step_id=ordered_steps[1].id, result="APPROVED",
        artifact_version=1, content_hash=resource.content_hash,
    )
    db.commit()

    assert decision.result == "APPROVED"
    audit = db.query(AuthorizationAuditEvent).filter_by(
        action_key="ideas.approve_final", decision="ALLOW",
        internal_reason="FOUNDER_SELF_APPROVAL_EXCEPTION",
    ).one()
    assert audit.actor_id == founder.user_id


def test_founder_khong_tu_duyet_neu_chang_cuoi_khong_giao_cho_workspace_owner(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, policy = du_lieu_rbac
    monkeypatch.setenv("FOUNDER_EMAIL", "author@example.invalid")
    policy.stages_json = json.dumps([
        {"stage_key": "TEAM_REVIEW", "allowed_role": "TEAM_LEAD"},
        {"stage_key": "FINAL_REVIEW", "allowed_role": "TEAM_LEAD"},
    ])
    db.commit()
    run = _tao_run(db, workspace, [], resource)
    ordered_steps = sorted(run.steps, key=lambda item: item.ordinal)
    lead = _actor(db, workspace, "member-lead")
    founder = _actor(db, workspace, "member-author")
    ApprovalService.record_decision(
        db, lead, step_id=ordered_steps[0].id, result="APPROVED",
        artifact_version=1, content_hash=resource.content_hash,
    )
    db.commit()

    with pytest.raises(ValueError, match="SELF_APPROVAL_DENIED"):
        ApprovalService.record_decision(
            db, founder, step_id=ordered_steps[1].id, result="APPROVED",
            artifact_version=1, content_hash=resource.content_hash,
        )

    assert db.query(ApprovalDecision).filter_by(step_id=ordered_steps[1].id).count() == 0


def test_evaluator_tu_choi_duyet_khi_thieu_resource_context(du_lieu_rbac):
    db, _, workspace, _, _, _ = du_lieu_rbac
    reviewer = _actor(db, workspace, "member-reviewer")
    decision = evaluate_permission(reviewer, "ideas.approve_final")
    assert decision.allowed is False
    assert decision.reason_code == "RESOURCE_CONTEXT_REQUIRED"


def test_evaluator_tu_choi_duyet_resource_thieu_owner_va_creator(du_lieu_rbac):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    reviewer = _actor(db, workspace, "member-reviewer")
    decision = evaluate_permission(reviewer, "ideas.approve_final", ResourceContext(
        workspace_id=workspace.id,
        resource_id=resource.id,
        resource_type=resource.resource_type,
        owner_id=None,
        creator_id=None,
    ))
    assert decision.allowed is False
    assert decision.reason_code == "RESOURCE_ATTRIBUTION_REQUIRED"


def test_approval_tu_choi_resource_mat_owner_va_creator_truoc_khi_tao_quyet_dinh(du_lieu_rbac):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    run = _tao_run(db, workspace, [], resource)
    resource.owner_id = None
    resource.creator_id = None
    db.commit()
    with pytest.raises(ValueError, match="RESOURCE_ATTRIBUTION_REQUIRED"):
        ApprovalService.record_decision(
            db, _actor(db, workspace, "member-lead"),
            step_id=run.steps[0].id, result="APPROVED",
            artifact_version=1, content_hash=resource.content_hash,
        )
    db.rollback()
    assert db.query(ApprovalDecision).count() == 0


def test_xac_minh_workspace_claim_human_optional_va_claim_loi_bi_tu_choi():
    secret = "test-only-workspace-claim"
    human = verify_bearer_token(
        _jwt(secret, "human-user", audience="human-audience"),
        secret=secret, issuer="unit-test-issuer", audience="human-audience",
    )
    assert human.workspace_id is None
    worker = verify_bearer_token(
        _jwt(secret, "worker-pool", audience="worker-audience", workspace_id="ws-a"),
        secret=secret, issuer="unit-test-issuer", audience="worker-audience",
    )
    assert worker.workspace_id == "ws-a"
    with pytest.raises(InvalidBearerToken, match="INVALID_WORKSPACE_ID"):
        verify_bearer_token(
            _jwt(secret, "worker-pool", audience="worker-audience", workspace_id={"id": "ws-a"}),
            secret=secret, issuer="unit-test-issuer", audience="worker-audience",
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
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-pool",
        expected_workspace_id=workspace.id,
    )
    assert result.allowed is False
    assert result.workspace_id is None
    assert result.target_resource is None


def _jwt(secret, subject, audience="worker-test-audience", workspace_id=None):
    def segment(value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    header = segment({"alg": "HS256", "typ": "JWT"})
    claims = {
        "sub": subject,
        "iss": "unit-test-issuer",
        "aud": audience,
        "exp": int(time.time()) + 120,
    }
    if workspace_id is not None:
        claims["workspace_id"] = workspace_id
    payload = segment(claims)
    signing_input = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{signing_input}.{signature}"


def test_worker_recheck_can_bi_toi_han_yeu_cau_da_xac_minh(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, _, _ = du_lieu_rbac
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
    token = _jwt(secret, "worker-pool", workspace_id=workspace.id)
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


def test_worker_recheck_tu_choi_token_thieu_workspace_claim(du_lieu_rbac, monkeypatch):
    db, _, _, _, _, _ = du_lieu_rbac
    secret = "test-only-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()
    monkeypatch.setattr(settings, "jwt_secret_key", secret)
    monkeypatch.setattr(settings, "jwt_issuer", "unit-test-issuer")
    monkeypatch.setattr(settings, "worker_jwt_audience", "worker-test-audience")
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    app = FastAPI()
    app.include_router(worker_router)

    def override_db():
        try:
            yield db
        finally:
            database_module.clear_tenant_context(db)

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).post(
        "/authz/v1/workers/recheck",
        headers={"Authorization": f"Bearer {_jwt(secret, 'worker-pool')}"},
        json={"job_id": "unknown-job", "action_key": "ideas.read"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "WORKER_WORKSPACE_REQUIRED"


def test_worker_recheck_tu_choi_job_khac_workspace_tren_token(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    other_workspace = Workspace(id="ws-other", name="Không gian B", slug="ws-other", status="ACTIVE")
    db.add(other_workspace)
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    grant = WorkerAuthService.issue_grant(
        db, _actor(db, workspace, "member-author"), job_id="job-ws-bound",
        target_resource=resource.id, allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.commit()

    secret = "test-only-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()
    monkeypatch.setattr(settings, "jwt_secret_key", secret)
    monkeypatch.setattr(settings, "jwt_issuer", "unit-test-issuer")
    monkeypatch.setattr(settings, "worker_jwt_audience", "worker-test-audience")
    app = FastAPI()
    app.include_router(worker_router)

    def override_db():
        try:
            yield db
        finally:
            database_module.clear_tenant_context(db)

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).post(
        "/authz/v1/workers/recheck",
        headers={"Authorization": f"Bearer {_jwt(secret, 'worker-pool', workspace_id=other_workspace.id)}"},
        json={"job_id": grant.job_id, "action_key": "ideas.read"},
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is False
    assert response.json()["workspace_id"] is None
    denied_audit = db.query(AuthorizationAuditEvent).filter_by(
        workspace_id=other_workspace.id, actor_type="WORKER", decision="DENY",
    ).one()
    assert denied_audit.workspace_id == other_workspace.id


def test_worker_recheck_gan_tenant_truoc_query_va_duy_tri_sau_commit(du_lieu_rbac, monkeypatch):
    db, _, workspace, _, resource, _ = du_lieu_rbac
    monkeypatch.setattr(settings, "worker_jwt_subject", "worker-pool")
    grant = WorkerAuthService.issue_grant(
        db, _actor(db, workspace, "member-author"), job_id="job-tenant-hook",
        target_resource=resource.id, allowed_actions=["ideas.read"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.commit()

    secret = "test-only-" + hashlib.sha256(str(time.time_ns()).encode()).hexdigest()
    monkeypatch.setattr(settings, "jwt_secret_key", secret)
    monkeypatch.setattr(settings, "jwt_issuer", "unit-test-issuer")
    monkeypatch.setattr(settings, "worker_jwt_audience", "worker-test-audience")
    app = FastAPI()
    app.include_router(worker_router)
    query_count = 0
    hook_calls = []
    original_query = db.query

    def query_with_tenant(*args, **kwargs):
        nonlocal query_count
        query_count += 1
        assert get_tenant_context() == workspace.id
        assert db.info.get("baha_auth.trusted_workspace_id") == workspace.id
        return original_query(*args, **kwargs)

    monkeypatch.setattr(db, "query", query_with_tenant)
    original_commit = db.commit

    class FakeConnection:
        dialect = SimpleNamespace(name="postgresql")

        def execute(self, statement, parameters):
            hook_calls.append((str(statement), parameters))

    def commit_with_context_hook():
        original_commit()
        assert get_tenant_context() == workspace.id
        assert db.info.get("baha_auth.trusted_workspace_id") == workspace.id
        database_module._apply_postgres_tenant_context(db, None, FakeConnection())

    monkeypatch.setattr(db, "commit", commit_with_context_hook)

    def override_db():
        try:
            yield db
        finally:
            database_module.clear_tenant_context(db)

    app.dependency_overrides[get_db] = override_db
    response = TestClient(app).post(
        "/authz/v1/workers/recheck",
        headers={"Authorization": f"Bearer {_jwt(secret, 'worker-pool', workspace_id=workspace.id)}"},
        json={"job_id": grant.job_id, "action_key": "ideas.read"},
    )
    assert response.status_code == 200
    assert response.json()["allowed"] is True
    assert query_count > 0
    assert hook_calls
    assert "baha.current_workspace_id" in hook_calls[0][0]
    assert hook_calls[0][1] == {"workspace_id": workspace.id}


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
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-pool",
        expected_workspace_id=workspace.id,
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
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-pool",
        expected_workspace_id=workspace.id,
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
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-project-pool",
        expected_workspace_id=workspace.id,
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
        db, job_id=grant.job_id, action_key="ideas.read", worker_subject="worker-project-pool",
        expected_workspace_id=workspace.id,
    )
    assert denied.allowed is False
    assert denied.workspace_id is None
    assert denied.target_resource is None
    assert denied.artifact_version is None
    assert denied.content_hash is None
    assert denied.policy_version is None
