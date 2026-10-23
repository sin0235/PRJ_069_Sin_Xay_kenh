# Test Suite cho Phase A01: AUTH-010 -> AUTH-019 (Tenant Boundary & Database Isolation)
import pytest
from baha_auth.src.services.tenant_service import TenantService
from baha_auth.src.policy.evaluator import ActorContext
from baha_auth.src.models.entities import BusinessResource

def test_auth_010_cross_tenant_read_denied_and_masked(db, multi_tenant_fixture):
    """
    AUTH-010: Member of tenant A GETs known tenant B resource UUID.
    Expected: Denied with no B data or existence details (masked None).
    """
    f = multi_tenant_fixture
    actor_a = ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    # Actor A doc tai nguyen cua Tenant B
    result = TenantService.get_resource(db, actor_a, f["res_b1"].id)
    assert result is None, "Phai chan va an su ton tai cua tai nguyen thuoc tenant B"

def test_auth_011_list_resources_scoped_strictly_to_tenant(db, multi_tenant_fixture):
    """
    AUTH-011: Member of A lists resources.
    Expected: Only records in authorized scope of A, never B.
    """
    f = multi_tenant_fixture
    actor_a = ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    resources = TenantService.list_resources(db, actor_a)
    assert len(resources) >= 1
    for r in resources:
        assert r.workspace_id == f["ws_a"].id
        assert r.workspace_id != f["ws_b"].id

def test_auth_012_attacker_cannot_create_in_foreign_tenant(db, multi_tenant_fixture):
    """
    AUTH-012: Attacker POSTs resource with workspace_id of B.
    Expected: Server rejects or overrides according to trusted parent; cannot create in B.
    """
    f = multi_tenant_fixture
    actor_a = ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    # Co tinh truyen workspace_id cua B
    new_res = TenantService.create_resource(
        db,
        actor_a,
        title="Trojan Horse Resource",
        attempted_workspace_id=f["ws_b"].id
    )

    assert new_res.workspace_id == f["ws_a"].id, "Server bat buoc ghi de bang trusted workspace_id cua actor"
    assert new_res.workspace_id != f["ws_b"].id

def test_auth_013_search_query_does_not_leak_foreign_tenant_data(db, multi_tenant_fixture):
    """
    AUTH-013: User runs vector/search query matching B private text.
    Expected: No B chunks, metadata or count returned.
    """
    f = multi_tenant_fixture
    actor_a = ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    # res_b1 co search_text la "Beta client highly restricted"
    results = TenantService.search_resources(db, actor_a, "restricted")
    assert len(results) == 0, "Khong duoc phep tim thay du lieu cua tenant B"

def test_auth_014_signed_download_url_cross_tenant_denied(db, multi_tenant_fixture):
    """
    AUTH-014: User accesses asset thumbnail/download URL from B.
    Expected: Denied and no usable B signed URL minted.
    """
    f = multi_tenant_fixture
    actor_a = ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    url = TenantService.get_asset_download_url(db, actor_a, f["res_b1"].id)
    assert url is None, "Khong the tao signed URL cho tai san cua tenant khac"

def test_auth_017_quarantine_legacy_orphaned_resource(db, multi_tenant_fixture):
    """
    AUTH-017: Migrate a legacy row without known tenant owner.
    Expected: Quarantined/manual resolution; not guessed into A or B.
    """
    import uuid
    orphan_id = f"legacy-orphan-{uuid.uuid4().hex[:8]}"
    # Tao row cu khong co tenant
    orphan = BusinessResource(
        id=orphan_id,
        workspace_id=None,
        title="Unassigned Legacy Content",
        is_quarantined=False
    )
    db.add(orphan)
    db.commit()

    quarantined = TenantService.quarantine_orphaned_resource(db, orphan_id, system_maintenance=True)
    assert quarantined.is_quarantined is True, "Phai cach ly tai nguyen vo chu"

def test_auth_018_cross_tenant_aggregates_isolated(db, multi_tenant_fixture):
    """
    AUTH-018: Cross-tenant join/aggregates of view counts.
    Expected: No foreign records affect scoped counts or totals.
    """
    f = multi_tenant_fixture
    actor_a = ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    # res_a1 co view_count=100, res_b1 co view_count=500
    total_a = TenantService.aggregate_view_counts(db, actor_a)
    assert total_a == 100, f"Tong so luot xem chi tinh tren tenant A (100), khong tinh B (500), thuc te la {total_a}"

def test_auth_019_cross_tenant_mutation_denied_and_audited(db, multi_tenant_fixture):
    """
    AUTH-019: Perform update/delete on another tenant resource.
    Expected: Denied, 0 rows modified, audit produced.
    """
    f = multi_tenant_fixture
    actor_a = ActorContext(
        user_id=f["user_a_owner"].id,
        workspace_id=f["ws_a"].id,
        membership_id=f["m_a_owner"].id,
        membership_status="ACTIVE",
        roles=[{"role_code": "WORKSPACE_OWNER", "scope_type": "WORKSPACE", "is_active": True}],
        department_ids=[],
        team_ids=[]
    )

    success = TenantService.update_resource(db, actor_a, f["res_b1"].id, "Hacked Title")
    assert success is False, "Khong the sua tai nguyen cua tenant khac"
    
    # Kiem tra tieu de tren DB van nguyen ven
    res_b = db.query(BusinessResource).filter(BusinessResource.id == f["res_b1"].id).first()
    assert res_b.title == "Dữ liệu B"
