"""Kiểm thử bảo mật bằng hai cơ sở dữ liệu SQLite riêng biệt chỉ trong RAM."""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

TEST_DATABASE_URL = "sqlite:///file:sin_content_rbac_test?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = (
    "sqlite:///file:baha_auth_rbac_test?mode=memory&cache=shared&uri=true"
)
os.environ["BAHA_AUTH_JWT_SECRET"] = "kiem-thu-bang-khoa-gia-lap"
os.environ["BAHA_AUTH_JWT_ISSUER"] = "kiem-thu-nha-cung-cap"
os.environ["BAHA_AUTH_JWT_AUDIENCE"] = "sin-content-test"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.auth.tenancy import TenantContext, authorize_action, authorize_resource
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models.entities import (
    AuditEvent, BrandBriefVersion, IdeaCard, Membership, ScriptDraftVersion, User, Workspace,
)
from baha_auth.src.database import Base as AuthBase, SessionLocal as AuthSessionLocal, engine as AuthEngine
from baha_auth.src.models.entities import (
    GlobalUser,
    Membership as AuthMembership,
    OrgAssignment,
    OrgUnit,
    Role as AuthRole,
    RoleAssignment,
    Workspace as AuthWorkspace,
)
from baha_auth.src.services.danh_tinh_service import load_actor_for_user
from baha_auth.src.policy.registry import registry
from src.modules.scripts.script_service import script_service


client = TestClient(app)


def tao_bearer(user_id: str) -> str:
    def encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = encode({"alg": "HS256", "typ": "JWT"})
    claims = encode({
        "sub": user_id,
        "iss": os.environ["BAHA_AUTH_JWT_ISSUER"],
        "aud": os.environ["BAHA_AUTH_JWT_AUDIENCE"],
        "exp": int(time.time()) + 300,
    })
    signing_input = f"{header}.{claims}".encode("ascii")
    signature = hmac.new(
        os.environ["BAHA_AUTH_JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{header}.{claims}.{encoded_signature}"


def lay_role(db, code: str):
    role = db.query(AuthRole).filter(AuthRole.code == code).first()
    if role is None:
        role = AuthRole(code=code, name=code, workspace_id=None, is_template=True, status="ACTIVE")
        db.add(role)
        db.flush()
    return role


@pytest.fixture
def du_lieu_workspace_cu():
    Base.metadata.create_all(bind=engine)
    AuthBase.metadata.create_all(bind=AuthEngine)

    workspace_id = str(uuid.uuid4())
    legacy_user_id = str(uuid.uuid4())
    canonical_user_id = str(uuid.uuid4())
    own_user_id = str(uuid.uuid4())
    guest_user_id = str(uuid.uuid4())
    workspace_owner_user_id = str(uuid.uuid4())
    team_one = str(uuid.uuid4())
    team_two = str(uuid.uuid4())
    team_membership_id = str(uuid.uuid4())
    own_membership_id = str(uuid.uuid4())
    guest_membership_id = str(uuid.uuid4())
    workspace_owner_membership_id = str(uuid.uuid4())
    slug = f"rbac-{uuid.uuid4().hex[:8]}"

    with SessionLocal() as db:
        db.add(Workspace(id=workspace_id, name="Workspace kiểm thử", slug=slug))
        db.add(User(id=legacy_user_id, email=f"legacy-{legacy_user_id}@test.invalid", hashed_password="mock"))
        db.flush()
        db.add(Membership(workspace_id=workspace_id, user_id=legacy_user_id, role="owner"))
        db.commit()

    with AuthSessionLocal() as db:
        db.add(AuthWorkspace(id=workspace_id, name="Workspace kiểm thử", slug=f"auth-{slug}", status="ACTIVE"))
        db.add_all([
            GlobalUser(id=canonical_user_id, email=f"canonical-{canonical_user_id}@test.invalid", status="ACTIVE"),
            GlobalUser(id=own_user_id, email=f"own-{own_user_id}@test.invalid", status="ACTIVE"),
            GlobalUser(id=guest_user_id, email=f"guest-{guest_user_id}@test.invalid", status="ACTIVE"),
            GlobalUser(id=workspace_owner_user_id, email=f"workspace-owner-{workspace_owner_user_id}@test.invalid", status="ACTIVE"),
        ])
        db.flush()
        db.add_all([
            AuthMembership(
                id=team_membership_id,
                workspace_id=workspace_id,
                user_id=canonical_user_id,
                status="ACTIVE",
            ),
            AuthMembership(
                id=own_membership_id,
                workspace_id=workspace_id,
                user_id=own_user_id,
                status="ACTIVE",
            ),
            AuthMembership(
                id=guest_membership_id,
                workspace_id=workspace_id,
                user_id=guest_user_id,
                status="ACTIVE",
            ),
            AuthMembership(
                id=workspace_owner_membership_id,
                workspace_id=workspace_id,
                user_id=workspace_owner_user_id,
                status="ACTIVE",
            ),
            OrgUnit(id=team_one, workspace_id=workspace_id, type="TEAM", name="Nhóm 1", status="ACTIVE"),
            OrgUnit(id=team_two, workspace_id=workspace_id, type="TEAM", name="Nhóm 2", status="ACTIVE"),
        ])
        db.flush()
        db.add_all([
            OrgAssignment(workspace_id=workspace_id, membership_id=team_membership_id, org_unit_id=team_one),
            OrgAssignment(workspace_id=workspace_id, membership_id=team_membership_id, org_unit_id=team_two),
        ])
        db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=team_membership_id,
            role_id=lay_role(db, "TEAM_LEAD").id,
            scope_type="TEAM",
            scope_id=team_one,
            status="ACTIVE",
        ))
        db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=own_membership_id,
            role_id=lay_role(db, "WORKSPACE_OWNER").id,
            scope_type="OWN",
            scope_id=own_user_id,
            status="ACTIVE",
        ))
        db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=guest_membership_id,
            role_id=lay_role(db, "GUEST").id,
            scope_type="WORKSPACE",
            scope_id=workspace_id,
            status="ACTIVE",
        ))
        db.add(RoleAssignment(
            workspace_id=workspace_id,
            membership_id=workspace_owner_membership_id,
            role_id=lay_role(db, "WORKSPACE_OWNER").id,
            scope_type="WORKSPACE",
            scope_id=workspace_id,
            status="ACTIVE",
        ))
        db.commit()

    return {
        "workspace_id": workspace_id,
        "legacy_user_id": legacy_user_id,
        "canonical_user_id": canonical_user_id,
        "own_user_id": own_user_id,
        "guest_user_id": guest_user_id,
        "workspace_owner_user_id": workspace_owner_user_id,
        "team_one": team_one,
        "team_two": team_two,
    }


def tao_context(workspace_id: str, user_id: str):
    auth_db = AuthSessionLocal()
    actor = load_actor_for_user(auth_db, workspace_id=workspace_id, user_id=user_id)
    assert actor is not None
    return TenantContext(
        workspace_id=workspace_id,
        user_id=user_id,
        actor=actor,
        auth_db=auth_db,
        request_id=str(uuid.uuid4()),
    )


def test_header_gia_danh_khong_mo_rong_quyen_canonical(du_lieu_workspace_cu):
    """Token TEAM_LEAD không lấy được quyền owner ghi trong Membership legacy."""
    response = client.get(
        "/v1/briefs",
        headers={
            "Authorization": f"Bearer {tao_bearer(du_lieu_workspace_cu['canonical_user_id'])}",
            "X-Workspace-Id": du_lieu_workspace_cu["workspace_id"],
            "X-User-Id": du_lieu_workspace_cu["legacy_user_id"],
        },
    )

    assert response.status_code == 403
    with SessionLocal() as db:
        assert db.query(BrandBriefVersion).filter(
            BrandBriefVersion.workspace_id == du_lieu_workspace_cu["workspace_id"]
        ).count() == 0


def test_api_dung_danh_tinh_va_grant_canonical_thuc_te(du_lieu_workspace_cu):
    response = client.get(
        "/v1/workspaces",
        headers={
            "Authorization": f"Bearer {tao_bearer(du_lieu_workspace_cu['workspace_owner_user_id'])}",
            "X-Workspace-Id": du_lieu_workspace_cu["workspace_id"],
            "X-User-Id": du_lieu_workspace_cu["legacy_user_id"],
        },
    )
    assert response.status_code == 200
    assert [workspace["id"] for workspace in response.json()] == [du_lieu_workspace_cu["workspace_id"]]


def test_workspace_owner_tao_duoc_brief_draft_bang_action_brief_edit(du_lieu_workspace_cu):
    response = client.post(
        "/v1/briefs",
        headers={
            "Authorization": f"Bearer {tao_bearer(du_lieu_workspace_cu['workspace_owner_user_id'])}",
            "X-Workspace-Id": du_lieu_workspace_cu["workspace_id"],
        },
        json={
            "brand_name": "Thương hiệu kiểm thử",
            "objective": "Tạo bản nháp brief để kiểm tra quyền.",
            "voice_description": "Giọng rõ ràng, thân thiện và chuyên nghiệp.",
            "current_audience": "Người đang theo dõi nội dung hiện tại.",
            "target_audience": "Người muốn tìm hiểu chủ đề này.",
            "topics_included": ["hướng dẫn"],
            "topics_excluded": ["khẳng định chưa kiểm chứng"],
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    assert response.json()["workspace_id"] == du_lieu_workspace_cu["workspace_id"]


def test_guest_khong_tao_duoc_brief(du_lieu_workspace_cu):
    response = client.post(
        "/v1/briefs",
        headers={
            "Authorization": f"Bearer {tao_bearer(du_lieu_workspace_cu['guest_user_id'])}",
            "X-Workspace-Id": du_lieu_workspace_cu["workspace_id"],
        },
        json={
            "brand_name": "Thương hiệu kiểm thử",
            "objective": "Tạo bản nháp brief để kiểm tra quyền.",
            "voice_description": "Giọng rõ ràng, thân thiện và chuyên nghiệp.",
            "current_audience": "Người đang theo dõi nội dung hiện tại.",
            "target_audience": "Người muốn tìm hiểu chủ đề này.",
            "topics_included": ["hướng dẫn"],
            "topics_excluded": ["khẳng định chưa kiểm chứng"],
        },
    )

    assert response.status_code == 403
    with SessionLocal() as db:
        assert db.query(BrandBriefVersion).filter(
            BrandBriefVersion.workspace_id == du_lieu_workspace_cu["workspace_id"]
        ).count() == 0


def test_brief_o_workspace_khac_va_id_khong_ton_tai_cung_tra_404(du_lieu_workspace_cu):
    workspace_id = du_lieu_workspace_cu["workspace_id"]
    foreign_workspace_id = str(uuid.uuid4())
    foreign_brief_id = str(uuid.uuid4())
    unknown_brief_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(Workspace(
            id=foreign_workspace_id,
            name="Workspace riêng tư",
            slug=f"foreign-{uuid.uuid4().hex[:8]}",
        ))
        db.add(BrandBriefVersion(
            id=foreign_brief_id,
            workspace_id=foreign_workspace_id,
            version=1,
            brand_name="Thương hiệu riêng tư",
            objective="Thông tin không thuộc workspace hiện tại.",
            voice_description="Không công khai.",
            current_audience="Đối tượng hiện tại.",
            target_audience="Đối tượng mục tiêu.",
        ))
        db.commit()
        audit_count_before = db.query(AuditEvent).count()

    headers = {
        "Authorization": f"Bearer {tao_bearer(du_lieu_workspace_cu['workspace_owner_user_id'])}",
        "X-Workspace-Id": workspace_id,
    }
    foreign_response = client.get(f"/v1/briefs/{foreign_brief_id}", headers=headers)
    unknown_response = client.get(f"/v1/briefs/{unknown_brief_id}", headers=headers)

    assert foreign_response.status_code == unknown_response.status_code == 404
    foreign_payload = foreign_response.json()
    unknown_payload = unknown_response.json()
    foreign_payload.pop("correlation_id", None)
    unknown_payload.pop("correlation_id", None)
    assert foreign_payload == unknown_payload
    assert foreign_brief_id not in foreign_response.text
    assert "Thương hiệu riêng tư" not in foreign_response.text
    with SessionLocal() as db:
        assert db.query(AuditEvent).count() == audit_count_before
        assert db.query(BrandBriefVersion).filter_by(
            id=foreign_brief_id, workspace_id=foreign_workspace_id
        ).count() == 1


def test_workspace_owner_khong_duyet_script_khi_thieu_tai_nguyen_tin_cay_va_nguoi_tao(
    du_lieu_workspace_cu, monkeypatch
):
    workspace_id = du_lieu_workspace_cu["workspace_id"]
    script_id = str(uuid.uuid4())
    idea_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(IdeaCard(
            id=idea_id,
            workspace_id=workspace_id,
            brief_version_id=str(uuid.uuid4()),
            title="Ý tưởng kiểm thử",
            target_need="Nhu cầu kiểm thử",
            hook="Mở đầu kiểm thử",
            content_angle="Góc nội dung kiểm thử",
        ))
        db.add(ScriptDraftVersion(
            id=script_id,
            workspace_id=workspace_id,
            idea_id=idea_id,
            title="Kịch bản kiểm thử",
            status="READY_FOR_REVIEW",
            hook_variants_json="[]",
            blocks_json="[]",
            claims_json="[]",
        ))
        db.commit()

    service_calls = []
    approve = script_service.approve_script

    def track_approve(*args, **kwargs):
        service_calls.append(True)
        return approve(*args, **kwargs)

    monkeypatch.setattr(script_service, "approve_script", track_approve)
    response = client.post(
        f"/v1/scripts/{script_id}/approve",
        headers={
            "Authorization": f"Bearer {tao_bearer(du_lieu_workspace_cu['workspace_owner_user_id'])}",
            "X-Workspace-Id": workspace_id,
        },
    )

    assert response.status_code == 403
    assert service_calls == []
    with SessionLocal() as db:
        script = db.query(ScriptDraftVersion).filter_by(id=script_id).one()
        assert script.status == "READY_FOR_REVIEW"
        assert script.approved_by_user_id is None
        assert script.approved_at is None
        assert db.query(AuditEvent).filter(
            AuditEvent.event_type == "SCRIPT_APPROVE",
            AuditEvent.details.contains(script_id),
        ).count() == 0


def test_grant_team_chi_cho_phep_nhom_duoc_gan_va_khong_cho_liet_ke_tenant(du_lieu_workspace_cu):
    """Grant nhóm 1 không thành quyền đọc nhóm 2 hoặc danh sách toàn tenant."""
    context = tao_context(du_lieu_workspace_cu["workspace_id"], du_lieu_workspace_cu["canonical_user_id"])
    try:
        authorize_resource(
            context,
            "brief.read",
            resource_type="brand_brief",
            resource_id=str(uuid.uuid4()),
            workspace_id=context.workspace_id,
            org_unit_id=du_lieu_workspace_cu["team_one"],
        )
        with pytest.raises(Exception) as denied:
            authorize_resource(
                context,
                "brief.read",
                resource_type="brand_brief",
                resource_id=str(uuid.uuid4()),
                workspace_id=context.workspace_id,
                org_unit_id=du_lieu_workspace_cu["team_two"],
            )
        assert getattr(denied.value, "status_code", None) == 403

        with pytest.raises(Exception) as unscoped:
            authorize_action(context, "brief.read")
        assert getattr(unscoped.value, "status_code", None) == 403
    finally:
        context.auth_db.close()


def test_thay_id_tai_nguyen_cung_tenant_khong_vuot_quyen_own(du_lieu_workspace_cu):
    """Một ID của đồng nghiệp trong cùng tenant không vượt assignment OWN."""
    context = tao_context(du_lieu_workspace_cu["workspace_id"], du_lieu_workspace_cu["own_user_id"])
    try:
        authorize_resource(
            context,
            "brief.read",
            resource_type="brand_brief",
            resource_id=str(uuid.uuid4()),
            workspace_id=context.workspace_id,
            owner_id=context.user_id,
        )
        with pytest.raises(Exception) as denied:
            authorize_resource(
                context,
                "brief.read",
                resource_type="brand_brief",
                resource_id=str(uuid.uuid4()),
                workspace_id=context.workspace_id,
                owner_id=du_lieu_workspace_cu["canonical_user_id"],
            )
        assert getattr(denied.value, "status_code", None) == 403
    finally:
        context.auth_db.close()


def test_thieu_cau_hinh_kho_rbac_thi_tu_choi(du_lieu_workspace_cu, monkeypatch):
    monkeypatch.delenv("BAHA_AUTH_DATABASE_URL", raising=False)
    response = client.get(
        "/v1/briefs",
        headers={
            "Authorization": f"Bearer {tao_bearer(du_lieu_workspace_cu['canonical_user_id'])}",
            "X-Workspace-Id": du_lieu_workspace_cu["workspace_id"],
            "X-User-Id": du_lieu_workspace_cu["legacy_user_id"],
        },
    )
    assert response.status_code == 503


def test_header_legacy_khong_the_tao_phien_dang_nhap(du_lieu_workspace_cu):
    response = client.get(
        "/v1/workspaces",
        headers={
            "X-Workspace-Id": du_lieu_workspace_cu["workspace_id"],
            "X-User-Id": du_lieu_workspace_cu["legacy_user_id"],
        },
    )
    assert response.status_code == 401


def test_moi_route_nghiep_vu_deu_khai_bao_action_rbac():
    """Không để sót route nghiệp vụ chỉ có xác thực hoặc không có guard."""
    bo_sot = []
    thieu_kiem_tra_resource = []
    action_chua_dang_ky = set()
    api_routes = []
    for mounted_route in app.routes:
        if isinstance(mounted_route, APIRoute):
            api_routes.append(mounted_route)
        else:
            # FastAPI mới bọc router đã include; đọc các route nguồn thay vì
            # kiểm tra wrapper để tránh coverage vacuous.
            api_routes.extend(
                route
                for route in getattr(getattr(mounted_route, "original_router", None), "routes", ())
                if isinstance(route, APIRoute)
            )

    for route in api_routes:
        if (
            not isinstance(route, APIRoute)
            or not route.path.startswith("/v1/")
            or route.path.startswith("/v1/platform/")
        ):
            continue
        stack = list(route.dependant.dependencies)
        actions = set()
        requires_resource = False
        while stack:
            dependency = stack.pop()
            call = dependency.call
            action = getattr(call, "required_action", None)
            if action:
                actions.add(action)
            actions.update(getattr(call, "required_actions", ()))
            requires_resource = requires_resource or getattr(
                call, "requires_resource_authorization", False
            )
            stack.extend(dependency.dependencies)
        if not actions:
            bo_sot.append(f"{','.join(sorted(route.methods or []))} {route.path}")
        action_chua_dang_ky.update(
            action for action in actions if not registry.is_action_registered(action)
        )
        if requires_resource and "authorize_resource" not in route.endpoint.__code__.co_names:
            thieu_kiem_tra_resource.append(
                f"{','.join(sorted(route.methods or []))} {route.path}"
            )

    assert api_routes
    assert bo_sot == []
    assert thieu_kiem_tra_resource == []
    assert action_chua_dang_ky <= {
        "evidence.import",
        "evidence.purge",
        "workspace.create",
        "media.create",
    }
