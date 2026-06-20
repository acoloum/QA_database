import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { useAdminUsers } from './useAdmin';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
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

describe('useAdmin', () => {
  it('透過 useAdminUsers 載入使用者清單', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: [{ id: 1, username: 'admin', role: 'admin', is_active: true, created_at: null }],
    });

    const { result } = renderHook(() => useAdminUsers(), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/users');
    expect(result.current.data?.[0].username).toBe('admin');
  });
});
