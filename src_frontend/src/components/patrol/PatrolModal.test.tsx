import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import appCss from '../../App.css?raw';
import PatrolModal from './PatrolModal';
import * as usePatrolHooks from '../../hooks/usePatrol';
import * as useSpcStudiesHooks from '../../hooks/useSpcStudies';

vi.mock('../../hooks/usePatrol', async () => {
  const actual = await vi.importActual('../../hooks/usePatrol');
  return {
    ...actual,
    usePatrolOptions: vi.fn(() => ({
      data: { machines: [], operators: [], inspectors: [], customers: [] },
    })),
    usePatrolDetail: vi.fn(() => ({ data: null, isLoading: false })),
    useCreatePatrol: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
    useUpdatePatrol: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
    usePatrolLiveLimits: vi.fn(),
  };
});

vi.mock('../../hooks/useSpcStudies', async () => {
  const actual = await vi.importActual('../../hooks/useSpcStudies');
  return {
    ...actual,
    useAnalyzeSpcStudy: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
    useSaveSpcOcap: vi.fn(() => ({
      mutate: vi.fn(), reset: vi.fn(), isPending: false, isError: false,
    })),
    useSpcAssignees: vi.fn(() => ({ data: [], isLoading: false, isError: false })),
  };
});

const renderPatrolModal = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PatrolModal show handleClose={vi.fn()} onSuccess={vi.fn()} editId={null} />
    </QueryClientProvider>,
  );
};

describe('PatrolModal NG 欄位樣式', () => {
  it('呼吸燈 keyframes 不使用瀏覽器會忽略的 important 宣告', () => {
    const keyframes = appCss.match(/@keyframes patrol-ng-breathing\s*\{[\s\S]*?\n\}/)?.[0] ?? '';

    expect(keyframes).toContain('@keyframes patrol-ng-breathing');
    expect(keyframes).toContain('box-shadow');
    expect(keyframes).not.toContain('!important');
  });
});

describe('PatrolModal 即時模式', () => {
  it('即時模式關閉時不查詢即時界限；開啟切換後開關狀態立即反映', async () => {
    const liveLimitsMock = vi.fn().mockReturnValue({
      data: { found: false }, isFetching: false,
    });
    vi.mocked(usePatrolHooks.usePatrolLiveLimits).mockImplementation(liveLimitsMock);

    renderPatrolModal();

    const liveModeToggle = screen.getByRole('checkbox', { name: '即時模式' });
    expect(liveModeToggle).not.toBeChecked();

    // 尚未開啟即時模式、也尚未有任何量測格失焦，hook 應以 enabled=false 呼叫
    // （元件仍會依 React hooks 規則無條件呼叫 usePatrolLiveLimits，
    // 但傳入的第二個參數 enabled 必須是 false，代表 React Query 實際上不會發出查詢）
    const lastCallBeforeToggle = liveLimitsMock.mock.calls.at(-1);
    expect(lastCallBeforeToggle?.[1]).toBe(false);

    await userEvent.click(liveModeToggle);
    expect(liveModeToggle).toBeChecked();

    // 開啟即時模式後，尚未讓任何量測格失焦，仍不應觸發查詢
    const lastCallAfterToggle = liveLimitsMock.mock.calls.at(-1);
    expect(lastCallAfterToggle?.[1]).toBe(false);
  });

  it('即時模式開啟後，量測格失焦會以 enabled=true 查詢該 item/position 的即時界限', async () => {
    const liveLimitsMock = vi.fn().mockReturnValue({
      data: { found: false }, isFetching: false,
    });
    vi.mocked(usePatrolHooks.usePatrolLiveLimits).mockImplementation(liveLimitsMock);

    renderPatrolModal();

    await userEvent.click(screen.getByRole('checkbox', { name: '即時模式' }));

    const minInputs = screen.getAllByRole('spinbutton');
    // 表格第一組「前段/外徑」的 MIN 欄位（依渲染順序為第一個輸入框）
    await userEvent.click(minInputs[0]);
    await userEvent.tab();

    // 由於 mock 每次都直接回傳資料（不論 enabled 為何），caching 的 useEffect
    // 會在下一次 render 就把結果存進 liveLimitsCache，讓 enabled 立刻變回 false，
    // 因此改為檢查「曾經以 enabled=true 查詢過該 item/position」而非檢查最後一次呼叫
    const enabledCall = liveLimitsMock.mock.calls.find(
      ([params, enabled]) => enabled === true && params.pos === '前段' && params.item === '外徑',
    );
    expect(enabledCall).toBeDefined();
  });
});

describe('PatrolModal 即時模式存檔後的正式異常事件面板（Bug 1 回歸測試）', () => {
  it('存檔觸發的事件卡片，在外層 show 變為 false（Modal 關閉）後仍留在 DOM 中', async () => {
    // 準備下拉選單有可選項目，讓「機台/主機手/檢驗員」必填驗證能通過
    vi.mocked(usePatrolHooks.usePatrolOptions).mockReturnValue({
      data: {
        machines: [{ id: 1, name: 'M1' }],
        operators: [{ id: 2, name: 'Op1' }],
        inspectors: [{ id: 3, name: 'Insp1' }],
        customers: [],
      },
    } as ReturnType<typeof usePatrolHooks.usePatrolOptions>);

    const createMutateAsync = vi.fn().mockResolvedValue({ id: 100 });
    vi.mocked(usePatrolHooks.useCreatePatrol).mockReturnValue({
      mutateAsync: createMutateAsync, isPending: false,
    } as ReturnType<typeof usePatrolHooks.useCreatePatrol>);

    // 讓「前段/外徑」量測格失焦時查到已存在的即時界限，且數值必定超出上限觸發違規
    const liveLimitsMock = vi.fn((params: { pos: string; item: string }) => {
      if (params.pos === '前段' && params.item === '外徑') {
        return {
          data: {
            found: true,
            recent_values: [],
            x_cl: 10, x_ucl: 12, x_lcl: 8,
            r_cl: 1, r_ucl: 2, r_lcl: 0,
          },
          isFetching: false,
        };
      }
      return { data: { found: false }, isFetching: false };
    });
    vi.mocked(usePatrolHooks.usePatrolLiveLimits).mockImplementation(liveLimitsMock);

    // 存檔後觸發的正式 SPC 判定，回傳一筆開放中的異常事件
    const analyzeOngoingMock = vi.fn().mockResolvedValue({
      monitoring_limit: {
        id: 900,
        status: 'active',
        events: [{
          id: 501,
          limit_version_id: 900,
          study_version_id: 1,
          sample_id: null,
          chart_kind: 'location',
          rule_code: 'Rule 1: 超出控制限',
          point_index: 0,
          observed_value: 20,
          status: 'open',
          created_at: '2026-07-20T00:00:00Z',
          ocap: null,
        }],
      },
    });
    vi.mocked(useSpcStudiesHooks.useAnalyzeSpcStudy).mockReturnValue({
      mutateAsync: analyzeOngoingMock, isPending: false,
    } as ReturnType<typeof useSpcStudiesHooks.useAnalyzeSpcStudy>);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const handleClose = vi.fn();
    const { rerender } = render(
      <QueryClientProvider client={queryClient}>
        <PatrolModal show handleClose={handleClose} onSuccess={vi.fn()} editId={null} />
      </QueryClientProvider>,
    );

    // 開啟即時模式
    await userEvent.click(screen.getByRole('checkbox', { name: '即時模式' }));

    // 選擇必填欄位：機台／主機手／檢驗員
    const selects = screen.getAllByRole('combobox');
    await userEvent.selectOptions(selects[0], '1');
    await userEvent.selectOptions(selects[1], '2');
    await userEvent.selectOptions(selects[2], '3');

    // 輸入「前段/外徑」的量測值並失焦，觸發即時界限查詢與違規判定
    const spins = screen.getAllByRole('spinbutton');
    await userEvent.type(spins[0], '20');
    await userEvent.tab();
    await userEvent.type(spins[1], '20');
    await userEvent.tab();

    // 儲存 — 依序觸發：新增巡檢紀錄 → 正式 SPC 判定 → onSuccess/handleClose
    await userEvent.click(screen.getByRole('button', { name: /^儲存$/ }));

    await waitFor(() => {
      expect(screen.getByText(/查看建議/)).toBeInTheDocument();
    });

    // 模擬真實情境：父層 PatrolPage 收到 handleClose() 後把 show 改為 false，
    // 但 PatrolModal 元件本身不會卸載（父層仍持續渲染同一個 <PatrolModal>）
    rerender(
      <QueryClientProvider client={queryClient}>
        <PatrolModal show={false} handleClose={handleClose} onSuccess={vi.fn()} editId={null} />
      </QueryClientProvider>,
    );

    // react-bootstrap 的 <Modal> 以 Fade（unmountOnExit）包住其子節點，
    // 關閉時會延遲一段轉場時間才真正卸載；等待超過該時間，
    // 確認事件卡片（Modal 的同層兄弟節點）不會被一併卸載
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 400));
    });

    expect(screen.getByText(/查看建議/)).toBeInTheDocument();
  });
});
