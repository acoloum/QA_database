import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import type { MechanicalSuspectMeasurement } from '../../types';
import MechanicalSuspectPanel from './MechanicalSuspectPanel';

const authMock = vi.fn();
vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));

vi.mock('../../services/mechanicalApi', () => ({
  mechanicalApi: {
    suspects: vi.fn(),
    setExclusion: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

const suspect = (overrides: Partial<MechanicalSuspectMeasurement> = {}): MechanicalSuspectMeasurement => ({
  識別碼: 501,
  檢驗ID: 1428,
  測試日期: '2024-11-28',
  材質: '6061-T651',
  產品尺寸: '66.7*59',
  量測項目: '抗拉強度',
  測量位置: '爐頂',
  取樣序: 1,
  量測值: 37128,
  同組中位數: 371.2,
  正常下界: 280.5,
  正常上界: 460.1,
  同組筆數: 6600,
  同爐次其他值: [{ 測量位置: '爐門', 取樣序: 1, 量測值: 379.64, 排除統計: false }],
  提示: '疑似小數點位置錯誤，可能應為 371.28',
  排除統計: false,
  排除原因: null,
  排除時間: null,
  ...overrides,
});

const respond = (rows: MechanicalSuspectMeasurement[]) => {
  vi.mocked(mechanicalApi.suspects).mockResolvedValue({
    success: true,
    data: rows,
    total: rows.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
    rule: { iqr_fence: 5, min_group_size: 10 },
  });
};

const renderPanel = (onEdit = vi.fn()) => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MechanicalSuspectPanel onEdit={onEdit} />
    </QueryClientProvider>,
  );
  return onEdit;
};

describe('MechanicalSuspectPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.mockReturnValue({ hasPermission: () => true });
    respond([suspect()]);
  });

  it('列出疑似異常值、同爐次其他值與提示', async () => {
    renderPanel();

    expect(await screen.findByText('37128')).toBeInTheDocument();
    expect(screen.getByText('疑似小數點位置錯誤，可能應為 371.28')).toBeInTheDocument();
    expect(screen.getByText('爐門1：379.64')).toBeInTheDocument();
    expect(screen.getByText('280.5 ～ 460.1')).toBeInTheDocument();
    expect(mechanicalApi.suspects).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, include_excluded: false }),
    );
  });

  it('依項目篩選並重設回第一頁', async () => {
    renderPanel();
    await screen.findByText('37128');

    fireEvent.change(screen.getByLabelText('量測項目'), { target: { value: '硬度' } });

    await waitFor(() => expect(mechanicalApi.suspects).toHaveBeenLastCalledWith(
      expect.objectContaining({ item: '硬度', page: 1 }),
    ));
  });

  it('編輯按鈕開啟該爐次表單', async () => {
    const onEdit = renderPanel();
    await screen.findByText('37128');

    fireEvent.click(screen.getByRole('button', { name: '編輯' }));

    expect(onEdit).toHaveBeenCalledWith(1428);
  });

  it('排除統計必須填寫原因後才能送出', async () => {
    vi.mocked(mechanicalApi.setExclusion).mockResolvedValue({
      id: 501, 排除統計: true, 排除原因: '小數點誤植', 排除者ID: 1, 排除時間: '2026-10-13T00:00:00+00:00',
    });
    renderPanel();
    await screen.findByText('37128');

    fireEvent.click(screen.getByRole('button', { name: '排除統計' }));
    const dialog = await screen.findByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: '確認排除' });
    expect(confirm).toBeDisabled();

    fireEvent.change(within(dialog).getByLabelText('原因'), { target: { value: '  小數點誤植 ' } });
    fireEvent.click(confirm);

    await waitFor(() => expect(mechanicalApi.setExclusion).toHaveBeenCalledWith(501, true, '小數點誤植'));
    expect(toast.success).toHaveBeenCalledWith('已排除統計');
  });

  it('已排除的值可恢復統計', async () => {
    respond([suspect({ 排除統計: true, 排除原因: '誤植' })]);
    vi.mocked(mechanicalApi.setExclusion).mockResolvedValue({
      id: 501, 排除統計: false, 排除原因: null, 排除者ID: null, 排除時間: null,
    });
    renderPanel();
    expect(await screen.findByText('已排除：誤植')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '恢復統計' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('原因'), { target: { value: '已確認原值正確' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '確認恢復' }));

    await waitFor(() => expect(mechanicalApi.setExclusion).toHaveBeenCalledWith(501, false, '已確認原值正確'));
  });

  it('缺少 SPC 管理權限時停用排除按鈕', async () => {
    authMock.mockReturnValue({ hasPermission: (permission: string) => permission !== 'spc.manage' });
    renderPanel();
    await screen.findByText('37128');

    expect(screen.getByRole('button', { name: '排除統計' })).toBeDisabled();
  });

  it('沒有疑似異常值時顯示提示文字', async () => {
    respond([]);
    renderPanel();

    expect(await screen.findByText('目前沒有疑似異常值')).toBeInTheDocument();
  });
});
