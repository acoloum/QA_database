import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { useToleranceDetail } from './useTolerance';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('useToleranceDetail', () => {
  it('enabled 為 false 時不查詢公差明細', () => {
    renderHook(() => useToleranceDetail(7, false), { wrapper: createWrapper() });

    expect(api.get).not.toHaveBeenCalled();
  });

  it('載入公差明細', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: { main: { 材質: '6061' }, details: [] } });

    const { result } = renderHook(() => useToleranceDetail(7), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/tolerance/7');
    expect(result.current.data?.main.材質).toBe('6061');
  });
});
