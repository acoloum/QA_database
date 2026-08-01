-- Migration 51：補齊路由權限矩陣。
-- JSONB 以現有權限在左、批次 patch 在右合併，因此保留自訂 key，
-- 並將此 migration 正式管理的 key 回填為 true。
UPDATE "角色" AS role_row
SET "權限" = COALESCE(role_row."權限", '{}'::jsonb) || patch.permissions
FROM (
    VALUES
        (
            'inspector',
            '{"tolerance.view": true, "mechanical.view": true, "mechanical.create": true, "task.view": true}'::jsonb
        ),
        (
            'qa_supervisor',
            '{"tolerance.view": true, "mechanical.view": true, "mechanical.create": true, "mechanical.edit": true, "task.view": true}'::jsonb
        ),
        (
            'qc_manager',
            '{"tolerance.view": true, "mechanical.view": true, "mechanical.create": true, "mechanical.edit": true, "mechanical.delete": true, "task.view": true, "analytics.view": true, "vendor.view": true}'::jsonb
        ),
        (
            'admin',
            '{"tolerance.view": true, "mechanical.view": true, "mechanical.create": true, "mechanical.edit": true, "mechanical.delete": true, "task.view": true, "analytics.view": true, "vendor.view": true}'::jsonb
        )
) AS patch(role_code, permissions)
WHERE role_row."角色代碼" = patch.role_code;
