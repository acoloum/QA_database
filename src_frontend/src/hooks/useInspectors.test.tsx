import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { useInspectors } from './useInspectors';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
);

describe('useInspectors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('透過共用 query 載入檢驗員清單', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [{ id: 1, name: '王小明' }] });

    const { result } = renderHook(() => useInspectors(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.get).toHaveBeenCalledWith('/inspectors', { params: undefined });
    expect(result.current.data).toEqual([{ id: 1, name: '王小明' }]);
  });

  it('disabled 時不送出請求', () => {
    renderHook(() => useInspectors({ enabled: false }), { wrapper });

    expect(api.get).not.toHaveBeenCalled();
  });
});
