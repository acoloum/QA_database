import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import VendorPerformancePage from './VendorPerformancePage';

// vi.mock 為 hoisted：可變狀態與 spy 需透過 vi.hoisted 暴露給 factory 使用
const authState = vi.hoisted(() => ({ hasManage: true }));
const refreshMutate = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({
  useAuth: () => ({
    hasPermission: (permission: string) =>
      permission === 'vendor.manage' && authState.hasManage,
  }),
}));

vi.mock('../../hooks/useVendorPerformance', () => ({
  useVendorPerformanceList: () => ({
    data: [
      {
        id: 1,
        vendor_id: 7,
        vendor_name: '測試廠商',
        period: '2026-08',
        inspection_count: 10,
        defect_count: 1,
        defect_rate: 10,
        capa_count: 2,
        avg_capa_days: 3.5,
        complaint_count: 0,
        score: 85,
      },
    ],
    isLoading: false,
  }),
  useVendorPerformanceHistory: () => ({ data: [] }),
  useRefreshVendorPerformance: () => ({ mutate: refreshMutate, isPending: false }),
}));

vi.mock('react-chartjs-2', () => ({
  Line: () => <canvas aria-label="score chart" />,
}));

const currentPeriod = () => {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
};

describe('VendorPerformancePage', () => {
  beforeEach(() => {
    authState.hasManage = true;
    refreshMutate.mockReset();
  });

  it('具 vendor.manage 權限時顯示「重新計算」按鈕並以目前期間觸發 refresh', async () => {
    const user = userEvent.setup();
    render(<VendorPerformancePage />);

    const refreshButton = screen.getByRole('button', { name: '重新計算' });
    await user.click(refreshButton);

    expect(refreshMutate).toHaveBeenCalledWith(currentPeriod());
  });

  it('無 vendor.manage 權限時不顯示「重新計算」按鈕', () => {
    authState.hasManage = false;
    render(<VendorPerformancePage />);

    expect(screen.queryByRole('button', { name: '重新計算' })).not.toBeInTheDocument();
  });

  it('渲染廠商績效表格與分數', () => {
    render(<VendorPerformancePage />);

    expect(screen.getByText('測試廠商')).toBeInTheDocument();
    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('廠商績效評比')).toBeInTheDocument();
  });
});
