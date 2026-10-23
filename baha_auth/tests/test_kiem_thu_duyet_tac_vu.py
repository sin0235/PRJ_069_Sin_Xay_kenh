"""Kiểm thử schema nghiêm ngặt cho API duyệt, grant và thao tác thành viên."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

BAHA_AUTH_ROOT = Path(__file__).resolve().parents[2]
if str(BAHA_AUTH_ROOT) not in sys.path:
    sys.path.insert(0, str(BAHA_AUTH_ROOT))

from baha_auth.src.schemas.contracts import (
    ApprovalDecisionRequest,
    ApprovalRunCreate,
    DelegatedJobGrantRequest,
    DelegationRequest,
    MemberInviteRequest,
    RoleAssignmentRequest,
    WorkerRecheckRequest,
)


def _assert_truong_la_bi_cam(schema, payload):
    with pytest.raises(ValidationError) as loi:
        schema.model_validate(payload)
    assert any(error["type"] == "extra_forbidden" for error in loi.value.errors())


def test_schema_duyet_khong_nhan_policy_stages_creator_hoac_hash_tu_client():
    _assert_truong_la_bi_cam(
        ApprovalRunCreate,
        {
            "artifact_type": "IDEA",
            "artifact_id": "resource-1",
            "expected_version": 1,
            "content_hash": "a" * 64,
            "stages": [{"stage_key": "FINAL", "allowed_role": "PLATFORM_OPS"}],
            "policy_id": "client-policy",
            "creator_membership_id": "client-creator",
        },
    )


def test_schema_quyet_dinh_khong_nhan_danh_tinh_nguoi_duyet_tu_client():
    _assert_truong_la_bi_cam(
        ApprovalDecisionRequest,
        {
            "step_id": "step-1",
            "result": "APPROVED",
            "artifact_version": 1,
            "content_hash": "a" * 64,
            "reviewer_membership_id": "other-reviewer",
            "workspace_id": "other-workspace",
            "policy_id": "other-policy",
        },
    )


def test_schema_grant_khong_nhan_actor_scope_version_hash_hoac_policy_tu_client():
    _assert_truong_la_bi_cam(
        DelegatedJobGrantRequest,
        {
            "job_id": "job-1",
            "target_resource": "resource-1",
            "allowed_actions": ["ideas.read"],
            "expires_at": datetime.now(timezone.utc).isoformat(),
            "workspace_id": "other-workspace",
            "initiating_membership_id": "other-member",
            "target_artifact_version": 999,
            "target_content_hash": "b" * 64,
            "worker_subject": "attacker",
            "policy_version": "forged",
        },
    )


def test_schema_worker_recheck_khong_nhan_workspace_hoac_actor_tu_client():
    _assert_truong_la_bi_cam(
        WorkerRecheckRequest,
        {
            "job_id": "job-1",
            "action_key": "ideas.read",
            "workspace_id": "other-workspace",
            "initiating_membership_id": "other-member",
        },
    )


def test_schema_gan_vai_tro_tu_choi_truong_is_admin():
    _assert_truong_la_bi_cam(
        RoleAssignmentRequest,
        {
            "grantee_membership_id": "member-1",
            "role_code": "TEAM_LEAD",
            "scope_type": "TEAM",
            "scope_id": "team-1",
            "is_admin": True,
        },
    )


def test_schema_gan_vai_tro_gioi_han_loai_pham_vi():
    with pytest.raises(ValidationError):
        RoleAssignmentRequest.model_validate({
            "grantee_membership_id": "member-1",
            "role_code": "TEAM_LEAD",
            "scope_type": "ALL_WORKSPACES",
        })


def test_schema_moi_thanh_vien_tu_choi_truong_is_admin():
    _assert_truong_la_bi_cam(
        MemberInviteRequest,
        {
            "email": "guest@example.invalid",
            "full_name": "Khách thử nghiệm",
            "initial_role_code": "GUEST",
            "scope_type": "WORKSPACE",
            "is_admin": True,
        },
    )


@pytest.mark.parametrize("schema,payload", [
    (
        RoleAssignmentRequest,
        {"grantee_membership_id": "member-1", "role_code": "TEAM_LEAD", "valid_until": "2026-10-22T12:00:00"},
    ),
    (
        DelegationRequest,
        {"grantee_membership_id": "member-1", "allowed_actions": ["ideas.read"], "expires_at": "2026-10-22T12:00:00"},
    ),
    (
        DelegatedJobGrantRequest,
        {"job_id": "job-1", "target_resource": "resource-1", "allowed_actions": ["ideas.read"], "expires_at": "2026-10-22T12:00:00"},
    ),
])
def test_schema_tu_choi_thoi_han_khong_co_mui_gio(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)
