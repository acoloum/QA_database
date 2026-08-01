import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

import NCMRPage from './NCMRPage';

const authMock = vi.fn();

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useNCMR', () => ({
  useNCMRList: () => ({ data: { data: [{
    id: 5,
    no: 'NCMR-5',
    date: '2026-08-01',
    source: '巡檢',
    defect_qty: 2,
    result: '待判定',
    status: '待處理',
  }], total: 1 }, isLoading: false }),
  useDeleteNCMR: () => ({ mutateAsync: vi.fn() }),
  useCreateCAPA: () => ({ mutateAsync: vi.fn() }),
  useNCMRDetail: () => ({ data: null }),
}));
vi.mock('../../components/ncmr/NCMRModal', () => ({ default: () => null }));
vi.mock('../../components/ncmr/DispositionModal', () => ({
  default: ({ show }: { show: boolean }) => show ? <h3>唯讀處置明細</h3> : null,
}));
vi.mock('../../components/common/ConfirmActionModal', () => ({ default: () => null }));

describe('NCMRPage 處置明細入口', () => {
  it('只有 ncmr.view 時仍可開啟處置明細', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'ncmr.view',
    });
    render(<MemoryRouter><NCMRPage /></MemoryRouter>);

    const result = screen.getByRole('button', { name: '待判定' });
    expect(result).toBeEnabled();
    fireEvent.click(result);
    expect(screen.getByRole('heading', { name: '唯讀處置明細' })).toBeInTheDocument();
  });
});
