import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import UserManagementPage from './UserManagementPage';


const resetPasswordMutate = vi.fn();

vi.mock('../../context/useAuth', () => ({
  useAuth: () => ({
    user: { user_id: '1', username: 'admin', role: 'admin' },
    hasPermission: (permission: string) => permission === 'user.manage',
  }),
}));

vi.mock('../../context/useRoles', () => ({
  useRoles: () => ({
    data: [
      { code: 'admin', name: '系統管理員', permissions: { 'user.manage': true } },
      { code: 'user', name: '一般使用者', permissions: {} },
    ],
  }),
}));

vi.mock('../../hooks/useAdmin', () => ({
  useAdminUsers: () => ({
    data: [
      { id: 1, username: 'admin', role: 'admin', is_active: true, created_at: null },
      { id: 2, username: 'operator', role: 'user', is_active: true, created_at: null },
    ],
    isLoading: false,
    isError: false,
  }),
  useCreateAdminUser: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateAdminUserActive: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateAdminUserRole: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
  useResetAdminUserPassword: () => ({ mutate: resetPasswordMutate, isPending: false }),
  useUpdateRolePermissions: () => ({ mutate: vi.fn(), isPending: false }),
}));


describe('UserManagementPage 重設密碼', () => {
  beforeEach(() => {
    resetPasswordMutate.mockReset();
  });

  it('由目標帳號操作列開啟重設密碼表單並提交至少八字元密碼', async () => {
    const user = userEvent.setup();
    render(<UserManagementPage />);

    const operatorRow = screen.getByText('operator').closest('tr');
    expect(operatorRow).not.toBeNull();
    await user.click(
      screen.getByRole('button', { name: '重設 operator 的密碼' }),
    );

    const passwordInput = screen.getByLabelText('新密碼');
    await user.type(passwordInput, 'new-password-123');
    await user.click(screen.getByRole('button', { name: '確認重設密碼' }));

    expect(resetPasswordMutate).toHaveBeenCalledWith({
      id: 2,
      password: 'new-password-123',
    });
  });

  it('前端拒絕七字元密碼且不送出 mutation', async () => {
    const user = userEvent.setup();
    render(<UserManagementPage />);

    await user.click(
      screen.getByRole('button', { name: '重設 operator 的密碼' }),
    );
    fireEvent.change(screen.getByLabelText('新密碼'), {
      target: { value: '1234567' },
    });
    fireEvent.submit(screen.getByRole('form', { name: '重設密碼表單' }));

    expect(await screen.findByText('密碼長度至少需要 8 個字元')).toBeInTheDocument();
    expect(resetPasswordMutate).not.toHaveBeenCalled();
  });
});
