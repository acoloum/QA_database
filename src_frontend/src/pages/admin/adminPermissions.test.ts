import { describe, expect, it } from 'vitest';
import { PERMISSION_GROUPS } from './adminPermissions';

describe('管理員權限清單', () => {
  it('可設定 SPC 檢視、管理與核准三層權限', () => {
    const spc = PERMISSION_GROUPS.find(group => group.label === 'SPC 研究與基準');
    expect(spc?.perms.map(permission => permission.key)).toEqual([
      'spc.view', 'spc.manage', 'spc.approve',
    ]);
  });

  it('可設定機械性質的建立、編輯與刪除權限', () => {
    const mechanical = PERMISSION_GROUPS.find(group => group.label === '機械性質');

    expect(mechanical?.perms).toEqual([
      { key: 'mechanical.create', label: '建立' },
      { key: 'mechanical.edit', label: '編輯' },
      { key: 'mechanical.delete', label: '刪除' },
    ]);
  });

  it('可設定 MSA 檢視、執行、管理與核准四層權限', () => {
    const msa = PERMISSION_GROUPS.find(group => group.label === '量測系統分析');

    expect(msa?.perms).toEqual([
      { key: 'msa.view', label: '檢視' },
      { key: 'msa.execute', label: '執行研究與輸入資料' },
      { key: 'msa.manage', label: '管理設備、準則與送審' },
      { key: 'msa.approve', label: '核准與作廢' },
    ]);
  });
});
