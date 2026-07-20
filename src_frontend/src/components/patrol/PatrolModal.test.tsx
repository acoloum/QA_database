import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import appCss from '../../App.css?raw';
import PatrolModal from './PatrolModal';
import * as usePatrolHooks from '../../hooks/usePatrol';

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
