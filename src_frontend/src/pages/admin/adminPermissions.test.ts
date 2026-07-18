import { describe, expect, it } from 'vitest';
import { PERMISSION_GROUPS } from './adminPermissions';

describe('管理員權限清單', () => {
  it('可設定 SPC 檢視、管理與核准三層權限', () => {
    const spc = PERMISSION_GROUPS.find(group => group.label === 'SPC 研究與基準');
    expect(spc?.perms.map(permission => permission.key)).toEqual([
      'spc.view', 'spc.manage', 'spc.approve',
    ]);
  });
});
