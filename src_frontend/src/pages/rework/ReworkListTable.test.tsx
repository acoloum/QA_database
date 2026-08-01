import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ReworkListTable from './ReworkListTable';
import type { ReworkApplication } from '../../types';

const authMock = vi.fn();
vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));

const item: ReworkApplication = {
  識別碼: 1,
  申請單號: 'RW-1',
  申請日期: '2026-06-27',
  NCMR_ID: 2,
  ncmr_number: 'NCMR-2',
  申請人員姓名: '王小明',
  部門: '品保',
  產品資訊: '6061',
  重工數量: 3,
  緊急程度: '普通',
  狀態: '申請中',
};

describe('ReworkListTable', () => {
  it('renders rework rows and exposes row actions', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    const onOpenDetail = vi.fn();
    const onApprove = vi.fn();
    const onDelete = vi.fn();

    render(
      <ReworkListTable
        loading={false}
        applications={[item]}
        onOpenDetail={onOpenDetail}
        onApprove={onApprove}
        onDelete={onDelete}
      />,
    );

    expect(screen.getByText('RW-1')).toBeInTheDocument();
    fireEvent.click(screen.getByText('詳情'));
    fireEvent.click(screen.getByText('審核'));
    fireEvent.click(screen.getByText('刪除'));

    expect(onOpenDetail).toHaveBeenCalledWith(item);
    expect(onApprove).toHaveBeenCalledWith(1);
    expect(onDelete).toHaveBeenCalledWith(1);
  });

  it('缺少 approve/delete 權限時停用動作且不呼叫 handler', () => {
    authMock.mockReturnValue({ hasPermission: (permission: string) => permission === 'rework.view' });
    const onApprove = vi.fn();
    const onDelete = vi.fn();
    render(
      <ReworkListTable
        loading={false}
        applications={[item]}
        onOpenDetail={vi.fn()}
        onApprove={onApprove}
        onDelete={onDelete}
      />,
    );
    const approve = screen.getByRole('button', { name: '審核' });
    const remove = screen.getByRole('button', { name: '刪除' });
    expect(approve).toBeDisabled();
    expect(remove).toBeDisabled();
    fireEvent.click(approve);
    fireEvent.click(remove);
    expect(onApprove).not.toHaveBeenCalled();
    expect(onDelete).not.toHaveBeenCalled();
  });
});
