import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ReworkListTable from './ReworkListTable';
import type { ReworkApplication } from '../../types';

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
});
