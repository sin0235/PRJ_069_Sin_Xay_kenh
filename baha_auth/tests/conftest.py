"""Bộ kiểm thử chỉ dùng SQLite trong RAM, không kết nối dịch vụ hoặc DB dự án."""

import os
import sys
import uuid
from pathlib import Path

import pytest


_RAM_DATABASE_URL = "sqlite:///:memory:"
os.environ["DATABASE_URL"] = _RAM_DATABASE_URL
os.environ["BAHA_AUTH_DATABASE_URL"] = _RAM_DATABASE_URL

_project_working_root = str(Path(__file__).resolve().parents[2])
if _project_working_root not in sys.path:
    sys.path.insert(0, _project_working_root)

from baha_auth.src.database import Base, SessionLocal, engine
from baha_auth.src.models.entities import (
    BusinessResource,
    GlobalUser,
    Membership,
    Role,
    RoleAssignment,
    Workspace,
)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    assert engine is not None
    assert engine.dialect.name == "sqlite"
    assert engine.url.database in (None, "", ":memory:")
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def multi_tenant_fixture(db):
    """Tạo hai tenant cùng dữ liệu kiểm thử cô lập trong bộ nhớ."""
    ws_a = Workspace(id=str(uuid.uuid4()), name="BAHA A", slug=f"baha-a-{uuid.uuid4().hex[:8]}")
    ws_b = Workspace(id=str(uuid.uuid4()), name="BAHA B", slug=f"baha-b-{uuid.uuid4().hex[:8]}")
    users = [
        GlobalUser(id=str(uuid.uuid4()), email=f"{label}-{uuid.uuid4().hex[:8]}@example.test")
        for label in ("owner-a", "member-a", "owner-b", "member-b")
    ]
    db.add_all([ws_a, ws_b, *users])
    db.flush()

    members = [
        Membership(id=str(uuid.uuid4()), workspace_id=workspace.id, user_id=user.id)
        for workspace, user in ((ws_a, users[0]), (ws_a, users[1]), (ws_b, users[2]), (ws_b, users[3]))
    ]
    db.add_all(members)
    role_codes = (
        "WORKSPACE_OWNER", "EXECUTIVE", "DEPARTMENT_MANAGER", "TEAM_LEAD",
        "RESEARCHER", "STRATEGIST", "VIDEO_EDITOR", "PUBLISHER", "ANALYST",
        "FINANCE_MANAGER", "CLIENT_APPROVER", "AUDITOR", "GUEST",
        "PLATFORM_OPS", "SERVICE_PRINCIPAL",
    )
    roles = {}
    for code in role_codes:
        role = db.query(Role).filter(Role.code == code).first()
        if role is None:
            role = Role(id=str(uuid.uuid4()), code=code, name=code.replace("_", " "), is_template=True)
            db.add(role)
        else:
            role.status = "ACTIVE"
        roles[code] = role
    db.flush()

    assignments = [
        RoleAssignment(workspace_id=ws_a.id, membership_id=members[0].id, role_id=roles["WORKSPACE_OWNER"].id, scope_type="WORKSPACE", status="ACTIVE"),
        RoleAssignment(workspace_id=ws_a.id, membership_id=members[1].id, role_id=roles["RESEARCHER"].id, scope_type="WORKSPACE", status="ACTIVE"),
        RoleAssignment(workspace_id=ws_b.id, membership_id=members[2].id, role_id=roles["WORKSPACE_OWNER"].id, scope_type="WORKSPACE", status="ACTIVE"),
        RoleAssignment(workspace_id=ws_b.id, membership_id=members[3].id, role_id=roles["RESEARCHER"].id, scope_type="WORKSPACE", status="ACTIVE"),
    ]
    db.add_all(assignments)
    res_a1 = BusinessResource(
        id=str(uuid.uuid4()), workspace_id=ws_a.id, owner_id=users[0].id, creator_id=users[0].id,
        title="Chiến lược A", search_text="nội dung riêng A", view_count=100,
    )
    res_b1 = BusinessResource(
        id=str(uuid.uuid4()), workspace_id=ws_b.id, owner_id=users[2].id, creator_id=users[2].id,
        title="Dữ liệu B", search_text="nội dung riêng B", view_count=500,
    )
    db.add_all([res_a1, res_b1])
    db.commit()

    return {
        "ws_a": ws_a,
        "ws_b": ws_b,
        "m_a_owner": members[0],
        "m_a_member": members[1],
        "m_b_owner": members[2],
        "m_b_member": members[3],
        "user_a_owner": users[0],
        "user_a_member": users[1],
        "user_b_owner": users[2],
        "user_b_member": users[3],
        "roles": roles,
        "res_a1": res_a1,
        "res_b1": res_b1,
    }
