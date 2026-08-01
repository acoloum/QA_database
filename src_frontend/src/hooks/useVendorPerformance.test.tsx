import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import {
  useVendorPerformanceList,
  useVendorPerformanceHistory,
  useRefreshVendorPerformance,
} from './useVendorPerformance';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const makeRow = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: 1,
  vendor_id: 7,
  vendor_name: '測試廠商',
  period: '2026-08',
  inspection_count: 10,
  defect_count: 1,
  defect_rate: 10,
  capa_count: 2,
  avg_capa_days: 3.5,
  complaint_count: 0,
  score: 85,
  ...overrides,
});

describe('useVendorPerformance', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('透過 useVendorPerformanceList 依期間載入評比清單', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: { success: true, data: [makeRow()] },
    });

    const { result } = renderHook(() => useVendorPerformanceList('2026-08'), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/vendor-performance', {
      params: { period: '2026-08' },
    });
    expect(result.current.data?.[0].vendor_name).toBe('測試廠商');
  });

  it('透過 useVendorPerformanceHistory 以 vendor_id 與 months 載入走勢', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: { success: true, data: [makeRow({ period: '2026-06' })] },
    });

    const { result } = renderHook(() => useVendorPerformanceHistory(7, 3), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/vendor-performance/7/history', {
      params: { months: 3 },
    });
  });

  it('vendor_id 為 0 時不發出歷史請求', async () => {
    const { result } = renderHook(() => useVendorPerformanceHistory(0), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isPending).toBe(true));
    expect(api.get).not.toHaveBeenCalled();
  });

  it('透過 useRefreshVendorPerformance 以該期間呼叫 refresh 端點', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: { success: true, data: { period: '2026-08', updated: 3 } },
    });
    const { result } = renderHook(() => useRefreshVendorPerformance(), {
      wrapper: createWrapper(),
    });

    let updated: number | undefined;
    await act(async () => {
      updated = (await result.current.mutateAsync('2026-08')).updated;
    });

    expect(api.post).toHaveBeenCalledWith('/vendor-performance/refresh', {
      period: '2026-08',
    });
    expect(updated).toBe(3);
  });
});
