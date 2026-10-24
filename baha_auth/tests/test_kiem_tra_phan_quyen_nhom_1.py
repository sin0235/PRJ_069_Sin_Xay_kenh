"""Kiểm thử hồi quy cho danh tính, phạm vi, tài nguyên, dữ liệu và nhật ký."""
import uuid
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from baha_auth.src.api.evaluate_router import evaluate_access
from baha_auth.src.api.role_router import invite_member
from baha_auth.src.main import app
from baha_auth.src.models.entities import (
    AuthorizationAuditEvent,
    ApprovalPolicy,
    ApprovalRun,
    BusinessResource,
    DelegatedJobGrant,
    Delegation,
    GlobalUser,
    Membership,
    OrgAssignment,
    OrgUnit,
    Permission,
    Role,
    RoleAssignment,
    ResourceGrant,
)
from baha_auth.src.policy.evaluator import ActorContext, ResourceContext, evaluate_permission
from baha_auth.src.schemas.contracts import EvaluateRequest, MemberInviteRequest
from baha_auth.src.services.danh_tinh_service import load_actor
from baha_auth.src.services.org_service import OrgService
from baha_auth.src.services.role_service import RoleService
from baha_auth.src.services.tenant_service import TenantService
from baha_auth.src.xac_minh_danh_tinh import InvalidBearerToken, verify_bearer_token


def _actor(user_id, workspace_id, membership_id, roles=(), teams=(), departments=()):
    return ActorContext(
        user_id=user_id,
        workspace_id=workspace_id,
        membership_id=membership_id,
        membership_status="ACTIVE",
        roles=list(roles),
        department_ids=list(departments),
        team_ids=list(teams),
    )


def _jwt(payload, alg="HS256", secret="unit-test-key"):
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    header = encode(json.dumps({"alg": alg}, separators=(",", ":")).encode())
    claims = encode(json.dumps(payload, separators=(",", ":"), allow_nan=True).encode())
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{claims}.{encode(signature)}"


def test_header_gia_danh_khong_xac_thuc_duoc_nguoi_dung(multi_tenant_fixture):
    f = multi_tenant_fixture
    with TestClient(app) as client:
        response = client.post(
            "/authz/v1/org/units",
            headers={"X-Workspace-Id": f["ws_a"].id, "X-User-Id": f["user_a_owner"].id},
            json={"name": "Đơn vị giả danh", "type": "DEPARTMENT"},
        )
    assert response.status_code == 401


def test_quyen_nhom_khong_lan_sang_nhom_khac(multi_tenant_fixture):
    f = multi_tenant_fixture
    team_1 = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="TEAM", name="Nhóm một")
    team_2 = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="TEAM", name="Nhóm hai")
    actor = _actor(
        f["user_a_member"].id,
        f["ws_a"].id,
        f["m_a_member"].id,
        roles=[{"role_code": "TEAM_LEAD", "scope_type": "TEAM", "scope_id": team_1.id, "is_active": True}],
        teams=[team_1.id, team_2.id],
    )
    assert evaluate_permission(actor, "ideas.read", ResourceContext(f["ws_a"].id, org_unit_id=team_1.id)).allowed
    assert not evaluate_permission(actor, "ideas.read", ResourceContext(f["ws_a"].id, org_unit_id=team_2.id)).allowed


def test_het_han_va_vai_tro_bi_vo_hieu_khong_duoc_cho_phep():
    now = datetime.now(timezone.utc)
    actor = _actor(
        "nguoi-dung",
        "khong-gian",
        "thanh-vien",
        roles=[
            {"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True, "valid_until": now - timedelta(seconds=1)},
            {"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True, "role_status": "REVOKED"},
        ],
    )
    assert not evaluate_permission(actor, "workspace.read").allowed


def test_tu_duyet_chi_duoc_phep_khi_bat_co_va_dung_ca_hai_csdlt_e2e(monkeypatch):
    actor = _actor(
        "nguoi-tao", "khong-gian", "thanh-vien",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
    )
    resource = ResourceContext("khong-gian", resource_id="storyboard", creator_id="nguoi-tao")
    for name in ("BAHA_AUTH_APP_ENV", "BAHA_AUTH_ALLOW_SELF_APPROVAL_IN_TEST", "DATABASE_URL", "BAHA_AUTH_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    assert evaluate_permission(actor, "media.approve", resource).reason_code == "SELF_FINAL_APPROVAL_DENIED"

    monkeypatch.setenv("BAHA_AUTH_APP_ENV", "test")
    monkeypatch.setenv("BAHA_AUTH_ALLOW_SELF_APPROVAL_IN_TEST", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sin_content_e2e_test.db")
    monkeypatch.setenv("BAHA_AUTH_DATABASE_URL", "sqlite:///./baha_auth_e2e_test.db")
    assert evaluate_permission(actor, "media.approve", resource).allowed

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sin_content_offline.db")
    assert evaluate_permission(actor, "media.approve", resource).reason_code == "SELF_FINAL_APPROVAL_DENIED"


def test_truong_nhom_khong_cap_vai_tro_vuot_nhom(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    team_1 = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="TEAM", name="Nhóm cấp quyền")
    team_2 = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="TEAM", name="Nhóm đích")
    grantor = f["m_a_member"]
    grantee_user = GlobalUser(
        id=str(uuid.uuid4()), email=f"nhan-vien-{uuid.uuid4().hex[:8]}@example.test"
    )
    grantee = Membership(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, user_id=grantee_user.id)
    db.add_all([team_1, team_2, grantee_user, grantee])
    db.flush()
    db.add_all([
        OrgAssignment(workspace_id=f["ws_a"].id, membership_id=grantor.id, org_unit_id=team_1.id),
        OrgAssignment(workspace_id=f["ws_a"].id, membership_id=grantee.id, org_unit_id=team_1.id),
        RoleAssignment(
            workspace_id=f["ws_a"].id,
            membership_id=grantor.id,
            role_id=f["roles"]["TEAM_LEAD"].id,
            scope_type="TEAM",
            scope_id=team_1.id,
            status="ACTIVE",
        ),
    ])
    db.commit()
    with pytest.raises(ValueError, match="GRANT_SCOPE"):
        RoleService.assign_role(
            db,
            f["ws_a"].id,
            grantor_membership_id=grantor.id,
            grantee_membership_id=grantee.id,
            role_code="RESEARCHER",
            scope_type="TEAM",
            scope_id=team_2.id,
        )


def test_owner_khong_the_cap_vai_tro_nen_tang(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    with pytest.raises(ValueError, match="UNAUTHORIZED_ROLE_GRANT"):
        RoleService.assign_role(
            db,
            f["ws_a"].id,
            grantor_membership_id=f["m_a_owner"].id,
            grantee_membership_id=f["m_a_member"].id,
            role_code="PLATFORM_OPS",
        )


def test_thu_hoi_khong_de_lai_owner_het_han(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    role = f["roles"]["WORKSPACE_OWNER"]
    expired_owner_user_id = str(uuid.uuid4())
    user = GlobalUser(id=expired_owner_user_id, email=f"owner-het-han-{uuid.uuid4().hex[:8]}@example.test")
    member = Membership(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, user_id=user.id)
    expired = RoleAssignment(
        workspace_id=f["ws_a"].id,
        membership_id=member.id,
        role_id=role.id,
        scope_type="WORKSPACE",
        valid_until=datetime.now(timezone.utc) - timedelta(days=1),
        status="ACTIVE",
    )
    db.add_all([user, member, expired])
    db.commit()
    current_owner = db.query(RoleAssignment).filter(
        RoleAssignment.membership_id == f["m_a_owner"].id,
        RoleAssignment.role_id == role.id,
    ).one()
    with pytest.raises(ValueError, match="LAST_OWNER_PROTECTION_VIOLATION"):
        RoleService.revoke_role(db, f["ws_a"].id, f["m_a_owner"].id, current_owner.id)


def test_thu_hoi_owner_het_han_khong_bi_chan(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    expired = RoleAssignment(
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_member"].id,
        role_id=f["roles"]["WORKSPACE_OWNER"].id,
        scope_type="WORKSPACE",
        valid_until=datetime.now(timezone.utc) - timedelta(days=1),
        status="ACTIVE",
    )
    db.add(expired)
    db.commit()
    assert RoleService.revoke_role(db, f["ws_a"].id, f["m_a_owner"].id, expired.id)


def test_doc_tai_nguyen_hop_le_va_chan_danh_sach_khong_co_quyen(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    owner = _actor(
        f["user_a_owner"].id,
        f["ws_a"].id,
        f["m_a_owner"].id,
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
    )
    actor_without_roles = _actor(f["user_a_member"].id, f["ws_a"].id, f["m_a_member"].id)
    assert TenantService.get_resource(db, owner, f["res_a1"].id) is not None
    assert TenantService.list_resources(db, actor_without_roles) == []


def test_cap_nhat_tai_nguyen_can_quyen_va_url_that_phai_fail_closed(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    actor_without_roles = _actor(f["user_a_member"].id, f["ws_a"].id, f["m_a_member"].id)
    owner = _actor(
        f["user_a_owner"].id,
        f["ws_a"].id,
        f["m_a_owner"].id,
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
    )
    assert not TenantService.update_resource(db, actor_without_roles, f["res_a1"].id, "Tiêu đề trái phép")
    db.refresh(f["res_a1"])
    assert db.query(BusinessResource).filter(BusinessResource.id == f["res_a1"].id).one().title == "Chiến lược A"
    assert TenantService.get_asset_download_url(db, owner, f["res_a1"].id) is None
    reader = _actor(
        f["user_a_member"].id,
        f["ws_a"].id,
        f["m_a_member"].id,
        roles=[{"role_code": "RESEARCHER", "scope_type": "WORKSPACE", "is_active": True}],
    )
    assert not evaluate_permission(reader, "ideas.read", ResourceContext(f["ws_a"].id, resource_id=f["res_a1"].id, owner_id=f["user_a_owner"].id)).allowed
    assert TenantService.get_asset_download_url(db, reader, f["res_a1"].id) is None


def test_api_danh_gia_tu_tra_thuoc_tinh_tai_nguyen_tu_co_so_du_lieu(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    owner = _actor(
        f["user_a_owner"].id,
        f["ws_a"].id,
        f["m_a_owner"].id,
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
    )
    result = evaluate_access(
        EvaluateRequest(action_key="ideas.read", resource_id="khong-ton-tai"),
        owner,
        db,
    )
    assert result.allowed is False


def test_org_assignment_khong_the_tren_tenant_khac(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    org_b = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_b"].id, type="TEAM", name="Nhóm tenant B")
    db.add(org_b)
    db.commit()
    db.add(OrgAssignment(workspace_id=f["ws_a"].id, membership_id=f["m_a_member"].id, org_unit_id=org_b.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_khoa_ngoai_ngan_resource_va_delegation_cheo_tenant(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    db.add(BusinessResource(
        id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, owner_id=f["user_b_owner"].id,
        creator_id=f["user_a_owner"].id, title="Chủ sở hữu khác tenant",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_khoa_ngoai_ngan_run_va_worker_gan_resource_khac_tenant(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    policy = ApprovalPolicy(
        workspace_id=f["ws_a"].id,
        stages_json='[{"stage_key":"TEAM","allowed_role":"TEAM_LEAD"}]',
        status="ACTIVE",
    )
    db.add(policy)
    db.flush()
    db.add(ApprovalRun(
        workspace_id=f["ws_a"].id,
        artifact_type="IDEA",
        artifact_id=f["res_b1"].id,
        artifact_version=1,
        content_hash="a" * 64,
        policy_id=policy.id,
        created_by=f["m_a_owner"].id,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(DelegatedJobGrant(
        workspace_id=f["ws_a"].id,
        job_id=f"cross-tenant-{uuid.uuid4().hex}",
        initiating_membership_id=f["m_a_owner"].id,
        target_resource=f["res_b1"].id,
        target_artifact_version=1,
        target_content_hash="b" * 64,
        worker_subject="worker-unit-test",
        allowed_actions_json='["ideas.read"]',
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        status="ACTIVE",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(Delegation(
        workspace_id=f["ws_a"].id,
        grantor_membership_id=f["m_b_owner"].id,
        grantee_membership_id=f["m_a_member"].id,
        grant_spec_json='{"allowed_actions":["ideas.read"]}',
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status="ACTIVE",
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    permission = Permission(action_key=f"test.read.{uuid.uuid4().hex}")
    db.add(permission)
    db.commit()
    db.add(ResourceGrant(
        workspace_id=f["ws_a"].id,
        resource_type="IDEA",
        resource_id=str(uuid.uuid4()),
        membership_id=f["m_b_owner"].id,
        permission_id=permission.id,
    ))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cap_thu_hoi_quyen_ghi_audit_va_event_khong_sua_xoa_duoc(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    assignment = RoleService.assign_role(
        db,
        f["ws_a"].id,
        grantor_membership_id=f["m_a_owner"].id,
        grantee_membership_id=f["m_a_member"].id,
        role_code="STRATEGIST",
    )
    assert RoleService.revoke_role(db, f["ws_a"].id, f["m_a_owner"].id, assignment.id)
    events = db.query(AuthorizationAuditEvent).filter(
        AuthorizationAuditEvent.action_key == "roles.assign",
        AuthorizationAuditEvent.workspace_id == f["ws_a"].id,
    ).all()
    assert [event.decision for event in events].count("ALLOW") >= 2
    event = events[0]
    event.internal_reason = "Đã bị sửa"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_quyen_du_an_chi_hieu_luc_tren_du_an_duoc_gan():
    actor = _actor(
        "nguoi-dung", "khong-gian", "thanh-vien",
        roles=[{"role_code": "RESEARCHER", "scope_type": "PROJECT", "scope_id": "du-an-a", "is_active": True}],
    )
    assert evaluate_permission(actor, "ideas.read", ResourceContext("khong-gian", project_id="du-an-a")).allowed
    assert not evaluate_permission(actor, "ideas.read", ResourceContext("khong-gian", project_id="du-an-b")).allowed
    workspace_grant = _actor(
        "nguoi-dung", "khong-gian", "thanh-vien",
        roles=[{"role_code": "RESEARCHER", "scope_type": "WORKSPACE", "is_active": True}],
    )
    assert not evaluate_permission(workspace_grant, "ideas.read", ResourceContext("khong-gian", project_id="du-an-a")).allowed


def test_thieu_dinh_danh_tenant_tin_cay_thi_tu_choi():
    actor = _actor("nguoi-dung", "", "thanh-vien", roles=[
        {"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}
    ])
    assert not evaluate_permission(actor, "workspace.read").allowed


def test_truong_nhom_moi_thanh_vien_cung_nhom_va_tu_choi_nhom_khac(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    team_one = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="TEAM", name="Nhóm một")
    team_two = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="TEAM", name="Nhóm hai")
    db.add_all([team_one, team_two])
    db.flush()
    db.add_all([
        OrgAssignment(workspace_id=f["ws_a"].id, membership_id=f["m_a_member"].id, org_unit_id=team_one.id),
        RoleAssignment(
            workspace_id=f["ws_a"].id,
            membership_id=f["m_a_member"].id,
            role_id=f["roles"]["TEAM_LEAD"].id,
            scope_type="TEAM",
            scope_id=team_one.id,
            status="ACTIVE",
        ),
    ])
    db.commit()
    actor = load_actor(db, f["ws_a"].id, f["m_a_member"].id)

    payload_same_team = MemberInviteRequest(
        email="same-team@example.test", full_name="Same team", initial_role_code="RESEARCHER",
        scope_type="TEAM", scope_id=team_one.id,
    )
    invited = invite_member(payload_same_team, actor, db)
    assert invited.workspace_id == f["ws_a"].id
    assert db.query(OrgAssignment).filter(
        OrgAssignment.workspace_id == f["ws_a"].id,
        OrgAssignment.membership_id == invited.id,
        OrgAssignment.org_unit_id == team_one.id,
    ).count() == 1

    before_users = db.query(GlobalUser).count()
    before_memberships = db.query(Membership).filter(Membership.workspace_id == f["ws_a"].id).count()
    payload_foreign_team = MemberInviteRequest(
        email="other-team@example.test", full_name="Other team", initial_role_code="RESEARCHER",
        scope_type="TEAM", scope_id=team_two.id,
    )
    with pytest.raises(HTTPException):
        invite_member(payload_foreign_team, actor, db)
    db.expire_all()
    assert db.query(GlobalUser).filter(GlobalUser.email == "other-team@example.test").count() == 0
    assert db.query(Membership).filter(Membership.workspace_id == f["ws_a"].id).count() == before_memberships
    assert db.query(GlobalUser).count() == before_users
    assert db.query(AuthorizationAuditEvent).filter(
        AuthorizationAuditEvent.action_key == "members.invite",
        AuthorizationAuditEvent.decision == "DENY",
    ).count() == 1


def test_quan_ly_phong_ban_duoc_tao_don_vi_con_trong_phong(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    department = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="DEPARTMENT", name="Nội dung")
    other_department = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="DEPARTMENT", name="Tài chính")
    db.add_all([department, other_department])
    db.flush()
    db.add_all([
        OrgAssignment(workspace_id=f["ws_a"].id, membership_id=f["m_a_member"].id, org_unit_id=department.id),
        RoleAssignment(
            workspace_id=f["ws_a"].id,
            membership_id=f["m_a_member"].id,
            role_id=f["roles"]["DEPARTMENT_MANAGER"].id,
            scope_type="DEPARTMENT",
            scope_id=department.id,
            status="ACTIVE",
        ),
    ])
    db.commit()
    actor = load_actor(db, f["ws_a"].id, f["m_a_member"].id)
    child = OrgService.create_org_unit(
        db, f["ws_a"].id, name="Kịch bản", unit_type="TEAM", parent_id=department.id, actor=actor
    )
    assert child.parent_id == department.id
    with pytest.raises(ValueError, match="UNAUTHORIZED_ORG_SCOPE"):
        OrgService.create_org_unit(
            db, f["ws_a"].id, name="Không được phép", unit_type="TEAM", parent_id=other_department.id, actor=actor
        )


def test_khong_ghep_quyen_cap_vai_tro_va_scope_tu_hai_grant_khac_nhau(db, multi_tenant_fixture):
    f = multi_tenant_fixture
    team = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="TEAM", name="Nhóm một")
    department = OrgUnit(id=str(uuid.uuid4()), workspace_id=f["ws_a"].id, type="DEPARTMENT", name="Phòng hai")
    db.add_all([team, department])
    db.flush()
    db.add_all([
        OrgAssignment(workspace_id=f["ws_a"].id, membership_id=f["m_a_member"].id, org_unit_id=team.id),
        OrgAssignment(workspace_id=f["ws_a"].id, membership_id=f["m_a_member"].id, org_unit_id=department.id),
        OrgAssignment(workspace_id=f["ws_a"].id, membership_id=f["m_a_owner"].id, org_unit_id=team.id),
        RoleAssignment(
            workspace_id=f["ws_a"].id,
            membership_id=f["m_a_member"].id,
            role_id=f["roles"]["TEAM_LEAD"].id,
            scope_type="TEAM",
            scope_id=team.id,
            status="ACTIVE",
        ),
        RoleAssignment(
            workspace_id=f["ws_a"].id,
            membership_id=f["m_a_member"].id,
            role_id=f["roles"]["EXECUTIVE"].id,
            scope_type="DEPARTMENT",
            scope_id=department.id,
            status="ACTIVE",
        ),
    ])
    db.commit()

    with pytest.raises(ValueError, match="UNAUTHORIZED_ROLE_GRANT|GRANT_SCOPE_NOT_AUTHORIZED"):
        RoleService.assign_role(
            db,
            f["ws_a"].id,
            grantor_membership_id=f["m_a_member"].id,
            grantee_membership_id=f["m_a_owner"].id,
            role_code="TEAM_LEAD",
            scope_type="TEAM",
            scope_id=team.id,
        )


@pytest.mark.parametrize(
    "payload,algorithm",
    [
        ({"sub": "user", "iss": "issuer", "aud": "aud", "exp": float("nan")}, "HS256"),
        ({"sub": "user", "iss": "issuer", "aud": "aud", "exp": float("inf")}, "HS256"),
        ({"sub": "user", "iss": "issuer", "aud": "aud"}, "HS256"),
        ({"sub": "user", "iss": "issuer", "aud": "other", "exp": 4_000_000_000}, "HS256"),
        ({"sub": "user", "iss": "issuer", "aud": "aud", "exp": 4_000_000_000}, "none"),
    ],
)
def test_token_sai_han_chi_or_audience_thuat_toan_deu_bi_tu_choi(payload, algorithm):
    with pytest.raises(InvalidBearerToken):
        verify_bearer_token(
            _jwt(payload, alg=algorithm),
            secret="unit-test-key",
            issuer="issuer",
            audience="aud",
        )
