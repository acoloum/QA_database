import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import MechanicalTestForm from './MechanicalTestForm';

vi.mock('../../services/mechanicalApi', () => ({
  mechanicalApi: {
    getDetail: vi.fn(),
    getSpec: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

const renderForm = (testId: number | null = null) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const onClose = vi.fn();
  const onSaved = vi.fn();

  render(
    <QueryClientProvider client={queryClient}>
      <MechanicalTestForm testId={testId} onClose={onClose} onSaved={onSaved} />
    </QueryClientProvider>,
  );

  return { onClose, onSaved };
};

const editDetail = {
  main: {
    識別碼: 8,
    產品尺寸: '62.5 x 2.3',
    材質: '6061-T651',
    廠商ID: 42,
    測試日期: '2026-07-23',
    T4溫度時間: '190°C / 3h',
    T6溫度時間: '180°C / 5h',
    備註: '既有備註',
    是否NG: false,
  },
  batches: [{ 序號: 1, 擠製編號: 'EX-001', 爐具編號: 'F-001' }],
  measurements: [
    { 量測項目: '硬度' as const, 測量位置: '爐門' as const, 取樣序: 1, 量測值: 95 },
  ],
};

describe('MechanicalTestForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(mechanicalApi.getSpec).mockResolvedValue({
      硬度: 90,
      抗拉強度: 240,
      降伏強度: 180,
      伸長率: 8,
    });
    vi.mocked(mechanicalApi.create).mockResolvedValue({ success: true, id: 9 });
    vi.mocked(mechanicalApi.update).mockResolvedValue({ success: true });
  });

  it('預設只顯示四個判定項目與第 1 取樣', () => {
    renderForm();

    expect(screen.getByText('硬度')).toBeInTheDocument();
    expect(screen.getByText('抗拉強度')).toBeInTheDocument();
    expect(screen.getByText('降伏強度')).toBeInTheDocument();
    expect(screen.getByText('伸長率')).toBeInTheDocument();
    expect(screen.queryByText('EC值')).not.toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '爐門 取樣 1' })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: '爐門 取樣 2' })).not.toBeInTheDocument();
  });

  it('開關會展開 EC 與第 2 取樣欄位', () => {
    renderForm();

    fireEvent.click(screen.getByLabelText('異常加測（第2取樣）'));
    fireEvent.click(screen.getByLabelText('顯示導電度 (EC)'));

    expect(screen.getByText('EC值')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '爐門 取樣 2' })).toBeInTheDocument();
    expect(screen.getByLabelText('EC值－爐頂－取樣 2')).toBeInTheDocument();
  });

  it('可動態新增並刪除批次', () => {
    renderForm();

    expect(screen.getAllByPlaceholderText('擠製編號')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: '新增一組' }));
    expect(screen.getAllByPlaceholderText('擠製編號')).toHaveLength(2);

    fireEvent.click(screen.getAllByRole('button', { name: '刪除批次' })[1]);
    expect(screen.getAllByPlaceholderText('擠製編號')).toHaveLength(1);
  });

  it('缺少產品尺寸時阻止儲存並提示必填欄位', async () => {
    renderForm();

    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(toast.error).toHaveBeenCalledWith('請填寫產品尺寸與材質');
    expect(mechanicalApi.create).not.toHaveBeenCalled();
  });

  it('新增時組成完整 payload 後呼叫建立 API', async () => {
    const { onSaved } = renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.change(screen.getByLabelText('測試日期'), { target: { value: '2026-07-23' } });
    fireEvent.change(screen.getByPlaceholderText('擠製編號'), { target: { value: 'EX-001' } });
    fireEvent.change(screen.getByPlaceholderText('爐具編號'), { target: { value: 'F-001' } });
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 1'), { target: { value: '95' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    await waitFor(() => {
      expect(mechanicalApi.create).toHaveBeenCalledWith({
        產品尺寸: '62.5 x 2.3',
        材質: '6061-T651',
        測試日期: '2026-07-23',
        T4溫度時間: '',
        T6溫度時間: '',
        備註: '',
        batches: [{ 序號: 1, 擠製編號: 'EX-001', 爐具編號: 'F-001' }],
        measurements: [{ 量測項目: '硬度', 測量位置: '爐門', 取樣序: 1, 量測值: 95 }],
      });
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it('編輯時載入既有資料、以廠商 ID 查規格並在更新 payload 保留該 ID', async () => {
    vi.mocked(mechanicalApi.getDetail).mockResolvedValue(editDetail);
    renderForm(8);

    expect(await screen.findByDisplayValue('62.5 x 2.3')).toBeInTheDocument();
    expect(screen.getByDisplayValue('EX-001')).toBeInTheDocument();
    expect(screen.getByDisplayValue('95')).toBeInTheDocument();
    await waitFor(() => expect(mechanicalApi.getSpec).toHaveBeenCalledWith('6061-T651', '62.5 x 2.3', 42));

    fireEvent.click(screen.getByRole('button', { name: '儲存' }));
    await waitFor(() => expect(mechanicalApi.update).toHaveBeenCalledWith(8, expect.objectContaining({ 廠商ID: 42 })));
  });

  it('顯示規格下限並即時標示低於下限的 NG 值', async () => {
    renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    expect(await screen.findByText('90')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 1'), { target: { value: '89' } });

    expect(screen.getByLabelText('硬度－爐門－取樣 1')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText('NG：低於下限 90')).toBeInTheDocument();
  });

  it('載入既有資料失敗時顯示明確錯誤', async () => {
    vi.mocked(mechanicalApi.getDetail).mockRejectedValue(new Error('讀取失敗'));
    renderForm(8);

    expect(await screen.findByRole('alert')).toHaveTextContent('載入機械性質檢驗資料失敗，請稍後再試');
  });

  it('規格查詢與儲存失敗時顯示明確錯誤', async () => {
    vi.mocked(mechanicalApi.getSpec).mockRejectedValue(new Error('規格讀取失敗'));
    vi.mocked(mechanicalApi.create).mockRejectedValue(new Error('儲存失敗'));
    renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    expect(await screen.findByRole('alert')).toHaveTextContent('載入機械性質規格失敗，請稍後再試');

    fireEvent.click(screen.getByRole('button', { name: '儲存' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('儲存失敗，請稍後再試'));
  });
});
