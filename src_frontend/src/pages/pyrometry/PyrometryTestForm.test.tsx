import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import api from '../../services/api';
import PyrometryTestForm from './PyrometryTestForm';

vi.mock('../../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('./ReportFieldsSection', () => ({
  default: () => <div data-testid="report-fields" />,
}));

vi.mock('./TusSection', () => ({
  default: () => <div data-testid="tus-section" />,
}));

vi.mock('./SatSection', () => ({
  default: () => <div data-testid="sat-section" />,
}));

vi.mock('./FurnaceRecorderSection', () => ({
  default: () => <div data-testid="furnace-recorder" />,
}));

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

const testResponse = (id: number, date: string) => ({
  data: {
    main: {
      爐子ID: 1,
      測試類型: 'TUS',
      測試日期: date,
      設定溫度: String(180 + id),
      允許公差: '10',
      測試人員: null,
      測試儀器編號: `INST-${id}`,
      標準校正儀器編號: '',
      儀器校正到期日: '',
      備註: '',
    },
    tus_points: [],
    sat_points: [],
    曲線資料: null,
    報告欄位: {},
  },
});

const renderForm = (editId: number) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <PyrometryTestForm editId={editId} onClose={() => undefined} onSaved={() => undefined} />
    </QueryClientProvider>,
  );
  return { ...result, queryClient };
};

describe('PyrometryTestForm', () => {
  it('ignores stale edit detail responses when editId changes', async () => {
    const first = deferred<ReturnType<typeof testResponse>>();
    const second = deferred<ReturnType<typeof testResponse>>();

    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/pyrometry/furnaces?active_only=1') {
        return Promise.resolve({ data: { data: [] } });
      }
      if (url === '/inspectors') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/pyrometry/tests/1') return first.promise;
      if (url === '/pyrometry/tests/2') return second.promise;
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    const { rerender, queryClient } = renderForm(1);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/pyrometry/tests/1'));

    rerender(
      <QueryClientProvider client={queryClient}>
        <PyrometryTestForm editId={2} onClose={() => undefined} onSaved={() => undefined} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/pyrometry/tests/2'));

    await act(async () => {
      second.resolve(testResponse(2, '2026-06-02'));
    });
    await waitFor(() => expect(screen.getByDisplayValue('2026-06-02')).toBeInTheDocument());

    await act(async () => {
      first.resolve(testResponse(1, '2026-06-01'));
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue('2026-06-02')).toBeInTheDocument();
      expect(screen.queryByDisplayValue('2026-06-01')).not.toBeInTheDocument();
    });
  });

  it('blocks save when an excluded measurement point is missing a reason', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/pyrometry/furnaces?active_only=1') {
        return Promise.resolve({ data: { data: [] } });
      }
      if (url === '/inspectors') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/pyrometry/tests/1') {
        return Promise.resolve({
          data: {
            main: {
              爐子ID: 1,
              測試類型: 'TUS',
              測試日期: '2026-06-01',
              設定溫度: '180',
              允許公差: '10',
              測試人員: null,
              測試儀器編號: 'INST-1',
              標準校正儀器編號: '',
              儀器校正到期日: '',
              備註: '',
            },
            tus_points: [
              { 點位: 'TUS-1', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '', 已排除: true, 排除原因: '' },
            ],
            sat_points: [],
            曲線資料: null,
            報告欄位: {},
          },
        });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    renderForm(1);

    await waitFor(() => expect(screen.getByDisplayValue('2026-06-01')).toBeInTheDocument());

    const saveButton = screen.getByRole('button', { name: '儲存' });
    await act(async () => {
      fireEvent.click(saveButton);
    });

    await waitFor(() => {
      expect(screen.getByText('排除的量測點必須填寫排除原因')).toBeInTheDocument();
    });
    expect(api.post).not.toHaveBeenCalled();
    expect(api.put).not.toHaveBeenCalled();
  });

  it('使用者修改欄位後重新載入資料不會覆寫輸入（hydrate 只執行一次）', async () => {
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === '/pyrometry/furnaces?active_only=1') {
        return Promise.resolve({ data: { data: [] } });
      }
      if (url === '/inspectors') {
        return Promise.resolve({ data: [] });
      }
      if (url === '/pyrometry/tests/1') {
        return Promise.resolve(testResponse(1, '2026-06-01'));
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    const { queryClient } = renderForm(1);
    await waitFor(() => expect(screen.getByDisplayValue('2026-06-01')).toBeInTheDocument());

    fireEvent.change(screen.getByDisplayValue('2026-06-01'), { target: { value: '2026-06-05' } });
    expect(screen.getByDisplayValue('2026-06-05')).toBeInTheDocument();

    // 模擬伺服器資料已變更並重新載入（另一使用者改過日期）
    await act(async () => {
      queryClient.setQueryData(['pyrometry-test-detail', 1], testResponse(1, '2026-06-02').data);
      // 讓出事件迴圈：React Query 通知微任務、React re-render 與 passive effects 依序執行
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // 確認使用者修改未被覆寫
    expect(screen.getByDisplayValue('2026-06-05')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('2026-06-01')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('2026-06-02')).not.toBeInTheDocument();
  });
});
