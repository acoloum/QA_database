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
    getVendors: vi.fn(),
    getOptions: vi.fn(),
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
    判定狀態: 'OK' as const,
  },
  batches: [{ 序號: 1, 擠製編號: 'EX-001', 爐具編號: 'F-001' }],
  measurements: [
    {
      量測項目: '硬度' as const, 測量位置: '爐門' as const, 取樣序: 1, 量測值: 95,
      排除統計: false, 排除原因: null, 排除者ID: null, 排除時間: null,
    },
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
    vi.mocked(mechanicalApi.getVendors).mockResolvedValue([
      { id: 42, name: '安泰' },
      { id: 51, name: '宏達' },
    ]);
    vi.mocked(mechanicalApi.getOptions).mockResolvedValue({
      materials: ['6061-T651', '6063'],
      product_sizes: ['36*25.2', '62.5*2.3'],
    });
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

    await screen.findByRole('option', { name: '安泰' });
    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.change(screen.getByLabelText('廠商'), { target: { value: '42' } });
    fireEvent.change(screen.getByLabelText('測試日期'), { target: { value: '2026-07-23' } });
    fireEvent.change(screen.getByPlaceholderText('擠製編號'), { target: { value: 'EX-001' } });
    fireEvent.change(screen.getByPlaceholderText('爐具編號'), { target: { value: 'F-001' } });
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 1'), { target: { value: '95' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    await waitFor(() => {
      expect(mechanicalApi.create).toHaveBeenCalledWith({
        產品尺寸: '62.5 x 2.3',
        材質: '6061-T651',
        廠商ID: 42,
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

  it('新增與編輯皆顯示廠商選擇器並以所選廠商查規格', async () => {
    renderForm();
    expect(await screen.findByRole('option', { name: '安泰' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('廠商'), { target: { value: '51' } });
    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    await waitFor(() => expect(mechanicalApi.getSpec).toHaveBeenCalledWith(
      '6061-T651', '62.5 x 2.3', 51,
    ));
  });

  it('選擇廠商後載入該廠商的材質與尺寸搜尋建議', async () => {
    renderForm();
    await screen.findByRole('option', { name: '安泰' });
    fireEvent.change(screen.getByLabelText('廠商'), { target: { value: '42' } });

    await waitFor(() => expect(mechanicalApi.getOptions).toHaveBeenCalledWith(42));
    await waitFor(() => {
      expect(document.querySelector('#mechanical-material-options option[value="6063"]')).not.toBeNull();
      expect(document.querySelector('#mechanical-product-size-options option[value="36*25.2"]')).not.toBeNull();
    });
    expect(screen.getByLabelText('產品尺寸')).toHaveAttribute('list', 'mechanical-product-size-options');
    expect(screen.getByLabelText('材質')).toHaveAttribute('list', 'mechanical-material-options');
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

  it('編輯時等待 detail hydrate 前不顯示表單、不查規格，完成後才以廠商 ID 查詢', async () => {
    let resolveDetail: ((value: typeof editDetail) => void) | undefined;
    vi.mocked(mechanicalApi.getDetail).mockImplementation(() => new Promise((resolve) => {
      resolveDetail = resolve;
    }));
    renderForm(8);

    expect(screen.getByRole('status')).toHaveTextContent('載入檢驗資料中…');
    expect(screen.queryByLabelText('產品尺寸')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '儲存' })).not.toBeInTheDocument();
    expect(mechanicalApi.getSpec).not.toHaveBeenCalled();

    resolveDetail?.(editDetail);

    expect(await screen.findByDisplayValue('62.5 x 2.3')).toBeInTheDocument();
    await waitFor(() => expect(mechanicalApi.getSpec).toHaveBeenCalledWith('6061-T651', '62.5 x 2.3', 42));
  });

  it('顯示規格下限並即時標示低於下限的 NG 值', async () => {
    renderForm();

    await screen.findByRole('option', { name: '安泰' });
    fireEvent.change(screen.getByLabelText('廠商'), { target: { value: '42' } });
    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    expect(await screen.findByText('90')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 1'), { target: { value: '89' } });

    const input = screen.getByLabelText('硬度－爐門－取樣 1');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-errormessage', 'mechanical-measurement-hardness-door-1-ng-error');
    expect(document.getElementById('mechanical-measurement-hardness-door-1-ng-error')).toHaveTextContent('NG：低於下限 90');
    expect(screen.getByText('NG：低於下限 90')).toBeInTheDocument();
  });

  it('載入既有資料失敗時僅顯示錯誤操作，且不得更新資料', async () => {
    vi.mocked(mechanicalApi.getDetail).mockRejectedValue(new Error('讀取失敗'));
    const { onClose } = renderForm(8);

    expect(await screen.findByRole('alert')).toHaveTextContent('載入機械性質檢驗資料失敗，請稍後再試');
    expect(screen.queryByLabelText('產品尺寸')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '儲存' })).not.toBeInTheDocument();
    expect(mechanicalApi.update).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '關閉' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('規格查詢與儲存失敗時顯示明確錯誤', async () => {
    vi.mocked(mechanicalApi.getSpec).mockRejectedValue(new Error('規格讀取失敗'));
    vi.mocked(mechanicalApi.create).mockRejectedValue(new Error('儲存失敗'));
    renderForm();

    await screen.findByRole('option', { name: '安泰' });
    fireEvent.change(screen.getByLabelText('廠商'), { target: { value: '42' } });
    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    expect(await screen.findByRole('alert')).toHaveTextContent('載入機械性質規格失敗，請稍後再試');

    fireEvent.click(screen.getByRole('button', { name: '儲存' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('儲存失敗'));
  });

  it('垃圾量測字串顯示可存取錯誤並阻止建立', async () => {
    renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 1'), { target: { value: 'abc' } });
    const input = screen.getByLabelText('硬度－爐門－取樣 1');

    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-errormessage', 'mechanical-measurement-hardness-door-1-format-error');
    expect(document.getElementById('mechanical-measurement-hardness-door-1-format-error')).toHaveTextContent('量測值必須為有限數字');
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(toast.error).toHaveBeenCalledWith('請修正量測值格式錯誤');
    expect(mechanicalApi.create).not.toHaveBeenCalled();
  });

  it('超過四位小數的量測值顯示可存取錯誤並阻止建立', async () => {
    renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 1'), { target: { value: '59.99996' } });
    const input = screen.getByLabelText('硬度－爐門－取樣 1');

    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-errormessage', 'mechanical-measurement-hardness-door-1-format-error');
    expect(document.getElementById('mechanical-measurement-hardness-door-1-format-error'))
      .toHaveTextContent('量測值最多只能有 4 位小數');
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(toast.error).toHaveBeenCalledWith('請修正量測值格式錯誤');
    expect(mechanicalApi.create).not.toHaveBeenCalled();
  });

  it('收合的非法 EC 第 2 取樣會在儲存時展開並阻止建立', async () => {
    renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.click(screen.getByLabelText('異常加測（第2取樣）'));
    fireEvent.click(screen.getByLabelText('顯示導電度 (EC)'));
    fireEvent.change(screen.getByLabelText('EC值－爐門－取樣 2'), { target: { value: 'NaN' } });
    fireEvent.click(screen.getByLabelText('異常加測（第2取樣）'));
    fireEvent.click(screen.getByLabelText('顯示導電度 (EC)'));
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(toast.error).toHaveBeenCalledWith('請修正量測值格式錯誤');
    expect(screen.getByLabelText('異常加測（第2取樣）')).toBeChecked();
    expect(screen.getByLabelText('顯示導電度 (EC)')).toBeChecked();
    expect(screen.getByLabelText('EC值－爐門－取樣 2')).toHaveAttribute('aria-invalid', 'true');
    expect(mechanicalApi.create).not.toHaveBeenCalled();
  });

  it('收合後仍會保留有效的 EC 與第 2 取樣量測值', async () => {
    renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.click(screen.getByLabelText('異常加測（第2取樣）'));
    fireEvent.click(screen.getByLabelText('顯示導電度 (EC)'));
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 2'), { target: { value: '91' } });
    fireEvent.change(screen.getByLabelText('EC值－爐頂－取樣 1'), { target: { value: '55.2' } });
    fireEvent.click(screen.getByLabelText('異常加測（第2取樣）'));
    fireEvent.click(screen.getByLabelText('顯示導電度 (EC)'));
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    await waitFor(() => expect(mechanicalApi.create).toHaveBeenCalledWith(expect.objectContaining({
      measurements: expect.arrayContaining([
        { 量測項目: '硬度', 測量位置: '爐門', 取樣序: 2, 量測值: 91 },
        { 量測項目: 'EC值', 測量位置: '爐頂', 取樣序: 1, 量測值: 55.2 },
      ]),
    })));
  });

  it('儲存請求未完成時重複點擊不會建立第二筆資料', async () => {
    let resolveCreate: ((value: { success: boolean; id: number }) => void) | undefined;
    vi.mocked(mechanicalApi.create).mockImplementation(() => new Promise((resolve) => {
      resolveCreate = resolve;
    }));
    renderForm();

    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));
    fireEvent.click(screen.getByRole('button', { name: '儲存中…' }));

    expect(mechanicalApi.create).toHaveBeenCalledTimes(1);
    resolveCreate?.({ success: true, id: 9 });
  });

  it('排除量測顯示稽核證據且一般編輯不可修改', async () => {
    vi.mocked(mechanicalApi.getDetail).mockResolvedValue({
      ...editDetail,
      measurements: [{
        ...editDetail.measurements[0],
        是否超差: true,
        排除統計: true,
        排除原因: '儀器異常',
        排除者ID: 7,
        排除時間: '2026-07-23T08:00:00+00:00',
      }],
    });
    renderForm(8);

    const input = await screen.findByLabelText('硬度－爐門－取樣 1');
    expect(input).toBeDisabled();
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute(
      'aria-describedby',
      'mechanical-measurement-hardness-door-1-excluded-snapshot',
    );
    expect(input).toHaveAttribute(
      'aria-errormessage',
      'mechanical-measurement-hardness-door-1-excluded-snapshot',
    );
    expect(document.getElementById('mechanical-measurement-hardness-door-1-excluded-snapshot'))
      .toHaveTextContent('歷史快照');
    expect(screen.getByText(/已排除：儀器異常/)).toBeInTheDocument();
  });

  it('排除量測使用歷史下限與判定，不受目前規格變更影響', async () => {
    vi.mocked(mechanicalApi.getDetail).mockResolvedValue({
      ...editDetail,
      measurements: [{
        ...editDetail.measurements[0],
        量測值: 95,
        下限: 90,
        是否超差: false,
        排除統計: true,
        排除原因: '儀器異常',
      }],
    });
    vi.mocked(mechanicalApi.getSpec).mockResolvedValue({ 硬度: 100 });
    renderForm(8);

    const input = await screen.findByLabelText('硬度－爐門－取樣 1');
    expect(input).toHaveAttribute('aria-invalid', 'false');
    expect(screen.getByText(/歷史快照：下限 90，判定 OK/)).toBeInTheDocument();
    expect(screen.queryByText('NG：低於下限 100')).not.toBeInTheDocument();
  });

  it('儲存失敗時顯示後端提供的 403 訊息', async () => {
    vi.mocked(mechanicalApi.create).mockRejectedValue({
      response: { status: 403, data: { error: '您沒有建立機械性質檢驗的權限' } },
    });
    renderForm();
    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('您沒有建立機械性質檢驗的權限');
  });

  it('相容 interceptor 轉換後的標準 Error 訊息且不重複 toast', async () => {
    const error = Object.assign(new Error('資料庫服務暫時無法使用'), { _toasted: true });
    vi.mocked(mechanicalApi.create).mockRejectedValue(error);
    renderForm();
    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '62.5 x 2.3' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('資料庫服務暫時無法使用');
    expect(toast.error).not.toHaveBeenCalledWith('資料庫服務暫時無法使用');
  });

  it('前端限制文字長度與 NUMERIC(12,4) 範圍', async () => {
    renderForm();
    expect(screen.getByLabelText('產品尺寸')).toHaveAttribute('maxlength', '50');
    expect(screen.getByLabelText('材質')).toHaveAttribute('maxlength', '50');
    expect(screen.getByLabelText('T4溫度/時間')).toHaveAttribute('maxlength', '100');
    fireEvent.change(screen.getByLabelText('產品尺寸'), { target: { value: '36*25.2' } });
    fireEvent.change(screen.getByLabelText('硬度－爐門－取樣 1'), {
      target: { value: '1e100' },
    });
    fireEvent.click(screen.getByRole('button', { name: '儲存' }));
    expect(mechanicalApi.create).not.toHaveBeenCalled();
    expect(screen.getByText('量測值超出 NUMERIC(12,4) 可儲存範圍')).toBeInTheDocument();
  });
});
