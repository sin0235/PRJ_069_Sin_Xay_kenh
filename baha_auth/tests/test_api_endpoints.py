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


def _token(subject, audience, workspace_id=None):
    header = _segment({"alg": "HS256", "typ": "JWT"})
    claims = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": audience,
        "exp": int(time.time()) + 300,
    }
    if workspace_id is not None:
        claims["workspace_id"] = workspace_id
    payload = _segment(claims)
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


def _worker_headers(workspace_id):
    return {"Authorization": f"Bearer {_token(settings.worker_jwt_subject, settings.worker_jwt_audience, workspace_id)}"}


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
        headers=_worker_headers(f["ws_a"].id),
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
        headers=_worker_headers(f["ws_a"].id),
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
