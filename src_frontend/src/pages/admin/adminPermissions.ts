export const PERMISSION_GROUPS: { label: string; perms: { key: string; label: string }[] }[] = [
  {
    label: 'NCMR',
    perms: [
      { key: 'ncmr.view', label: '查看' },
      { key: 'ncmr.create', label: '建立' },
      { key: 'ncmr.edit_own', label: '編輯（自己）' },
      { key: 'ncmr.edit', label: '編輯（所有）' },
      { key: 'ncmr.delete', label: '刪除' },
    ],
  },
  {
    label: 'CAPA',
    perms: [
      { key: 'capa.view', label: '查看' },
      { key: 'capa.create', label: '建立' },
      { key: 'capa.edit', label: '編輯' },
      { key: 'capa.close', label: '結案' },
    ],
  },
  {
    label: '重工',
    perms: [
      { key: 'rework.view', label: '查看' },
      { key: 'rework.create', label: '建立' },
      { key: 'rework.approve', label: '審核' },
      { key: 'rework.delete', label: '刪除' },
    ],
  },
  {
    label: '客訴',
    perms: [
      { key: 'complaint.view', label: '查看' },
      { key: 'complaint.create', label: '建立' },
      { key: 'complaint.edit', label: '編輯' },
      { key: 'complaint.delete', label: '刪除' },
    ],
  },
  {
    label: '出貨巡檢',
    perms: [
      { key: 'shipping.view', label: '查看' },
      { key: 'shipping.create', label: '建立' },
      { key: 'shipping.edit_own', label: '編輯（自己）' },
      { key: 'shipping.edit', label: '編輯（所有）' },
      { key: 'shipping.delete', label: '刪除' },
    ],
  },
  {
    label: '巡線',
    perms: [
      { key: 'patrol.view', label: '查看' },
      { key: 'patrol.create', label: '建立' },
      { key: 'patrol.edit_own', label: '編輯（自己）' },
      { key: 'patrol.edit', label: '編輯（所有）' },
      { key: 'patrol.delete', label: '刪除' },
    ],
  },
  {
    label: '爐溫測試 (CQI-9)',
    perms: [
      { key: 'pyrometry.view', label: '查看' },
      { key: 'pyrometry.edit', label: '建立 / 編輯' },
      { key: 'pyrometry.delete', label: '刪除' },
    ],
  },
  {
    label: '任務',
    perms: [
      { key: 'task.create', label: '建立' },
      { key: 'task.edit', label: '編輯 / 狀態' },
      { key: 'task.delete', label: '刪除' },
    ],
  },
  {
    label: '廠商 / 報表 / 管理',
    perms: [
      { key: 'vendor.manage', label: '廠商管理' },
      { key: 'tolerance.manage', label: '公差管理' },
      { key: 'report.view', label: '報表查看' },
      { key: 'user.manage', label: '使用者管理' },
    ],
  },
];
