import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ComplaintFilterBar, ComplaintTable } from './ComplaintPageParts';
import type { CustomerComplaint } from '../../types';

const authMock = vi.fn();
vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));

const complaint: CustomerComplaint = {
  id: 1,
  complaint_no: 'CC-1',
  customer: '客戶A',
  complaint_date: '2026-06-27',
  material: '6061',
  spec: 'T6',
  description: '尺寸不良',
  complaint_type: 'quality',
  severity: 'Major',
  is_repeat: true,
  repeat_refs: [],
  related_capa_id: null,
  related_rework_id: null,
  status: '待處理',
};

describe('ComplaintPageParts', () => {
  it('renders filter bar and resets page on field changes', () => {
    const onFilterChange = vi.fn();
    render(
      <ComplaintFilterBar
        filters={{ customer: '', material: '', spec: '', status: '', type: '', dateFrom: '', dateTo: '', repeat: '' }}
        onFilterChange={onFilterChange}
        onReset={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('搜尋客戶…'), { target: { value: '客戶A' } });
    expect(onFilterChange).toHaveBeenCalledWith('customer', '客戶A');
  });

  it('renders complaint table actions', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    const onOpenCapa = vi.fn();
    const onOpenRework = vi.fn();

    render(
      <ComplaintTable
        loading={false}
        complaints={[complaint]}
        capaPending={false}
        reworkPending={false}
        onEdit={onEdit}
        onDelete={onDelete}
        onOpenCapa={onOpenCapa}
        onOpenRework={onOpenRework}
        onNavigateToCapa={vi.fn()}
        onNavigateToRework={vi.fn()}
      />,
    );

    expect(screen.getByText('CC-1')).toBeInTheDocument();
    fireEvent.click(screen.getByText('編輯'));
    fireEvent.click(screen.getByText('刪除'));
    fireEvent.click(screen.getByText('開立CAPA'));
    fireEvent.click(screen.getByText('開立重工'));

    expect(onEdit).toHaveBeenCalledWith(complaint);
    expect(onDelete).toHaveBeenCalledWith(complaint);
    expect(onOpenCapa).toHaveBeenCalledWith(complaint);
    expect(onOpenRework).toHaveBeenCalledWith(complaint);
  });

  it('跨領域開單缺少任一權限時停用且不呼叫 handler', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'complaint.edit',
    });
    const onOpenCapa = vi.fn();
    const onOpenRework = vi.fn();
    render(
      <ComplaintTable
        loading={false}
        complaints={[complaint]}
        capaPending={false}
        reworkPending={false}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onOpenCapa={onOpenCapa}
        onOpenRework={onOpenRework}
        onNavigateToCapa={vi.fn()}
        onNavigateToRework={vi.fn()}
      />,
    );
    const capa = screen.getByRole('button', { name: '開立CAPA' });
    const rework = screen.getByRole('button', { name: '開立重工' });
    expect(capa).toBeDisabled();
    expect(rework).toBeDisabled();
    fireEvent.click(capa);
    fireEvent.click(rework);
    expect(onOpenCapa).not.toHaveBeenCalled();
    expect(onOpenRework).not.toHaveBeenCalled();
  });
});
