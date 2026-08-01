import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PermissionAction from './PermissionAction';

const authMock = vi.fn();

vi.mock('../context/useAuth', () => ({ useAuth: () => authMock() }));

describe('PermissionAction', () => {
  beforeEach(() => vi.clearAllMocks());

  it('缺少權限時停用動作、合併說明關聯且不觸發事件', () => {
    const handleClick = vi.fn();
    authMock.mockReturnValue({ hasPermission: () => false });
    render(
      <>
        <span id="既有說明">既有說明</span>
        <PermissionAction permission="ncmr.delete">
          <button aria-describedby="既有說明" onClick={handleClick}>刪除</button>
        </PermissionAction>
      </>,
    );

    const button = screen.getByRole('button', { name: '刪除' });
    expect(button).toBeDisabled();
    expect(button.getAttribute('aria-describedby')).toContain('既有說明');
    const reason = screen.getByText('需要 ncmr.delete 權限');
    expect(button.getAttribute('aria-describedby')).toContain(reason.id);
    fireEvent.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('保留 child 原本的 disabled 狀態', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    render(
      <PermissionAction permission="shipping.create">
        <button disabled>新增</button>
      </PermissionAction>,
    );
    expect(screen.getByRole('button', { name: '新增' })).toBeDisabled();
  });

  it('具有全部指定權限時動作可用且事件正常觸發', () => {
    const handleClick = vi.fn();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => ['complaint.edit', 'capa.create'].includes(permission),
    });
    render(
      <PermissionAction permission="complaint.edit" permissions={['capa.create']}>
        <button onClick={handleClick}>開立 CAPA</button>
      </PermissionAction>,
    );
    const button = screen.getByRole('button', { name: '開立 CAPA' });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledOnce();
  });

  it('any 模式接受任一權限，缺少全部權限時使用指定提示', () => {
    authMock.mockReturnValue({ hasPermission: (permission: string) => permission === 'ncmr.edit_own' });
    const { rerender } = render(
      <PermissionAction
        permission="ncmr.edit"
        permissions={['ncmr.edit_own']}
        requireMode="any"
        reason="只能編輯本人建立的 NCMR"
      >
        <button>編輯</button>
      </PermissionAction>,
    );
    expect(screen.getByRole('button', { name: '編輯' })).toBeEnabled();

    authMock.mockReturnValue({ hasPermission: () => false });
    rerender(
      <PermissionAction
        permission="ncmr.edit"
        permissions={['ncmr.edit_own']}
        requireMode="any"
        reason="只能編輯本人建立的 NCMR"
      >
        <button>編輯</button>
      </PermissionAction>,
    );
    expect(screen.getByRole('button', { name: '編輯' })).toBeDisabled();
    expect(screen.getByText('只能編輯本人建立的 NCMR')).toBeInTheDocument();
  });

  it('mode hide 在缺權限時不呈現動作', () => {
    authMock.mockReturnValue({ hasPermission: () => false });
    render(
      <PermissionAction permission="ncmr.delete" mode="hide">
        <button>隱藏刪除</button>
      </PermissionAction>,
    );
    expect(screen.queryByText('隱藏刪除')).not.toBeInTheDocument();
  });

  it('預設 disable 模式拒絕不支援 disabled 的原生 child', () => {
    authMock.mockReturnValue({ hasPermission: () => false });
    expect(() => render(
      <PermissionAction permission="ncmr.delete">
        <a href="/delete">連結動作</a>
      </PermissionAction>,
    )).toThrow('不支援 disabled；請明確使用 mode="hide"');
  });
});
