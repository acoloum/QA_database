import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { mechanicalApi } from '../../services/mechanicalApi';
import MechanicalTestListPage from './MechanicalTestListPage';

vi.mock('../../services/mechanicalApi', () => ({
  mechanicalApi: {
    list: vi.fn(),
    remove: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn() },
}));

vi.mock('./MechanicalTestForm', () => ({
  default: () => <div data-testid="mechanical-test-form" />,
}));

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MechanicalTestListPage />
    </QueryClientProvider>,
  );
};

describe('MechanicalTestListPage', () => {
  beforeEach(() => {
    vi.mocked(mechanicalApi.list).mockResolvedValue({
      success: true,
      data: [{
        識別碼: 7,
        產品尺寸: '62.5 x 2.3',
        材質: '6063',
        測試日期: '2026-07-23',
        擠製編號: 'EX-20260723-01',
        T4溫度時間: '190°C / 3h',
        T6溫度時間: '180°C / 5h',
        是否NG: false,
        備註: '',
      }],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  });

  it('載入後顯示機械性質檢驗資料與 OK 判定', async () => {
    renderPage();

    expect(screen.getByText('載入中…')).toBeInTheDocument();
    expect(await screen.findByText('62.5 x 2.3')).toBeInTheDocument();
    expect(screen.getByText('EX-20260723-01')).toBeInTheDocument();
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('變更產品尺寸篩選時以篩選條件重新載入清單', async () => {
    renderPage();

    await screen.findByText('62.5 x 2.3');
    fireEvent.change(screen.getByPlaceholderText('產品尺寸'), {
      target: { value: '80 x 3.0' },
    });

    await waitFor(() => {
      expect(mechanicalApi.list).toHaveBeenLastCalledWith({
        product_size: '80 x 3.0',
        material: undefined,
      });
    });
  });
});
