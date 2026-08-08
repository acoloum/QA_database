import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ShippingModal from './ShippingModal';
import type { ToleranceResult } from '../../types';

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

const deferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(res => {
    resolve = res;
  });
  return { promise, resolve };
};

const checkToleranceMutate = vi.fn();

let shippingDetail: Record<string, unknown> | null = null;

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// ShippingModal 改走統一 useInspectors hook（內部使用 useQuery），測試直接 mock 該 hook 資料
vi.mock('../../hooks/useInspectors', () => ({
  useInspectors: (() => {
    const data = [{ id: 1, name: '檢驗員A' }];
    return () => ({ data });
  })(),
}));

vi.mock('../../hooks/useShipping', () => {
  const vendors = [{ id: 10, name: '廠商A' }];
  return {
    useVendors: () => ({ data: vendors }),
    useShippingDetail: () => ({ data: shippingDetail, isLoading: false }),
    useCreateShipping: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useUpdateShipping: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useCheckTolerance: () => ({ mutateAsync: checkToleranceMutate }),
  };
});

const toleranceResponse = (specLabel: string): ToleranceResult => ({
  success: true,
  found: true,
  is_valid: true,
  violates: [],
  message: specLabel,
  tolerances: [{
    項目: '外徑',
    標準值: null,
    公差上限: null,
    公差下限: null,
    尺寸上限: 10,
    尺寸下限: 1,
    單位: 'mm',
  }],
});

describe('ShippingModal', () => {
  beforeEach(() => {
    checkToleranceMutate.mockReset();
    shippingDetail = null;
  });

  it('載入含分段鍵的紀錄時自動展開外徑三列', async () => {
    shippingDetail = {
      識別碼: 5,
      檢驗日期: '2026-07-01',
      檢驗人員: '檢驗員A',
      廠商中文名稱: '廠商A',
      材質: 'A6061',
      檢驗規格: '10*2',
      組數: 1,
      measurements: {
        '1': {
          '外徑@前段': { value_min: 9.8, value_max: 10.1, is_ng: false },
          '外徑@中段': { value_min: 9.9, value_max: 10.2, is_ng: false },
          '外徑@後段': { value_min: 9.7, value_max: 10.0, is_ng: false },
        },
      },
    };

    render(
      <ShippingModal show editId={5} handleClose={() => undefined} onSuccess={() => undefined} />,
    );

    await waitFor(() => expect(screen.getByText('外徑(前)')).toBeInTheDocument());
    expect(screen.getByText('外徑(中)')).toBeInTheDocument();
    expect(screen.getByText('外徑(後)')).toBeInTheDocument();
    expect(screen.getByDisplayValue('9.9')).toBeInTheDocument();
  });

  it('關閉分段量測時以自訂確認視窗提示，取消不變、確認才收合', async () => {
    shippingDetail = {
      識別碼: 6,
      檢驗日期: '2026-07-01',
      檢驗人員: '檢驗員A',
      廠商中文名稱: '廠商A',
      材質: 'A6061',
      檢驗規格: '10*2',
      組數: 1,
      measurements: {
        '1': {
          '外徑@前段': { value_min: 9.8, value_max: 10.1, is_ng: false },
          '外徑@中段': { value_min: 9.9, value_max: 10.2, is_ng: false },
          '外徑@後段': { value_min: 9.7, value_max: 10.0, is_ng: false },
        },
      },
    };

    render(
      <ShippingModal show editId={6} handleClose={() => undefined} onSuccess={() => undefined} />,
    );

    await waitFor(() => expect(screen.getByText('外徑(中)')).toBeInTheDocument());

    const findSegmentSwitch = () =>
      screen.getAllByTitle('分段量測(前/中/後)').find(el => el.id === 'segment-switch-外徑') as HTMLInputElement;
    expect(findSegmentSwitch()).toBeTruthy();

    // 取得確認視窗（依標題定位）的容器，避免與出貨表單的按鈕混淆
    const getConfirmDialog = () =>
      screen.getByText('關閉分段量測').closest('.modal') as HTMLElement;

    // 點擊關閉分段：應跳出自訂確認視窗，而非原生 window.confirm
    fireEvent.click(findSegmentSwitch());
    await waitFor(() => expect(screen.getByText('關閉分段量測')).toBeInTheDocument());
    expect(screen.getByText('關閉分段後將只保留前段數據，確定要關閉嗎？')).toBeInTheDocument();

    // 取消：資料維持不變，中段仍在
    fireEvent.click(within(getConfirmDialog()).getByText('取消'));
    await waitFor(() => expect(screen.queryByText('關閉分段量測')).not.toBeInTheDocument());
    expect(screen.getByText('外徑(中)')).toBeInTheDocument();

    // 再次關閉並確認：收合分段，只保留前段，中段消失
    fireEvent.click(findSegmentSwitch());
    await waitFor(() => expect(screen.getByText('關閉分段量測')).toBeInTheDocument());
    fireEvent.click(within(getConfirmDialog()).getByText('關閉'));

    await waitFor(() => expect(screen.queryByText('外徑(中)')).not.toBeInTheDocument());
    expect(screen.queryByText('外徑(後)')).not.toBeInTheDocument();
    expect(screen.getByText('外徑')).toBeInTheDocument();
  });

  it('ignores stale tolerance lookup results after form keys change', async () => {
    const stale = deferred<ToleranceResult>();
    const current = deferred<ToleranceResult>();
    checkToleranceMutate
      .mockReturnValueOnce(stale.promise)
      .mockReturnValueOnce(current.promise);

    render(
      <ShippingModal
        show
        editId={null}
        handleClose={() => undefined}
        onSuccess={() => undefined}
      />,
    );

    const selects = screen.getAllByRole('combobox');
    const textInputs = screen.getAllByRole('textbox');
    const vendorSelect = selects[1];
    const specInput = textInputs[0];
    const materialInput = textInputs[1];

    fireEvent.change(vendorSelect, { target: { value: '廠商A' } });
    fireEvent.change(materialInput, { target: { value: 'A6061' } });
    fireEvent.change(specInput, { target: { value: 'SPEC-OLD' } });

    await waitFor(() => expect(checkToleranceMutate).toHaveBeenCalledTimes(1));

    fireEvent.change(specInput, { target: { value: 'SPEC-NEW' } });
    await waitFor(() => expect(checkToleranceMutate).toHaveBeenCalledTimes(2));

    await act(async () => {
      stale.resolve(toleranceResponse('old'));
    });
    expect(screen.queryByText(/公差標準已載入/)).not.toBeInTheDocument();

    await act(async () => {
      current.resolve(toleranceResponse('new'));
    });
    await waitFor(() => expect(screen.getByText(/公差標準已載入/)).toBeInTheDocument());
  });
  it('韋伯專用規格仍保留已存檔的硬度欄，且輸入不被項目重算清掉', async () => {
    // 公差只有韋伯氏硬度時主硬度欄會隱藏；但既有紀錄已存有硬度值，隱藏會讓值被孤立。
    // 另：項目清單若反過來依賴編輯中的量測值會形成循環並清掉剛輸入的內容。
    shippingDetail = {
      識別碼: 7,
      檢驗日期: '2026-07-01',
      檢驗人員: '檢驗員A',
      廠商中文名稱: '廠商A',
      材質: 'A6061',
      檢驗規格: '10*2',
      組數: 1,
      measurements: {
        '1': { '硬度': { value_single: 8, is_ng: false } },
      },
    };
    checkToleranceMutate.mockResolvedValue({
      success: true,
      found: true,
      tolerances: [{
        項目: '韋伯氏硬度', 標準值: null, 公差上限: null, 公差下限: null,
        尺寸上限: null, 尺寸下限: 10, 單位: 'HW',
      }],
    });

    render(
      <ShippingModal show editId={7} handleClose={() => undefined} onSuccess={() => undefined} />,
    );

    // 已存檔的硬度值仍在，未因韋伯專用公差而消失
    await waitFor(() => expect(screen.getByDisplayValue('8')).toBeInTheDocument());
    // 韋伯欄位同時可用
    await waitFor(() => expect(screen.getByText('韋伯氏硬度(HW)')).toBeInTheDocument());
  });
});
