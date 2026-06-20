import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import {
  useExportPyrometryTest,
  useFurnaces,
  usePyrometryDashboard,
  useSaveFurnace,
} from './usePyrometry';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
};

describe('usePyrometry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('載入啟用中的爐子清單', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { data: [{ 識別碼: 1, 爐號: 'F-01' }] } });
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => useFurnaces({ activeOnly: true }), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/pyrometry/furnaces?active_only=1');
    expect(result.current.data).toEqual([{ 識別碼: 1, 爐號: 'F-01' }]);
  });

  it('新增爐子後刷新爐子查詢', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { success: true } });
    const { queryClient, wrapper } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useSaveFurnace(), { wrapper });
    result.current.mutate({ payload: { 爐號: 'F-02' } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.post).toHaveBeenCalledWith('/pyrometry/furnaces', { 爐號: 'F-02' });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['furnaces'] });
  });

  it('匯出測試報告時下載 xlsx', async () => {
    const blob = new Blob(['xlsx']);
    vi.mocked(api.get).mockResolvedValue({ data: blob });
    const createObjectURL = vi.fn(() => 'blob:test');
    const revokeObjectURL = vi.fn();
    const click = vi.fn();
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(click);
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => useExportPyrometryTest(), { wrapper });
    result.current.mutate(7);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/pyrometry/tests/7/export', { responseType: 'blob' });
    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:test');
  });

  it('透過 hook 載入爐溫 Dashboard', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { data: [{ 爐子ID: 1, 爐號: 'F-01', 名稱: '一號爐' }] } });
    const { wrapper } = createWrapper();

    const { result } = renderHook(() => usePyrometryDashboard(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/pyrometry/dashboard');
    expect(result.current.data?.[0].爐號).toBe('F-01');
  });
});
