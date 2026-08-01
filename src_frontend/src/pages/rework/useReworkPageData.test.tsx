import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

import api from '../../services/api';
import { useReworkPageData } from './useReworkPageData';

vi.mock('../../services/api', () => ({
  default: { get: vi.fn() },
}));

const createWrapper = (queryClient: QueryClient) =>
  ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

describe('useReworkPageData', () => {
  it('以 useQuery 註冊列表與統計快取並回傳 isSuccess', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url.startsWith('/rework/applications?')) {
        return Promise.resolve({ data: [{ 重工單號: 'RW-1' }] });
      }
      if (url === '/rework/statistics') {
        return Promise.resolve({ data: { 申請件數: 1 } });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    const { result } = renderHook(
      () => useReworkPageData({ statusFilter: '待審核', startDate: '', endDate: '' }),
      { wrapper: createWrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith(`/rework/applications?status=${encodeURIComponent('待審核')}`);
    expect(api.get).toHaveBeenCalledWith('/rework/statistics');
    expect(queryClient.getQueryState([
      'rework',
      'applications',
      { statusFilter: '待審核', startDate: '', endDate: '' },
    ])).toBeTruthy();
  });

  it('篩選條件變更後以新條件重新載入列表', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url.startsWith('/rework/applications?')) {
        return Promise.resolve({ data: [] });
      }
      if (url === '/rework/statistics') {
        return Promise.resolve({ data: { 申請件數: 0 } });
      }
      return Promise.reject(new Error(`unexpected url: ${url}`));
    });

    const { result, rerender } = renderHook(
      ({ statusFilter }: { statusFilter: string }) =>
        useReworkPageData({ statusFilter, startDate: '', endDate: '' }),
      { wrapper: createWrapper(queryClient), initialProps: { statusFilter: '待審核' } },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    rerender({ statusFilter: '已完成' });
    await waitFor(() => expect(api.get).toHaveBeenCalledWith(`/rework/applications?status=${encodeURIComponent('已完成')}`));
  });
});
