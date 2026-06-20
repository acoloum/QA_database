import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

import api from '../../services/api';
import { useCreateReworkExecution } from './useReworkMutations';

vi.mock('../../services/api', () => ({
  default: {
    post: vi.fn(),
    put: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('useReworkMutations', () => {
  it('新增執行紀錄後呼叫成功 callback', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: {} });
    const onSuccess = vi.fn();
    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
      },
    });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useCreateReworkExecution({ onSuccess }), { wrapper });
    result.current.mutate({ 重工單號: 'RW-001', 負責人員姓名: '王小明' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.post).toHaveBeenCalledWith('/rework/execute', { 重工單號: 'RW-001', 負責人員姓名: '王小明' });
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });
});
