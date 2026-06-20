import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { downloadResponseBlob } from '../utils/downloadFile';
import { useExportPatrolRawData } from './usePatrol';
import { useExportShippingData } from './useShipping';
import { useExportToleranceData } from './useTolerance';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('../utils/downloadFile', () => ({
  downloadResponseBlob: vi.fn(),
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('匯出 hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.get).mockResolvedValue({ data: new Blob(['xlsx']) });
  });

  it('匯出巡檢原始資料', async () => {
    const { result } = renderHook(() => useExportPatrolRawData(), { wrapper: createWrapper() });

    result.current.mutate({ page: 1, s_date: '2026-06-01', m_id: 'M1' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/patrol/export?s_date=2026-06-01&m_id=M1', { responseType: 'blob' });
    expect(downloadResponseBlob).toHaveBeenCalledWith(expect.any(Blob), '巡檢數據.xlsx');
  });

  it('匯出公差資料', async () => {
    const { result } = renderHook(() => useExportToleranceData(), { wrapper: createWrapper() });

    result.current.mutate({ page: 1, page_size: 20, material: '6061', vendor_id: '3' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/tolerance/export?material=6061&vendor_id=3', { responseType: 'blob' });
    expect(downloadResponseBlob).toHaveBeenCalledWith(expect.any(Blob), '廠商公差資料.xlsx');
  });

  it('匯出出貨檢驗資料', async () => {
    const { result } = renderHook(() => useExportShippingData(), { wrapper: createWrapper() });

    result.current.mutate({ page: 1, vendor: 'A廠', material: '6061' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/export/excel', {
      params: { vendor: 'A廠', material: '6061', spec: undefined, start_date: undefined, end_date: undefined },
      responseType: 'blob',
    });
    expect(downloadResponseBlob).toHaveBeenCalledWith(expect.any(Blob), '出貨檢驗數據.xlsx');
  });
});
