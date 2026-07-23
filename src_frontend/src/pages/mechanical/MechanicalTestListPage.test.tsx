import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import MechanicalTestListPage from './MechanicalTestListPage';

vi.mock('../../services/mechanicalApi', () => ({
  mechanicalApi: {
    list: vi.fn(),
    remove: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
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
    vi.clearAllMocks();
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

  it('以尺寸、材質、日期區間及僅 NG 條件重新載入清單', async () => {
    renderPage();

    await screen.findByText('62.5 x 2.3');
    fireEvent.change(screen.getByPlaceholderText('產品尺寸'), {
      target: { value: '80 x 3.0' },
    });
    fireEvent.change(screen.getByPlaceholderText('材質'), {
      target: { value: '6061' },
    });
    fireEvent.change(screen.getByLabelText('起始日期'), {
      target: { value: '2026-07-01' },
    });
    fireEvent.change(screen.getByLabelText('結束日期'), {
      target: { value: '2026-07-31' },
    });
    fireEvent.click(screen.getByLabelText('僅顯示 NG'));

    await waitFor(() => {
      expect(mechanicalApi.list).toHaveBeenLastCalledWith({
        product_size: '80 x 3.0',
        material: '6061',
        date_from: '2026-07-01',
        date_to: '2026-07-31',
        only_ng: 'true',
      });
    });
  });

  it('確認刪除後呼叫刪除 API', async () => {
    vi.mocked(mechanicalApi.remove).mockResolvedValue({ success: true });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();

    await screen.findByText('62.5 x 2.3');
    fireEvent.click(screen.getByRole('button', { name: '刪除' }));

    expect(confirmSpy).toHaveBeenCalledWith('確定刪除這筆檢驗？');
    await waitFor(() => expect(mechanicalApi.remove).toHaveBeenCalledWith(7));
  });

  it('刪除失敗時顯示錯誤回饋', async () => {
    vi.mocked(mechanicalApi.remove).mockRejectedValue(new Error('刪除失敗'));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();

    await screen.findByText('62.5 x 2.3');
    fireEvent.click(screen.getByRole('button', { name: '刪除' }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('刪除失敗，請稍後再試'));
  });

  it('查詢失敗時顯示錯誤狀態', async () => {
    vi.mocked(mechanicalApi.list).mockRejectedValue(new Error('查詢失敗'));
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('載入機械性質檢驗資料失敗，請稍後再試');
  });
});
