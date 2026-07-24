import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import MechanicalTestListPage from './MechanicalTestListPage';

const authMock = vi.fn();
vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));

vi.mock('../../services/mechanicalApi', () => ({
  mechanicalApi: {
    list: vi.fn(),
    remove: vi.fn(),
    getVendors: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock('../../components/mechanical/MechanicalCharts', () => ({
  default: () => <div data-testid="mechanical-charts" />,
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
        擠製編號: 'E001',
        T4爐號: 'T4-01、T4-02',
        T4溫度時間: '190°C / 3h',
        T6溫度時間: '180°C / 5h',
        是否NG: false,
        判定狀態: 'OK',
        備註: '',
      }],
      total: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
    authMock.mockReturnValue({ hasPermission: () => true });
  });

  it('載入後顯示機械性質檢驗資料與 OK 判定', async () => {
    renderPage();

    expect(screen.getByText('載入中…')).toBeInTheDocument();
    expect(await screen.findByText('62.5 x 2.3')).toBeInTheDocument();
    expect(screen.getByText('E001')).toBeInTheDocument();
    // 判定徽章（限定 .badge，避免與「判定狀態」下拉選項的 OK 文字衝突）
    expect(screen.getByText('OK', { selector: '.badge' })).toBeInTheDocument();
  });

  it('分欄顯示兩種追溯摘要並使用完整溫度時間標題', async () => {
    renderPage();

    expect(await screen.findByRole('columnheader', { name: '擠製編號' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'T4爐號' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'T4溫度/時間' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'T6溫度/時間' })).toBeInTheDocument();
    expect(screen.getByText('E001')).toBeInTheDocument();
    expect(screen.getByText('T4-01、T4-02')).toBeInTheDocument();
  });

  it('空資料提示橫跨全部十個欄位', async () => {
    vi.mocked(mechanicalApi.list).mockResolvedValueOnce({
      success: true,
      data: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 0,
    });
    renderPage();

    expect(await screen.findByText('查無資料')).toHaveAttribute('colSpan', '10');
  });

  it('以尺寸、材質、日期區間及判定狀態條件重新載入清單', async () => {
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
    fireEvent.change(screen.getByLabelText('判定狀態'), {
      target: { value: 'NG' },
    });

    await waitFor(() => {
      expect(mechanicalApi.list).toHaveBeenLastCalledWith({
        product_size: '80 x 3.0',
        material: '6061',
        vendor_id: undefined,
        judgement_status: 'NG',
        date_from: '2026-07-01',
        date_to: '2026-07-31',
        page: 1,
        page_size: 20,
      });
    });
  });

  it.each([
    ['NG', 'NG'],
    ['OK', 'OK'],
    ['NO_SPEC', '無規格'],
    ['INCOMPLETE', '未完成'],
  ] as const)('顯示 %s 判定狀態', async (status, label) => {
    vi.mocked(mechanicalApi.list).mockResolvedValueOnce({
      success: true,
      data: [{
        識別碼: 7, 產品尺寸: 'A', 材質: '6061', 測試日期: null,
        擠製編號: '', T4爐號: '', T4溫度時間: null, T6溫度時間: null,
        是否NG: status === 'NG', 判定狀態: status, 備註: null,
      }],
      total: 1, page: 1, page_size: 20, total_pages: 1,
    });
    renderPage();
    expect(await screen.findByText(label)).toBeInTheDocument();
  });

  it('可翻頁與切換每頁筆數，篩選變更會回到第一頁', async () => {
    vi.mocked(mechanicalApi.list).mockResolvedValue({
      success: true, data: [], total: 45, page: 1, page_size: 20, total_pages: 3,
    });
    renderPage();
    await screen.findByText('共 45 筆');

    fireEvent.click(screen.getByRole('button', { name: '下一頁' }));
    await waitFor(() => expect(mechanicalApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
      page: 2, page_size: 20,
    })));

    fireEvent.change(screen.getByPlaceholderText('產品尺寸'), { target: { value: '80' } });
    await waitFor(() => expect(mechanicalApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
      product_size: '80', page: 1,
    })));

    fireEvent.change(screen.getByLabelText('每頁筆數'), { target: { value: '50' } });
    await waitFor(() => expect(mechanicalApi.list).toHaveBeenLastCalledWith(expect.objectContaining({
      page: 1, page_size: 50,
    })));
  });

  it('依 create/edit/delete 權限控制操作按鈕', async () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'mechanical.edit',
    });
    renderPage();
    await screen.findByText('62.5 x 2.3');

    expect(screen.queryByRole('button', { name: /新增檢驗/ })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '編輯' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '刪除' })).not.toBeInTheDocument();
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

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('刪除失敗'));
  });

  it('刪除遭拒時顯示後端權限訊息', async () => {
    vi.mocked(mechanicalApi.remove).mockRejectedValue({
      response: { status: 403, data: { error: '您沒有刪除機械性質檢驗的權限' } },
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();
    await screen.findByText('62.5 x 2.3');
    fireEvent.click(screen.getByRole('button', { name: '刪除' }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      '您沒有刪除機械性質檢驗的權限',
    ));
  });

  it('刪除錯誤相容 interceptor 的標準 Error 並避免重複 toast', async () => {
    const error = Object.assign(new Error('伺服器已顯示錯誤'), { _toasted: true });
    vi.mocked(mechanicalApi.remove).mockRejectedValue(error);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();
    await screen.findByText('62.5 x 2.3');
    fireEvent.click(screen.getByRole('button', { name: '刪除' }));

    await waitFor(() => expect(mechanicalApi.remove).toHaveBeenCalled());
    expect(toast.error).not.toHaveBeenCalledWith('伺服器已顯示錯誤');
  });

  it('查詢失敗時顯示錯誤狀態', async () => {
    vi.mocked(mechanicalApi.list).mockRejectedValue(new Error('查詢失敗'));
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('載入機械性質檢驗資料失敗，請稍後再試');
  });
});
