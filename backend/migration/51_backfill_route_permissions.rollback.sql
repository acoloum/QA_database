-- Migration 51 rollback：只移除本次新增並管理的路由權限 keys。
-- 角色原有的其他權限與自訂 keys 必須完整保留。
UPDATE "角色"
SET "權限" = COALESCE("權限", '{}'::jsonb)
    - 'tolerance.view'
    - 'mechanical.view'
    - 'mechanical.create'
    - 'mechanical.edit'
    - 'mechanical.delete'
    - 'task.view'
    - 'analytics.view'
    - 'vendor.view'
WHERE "角色代碼" IN ('inspector', 'qa_supervisor', 'qc_manager', 'admin');
