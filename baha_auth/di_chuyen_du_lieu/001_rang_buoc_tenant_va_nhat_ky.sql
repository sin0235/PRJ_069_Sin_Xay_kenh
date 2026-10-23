-- Migration PostgreSQL ngoại tuyến cho ràng buộc cùng tenant và nhật ký bất biến.
-- Chạy bằng tài khoản migration sau khi lưu trữ và rà soát kết quả các truy vấn kiểm tra.
-- Không áp dụng migration này vào cơ sở dữ liệu dự án trong lượt sửa lỗi.

BEGIN;

ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS creator_id VARCHAR(36);
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS artifact_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS project_id VARCHAR(36);
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS brand_id VARCHAR(36);
ALTER TABLE business_resources ADD COLUMN IF NOT EXISTS channel_id VARCHAR(36);

ALTER TABLE delegated_job_grants ADD COLUMN IF NOT EXISTS target_artifact_version INTEGER;
ALTER TABLE delegated_job_grants ADD COLUMN IF NOT EXISTS target_content_hash VARCHAR(64);
ALTER TABLE delegated_job_grants ADD COLUMN IF NOT EXISTS worker_subject VARCHAR(255);

-- Thu hồi các grant cũ chưa khóa tài nguyên và principal; không tự đoán dữ liệu tin cậy.
UPDATE delegated_job_grants
SET status = CASE WHEN status = 'ACTIVE' THEN 'REVOKED' ELSE status END,
    target_artifact_version = COALESCE(target_artifact_version, 0),
    target_content_hash = COALESCE(target_content_hash, repeat('0', 64)),
    worker_subject = COALESCE(worker_subject, 'revoked-unpinned')
WHERE target_artifact_version IS NULL
   OR target_content_hash IS NULL
   OR worker_subject IS NULL;

ALTER TABLE delegated_job_grants ALTER COLUMN target_artifact_version SET NOT NULL;
ALTER TABLE delegated_job_grants ALTER COLUMN target_content_hash SET NOT NULL;
ALTER TABLE delegated_job_grants ALTER COLUMN worker_subject SET NOT NULL;

-- Từ chối migration nếu dữ liệu cũ đang trỏ sang tenant khác hoặc có khóa duy nhất bị trùng.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM org_units child JOIN org_units parent ON parent.id = child.parent_id
        WHERE child.parent_id IS NOT NULL AND child.workspace_id <> parent.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công cây OrgUnit đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM org_assignments a JOIN memberships m ON m.id = a.membership_id
        JOIN org_units o ON o.id = a.org_unit_id
        WHERE a.workspace_id <> m.workspace_id OR a.workspace_id <> o.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công OrgAssignment đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM role_assignments a JOIN memberships m ON m.id = a.membership_id
        WHERE a.workspace_id <> m.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công RoleAssignment đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM role_assignments a JOIN memberships m ON m.id = a.granted_by
        WHERE a.granted_by IS NOT NULL AND a.workspace_id <> m.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công grantor của RoleAssignment đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM reporting_lines r
        LEFT JOIN memberships manager ON manager.id = r.manager_membership_id
        LEFT JOIN memberships report ON report.id = r.report_membership_id
        LEFT JOIN org_units unit ON unit.id = r.org_unit_id
        WHERE r.workspace_id <> manager.workspace_id OR r.workspace_id <> report.workspace_id
           OR (r.org_unit_id IS NOT NULL AND r.workspace_id <> unit.workspace_id)
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ReportingLine đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM resource_grants g JOIN memberships m ON m.id = g.membership_id
        WHERE g.workspace_id <> m.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ResourceGrant đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM delegations d
        LEFT JOIN memberships grantor ON grantor.id = d.grantor_membership_id
        LEFT JOIN memberships grantee ON grantee.id = d.grantee_membership_id
        WHERE d.workspace_id <> grantor.workspace_id OR d.workspace_id <> grantee.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công Delegation đang chéo tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM business_resources r
        LEFT JOIN org_units o ON o.id = r.org_unit_id
        WHERE r.org_unit_id IS NOT NULL AND r.workspace_id <> o.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công BusinessResource đang gắn OrgUnit khác tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM business_resources r
        LEFT JOIN memberships m ON m.user_id = r.owner_id AND m.workspace_id = r.workspace_id
        WHERE r.workspace_id IS NOT NULL AND r.owner_id IS NOT NULL AND m.id IS NULL
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công owner của BusinessResource không thuộc tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM business_resources r
        LEFT JOIN memberships m ON m.user_id = r.creator_id AND m.workspace_id = r.workspace_id
        WHERE r.workspace_id IS NOT NULL AND r.creator_id IS NOT NULL AND m.id IS NULL
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công creator của BusinessResource không thuộc tenant'; END IF;

    IF EXISTS (
        SELECT 1 FROM approval_runs
        GROUP BY workspace_id, artifact_type, artifact_id, artifact_version, policy_id
        HAVING count(*) > 1
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ApprovalRun trùng tài nguyên, phiên bản và policy'; END IF;

    IF EXISTS (
        SELECT 1 FROM approval_runs r
        LEFT JOIN business_resources b ON b.id = r.artifact_id
        LEFT JOIN approval_policies p ON p.id = r.policy_id
        LEFT JOIN memberships m ON m.id = r.created_by
        WHERE b.id IS NULL OR b.workspace_id <> r.workspace_id
           OR p.id IS NULL OR p.workspace_id <> r.workspace_id
           OR m.id IS NULL OR m.workspace_id <> r.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ApprovalRun tham chiếu khác tenant hoặc thiếu dữ liệu'; END IF;

    IF EXISTS (
        SELECT 1 FROM delegated_job_grants g
        LEFT JOIN business_resources b ON b.id = g.target_resource
        LEFT JOIN memberships m ON m.id = g.initiating_membership_id
        WHERE b.id IS NULL OR b.workspace_id <> g.workspace_id
           OR m.id IS NULL OR m.workspace_id <> g.workspace_id
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công worker grant tham chiếu khác tenant hoặc thiếu dữ liệu'; END IF;

    IF EXISTS (
        SELECT 1 FROM approval_decisions GROUP BY step_id HAVING count(*) > 1
    ) THEN RAISE EXCEPTION 'Cần xử lý thủ công ApprovalDecision trùng step_id'; END IF;
END;
$$;

-- Hàm tạm chỉ giúp thêm ràng buộc một lần trong cùng phiên migration.
CREATE OR REPLACE FUNCTION pg_temp.add_constraint_if_missing(
    p_table REGCLASS, p_name TEXT, p_definition TEXT
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = p_table AND conname = p_name
    ) THEN
        EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', p_table, p_name, p_definition);
    END IF;
END;
$$;

SELECT pg_temp.add_constraint_if_missing('memberships', 'uq_memberships_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('org_units', 'uq_org_units_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'uq_approval_runs_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_steps', 'uq_approval_steps_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_policies', 'uq_approval_policies_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'uq_business_resources_workspace_id',
    'UNIQUE (workspace_id, id)');

SELECT pg_temp.add_constraint_if_missing('org_units', 'fk_org_units_parent_same_workspace',
    'FOREIGN KEY (workspace_id, parent_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('org_assignments', 'fk_org_assignment_membership_same_workspace',
    'FOREIGN KEY (workspace_id, membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('org_assignments', 'fk_org_assignment_unit_same_workspace',
    'FOREIGN KEY (workspace_id, org_unit_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('role_assignments', 'fk_role_assignment_membership_same_workspace',
    'FOREIGN KEY (workspace_id, membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('role_assignments', 'fk_role_assignment_grantor_same_workspace',
    'FOREIGN KEY (workspace_id, granted_by) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'uq_reporting_lines_workspace_id',
    'UNIQUE (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'fk_reporting_manager_same_workspace',
    'FOREIGN KEY (workspace_id, manager_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'fk_reporting_report_same_workspace',
    'FOREIGN KEY (workspace_id, report_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('reporting_lines', 'fk_reporting_org_unit_same_workspace',
    'FOREIGN KEY (workspace_id, org_unit_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('resource_grants', 'fk_resource_grant_membership_same_workspace',
    'FOREIGN KEY (workspace_id, membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegations', 'fk_delegation_grantor_same_workspace',
    'FOREIGN KEY (workspace_id, grantor_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegations', 'fk_delegation_grantee_same_workspace',
    'FOREIGN KEY (workspace_id, grantee_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_steps', 'fk_approval_step_run_same_workspace',
    'FOREIGN KEY (workspace_id, run_id) REFERENCES approval_runs (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_decisions', 'uq_approval_decision_step',
    'UNIQUE (step_id)');
SELECT pg_temp.add_constraint_if_missing('approval_decisions', 'fk_approval_decision_step_same_workspace',
    'FOREIGN KEY (workspace_id, step_id) REFERENCES approval_steps (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_decisions', 'fk_approval_decision_reviewer_same_workspace',
    'FOREIGN KEY (workspace_id, reviewer_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'fk_job_grant_membership_same_workspace',
    'FOREIGN KEY (workspace_id, initiating_membership_id) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'fk_job_grant_resource_same_workspace',
    'FOREIGN KEY (workspace_id, target_resource) REFERENCES business_resources (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'fk_approval_run_artifact_same_workspace',
    'FOREIGN KEY (workspace_id, artifact_id) REFERENCES business_resources (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'fk_approval_run_policy_same_workspace',
    'FOREIGN KEY (workspace_id, policy_id) REFERENCES approval_policies (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'fk_approval_run_creator_same_workspace',
    'FOREIGN KEY (workspace_id, created_by) REFERENCES memberships (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('approval_runs', 'uq_approval_run_artifact_version_policy',
    'UNIQUE (workspace_id, artifact_type, artifact_id, artifact_version, policy_id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'fk_business_resource_org_same_workspace',
    'FOREIGN KEY (workspace_id, org_unit_id) REFERENCES org_units (workspace_id, id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'fk_business_resource_owner_same_workspace',
    'FOREIGN KEY (workspace_id, owner_id) REFERENCES memberships (workspace_id, user_id)');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'fk_business_resource_creator_same_workspace',
    'FOREIGN KEY (workspace_id, creator_id) REFERENCES memberships (workspace_id, user_id)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'ck_job_grant_version_nonnegative',
    'CHECK (target_artifact_version >= 0)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'ck_job_grant_hash_length',
    'CHECK (length(target_content_hash) = 64)');
SELECT pg_temp.add_constraint_if_missing('delegated_job_grants', 'ck_job_grant_active_is_pinned',
    'CHECK (status <> ''ACTIVE'' OR (target_artifact_version > 0 AND target_content_hash <> repeat(''0'', 64) AND worker_subject <> ''revoked-unpinned''))');
SELECT pg_temp.add_constraint_if_missing('business_resources', 'ck_business_resource_version_positive',
    'CHECK (artifact_version > 0)');

-- Chỉ cho truy vấn theo tenant đã được backend xác minh trong giao dịch hiện tại.
DO $$
DECLARE
    table_name TEXT;
    tenant_tables TEXT[] := ARRAY[
        'memberships', 'org_units', 'reporting_lines', 'org_assignments',
        'role_assignments', 'resource_grants', 'delegations', 'approval_policies',
        'approval_runs', 'approval_steps', 'approval_decisions',
        'delegated_job_grants', 'authz_audit_events', 'business_resources'
    ];
BEGIN
    ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
    ALTER TABLE workspaces FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_workspace_isolation ON workspaces;
    CREATE POLICY tenant_workspace_isolation ON workspaces
        USING (id = NULLIF(current_setting('baha.current_workspace_id', true), ''))
        WITH CHECK (id = NULLIF(current_setting('baha.current_workspace_id', true), ''));

    FOREACH table_name IN ARRAY tenant_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format('DROP POLICY IF EXISTS tenant_workspace_isolation ON %I', table_name);
        IF table_name = 'business_resources' THEN
            EXECUTE format(
                'CREATE POLICY tenant_workspace_isolation ON %I USING (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), '''') OR (workspace_id IS NULL AND current_setting(''baha.authz_maintenance'', true) = ''on'')) WITH CHECK (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), '''') OR (workspace_id IS NULL AND current_setting(''baha.authz_maintenance'', true) = ''on''))',
                table_name
            );
        ELSE
            EXECUTE format(
                'CREATE POLICY tenant_workspace_isolation ON %I USING (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), '''')) WITH CHECK (workspace_id = NULLIF(current_setting(''baha.current_workspace_id'', true), ''''))',
                table_name
            );
        END IF;
    END LOOP;

    ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
    ALTER TABLE roles FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_role_catalog ON roles;
    CREATE POLICY tenant_role_catalog ON roles
        USING (workspace_id IS NULL OR workspace_id = NULLIF(current_setting('baha.current_workspace_id', true), ''))
        WITH CHECK (workspace_id = NULLIF(current_setting('baha.current_workspace_id', true), ''));

    ALTER TABLE permissions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE permissions FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS shared_permission_catalog ON permissions;
    CREATE POLICY shared_permission_catalog ON permissions FOR SELECT USING (true);

    ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_role_permissions ON role_permissions;
    CREATE POLICY tenant_role_permissions ON role_permissions FOR SELECT
        USING (EXISTS (
            SELECT 1 FROM roles r WHERE r.id = role_permissions.role_id
              AND (r.workspace_id IS NULL OR r.workspace_id = NULLIF(current_setting('baha.current_workspace_id', true), ''))
        ));
END;
$$;

-- Bảo vệ nhật ký kể cả khi một đường API mới vô tình thêm thao tác cập nhật/xóa.
CREATE OR REPLACE FUNCTION authz_reject_audit_mutation() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Nhật ký phân quyền chỉ được ghi nối tiếp';
END;
$$;

DROP TRIGGER IF EXISTS authz_audit_no_update ON authz_audit_events;
CREATE TRIGGER authz_audit_no_update
    BEFORE UPDATE ON authz_audit_events FOR EACH ROW EXECUTE FUNCTION authz_reject_audit_mutation();
DROP TRIGGER IF EXISTS authz_audit_no_delete ON authz_audit_events;
CREATE TRIGGER authz_audit_no_delete
    BEFORE DELETE ON authz_audit_events FOR EACH ROW EXECUTE FUNCTION authz_reject_audit_mutation();

COMMIT;
