import { QueryClientProvider } from '@tanstack/react-query';
// @ts-expect-error 封裝套件未重新匯出 QueryClient 型別；測試仍使用其真實執行期建構子。
import { QueryClient } from '@tanstack/query-core';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { isMsaEquipmentListQuery } from './useMsaEquipment';
import { useConfirmMsaEquipmentImport, usePreviewMsaEquipmentImport } from './useMsaImports';

vi.mock('../services/api', () => ({ default: { post: vi.fn() } }));

const createWrapper = (queryClient: QueryClient) => ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe('MSA 設備匯入資料層', () => {
  beforeEach(() => vi.clearAllMocks());

  it('預覽使用含原始檔案的 FormData，並以查詢參數傳遞盤點日', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { data: { id: 41, status: 'previewed' } } });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const { result } = renderHook(() => usePreviewMsaEquipmentImport(), { wrapper: createWrapper(queryClient) });
    const file = new File(['設備編號,名稱\nEQ-001,卡尺'], 'measurements.csv', { type: 'text/csv' });

    await act(async () => {
      await result.current.mutateAsync({ file, as_of: '2026-07-27' });
    });

    const [path, body, config] = vi.mocked(api.post).mock.calls[0] ?? [];
    expect(path).toBe('/measurement-equipment/imports/preview');
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get('file')).toBe(file);
    expect(config).toEqual({ params: { as_of: '2026-07-27' } });
  });

  it('確認時原樣傳送逐列 resolution，並只使批次與設備清單失效', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { data: { id: 41, status: 'confirmed' } } });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useConfirmMsaEquipmentImport(), { wrapper: createWrapper(queryClient) });
    const resolutions = {
      71: { action: 'reject' as const },
      72: {
        action: 'pending_review' as const, calibration_type: 'exempt' as const,
        calibration_exemption_reason: '不影響產品判定', serial_no: 'SN-72',
      },
    };

    await act(async () => {
      await result.current.mutateAsync({ batchId: 41, resolutions, confirmation_date: '2026-07-27' });
    });

    expect(api.post).toHaveBeenCalledWith('/measurement-equipment/imports/41/confirm', {
      resolutions, confirmation_date: '2026-07-27',
    });
    expect(invalidateSpy.mock.calls.map(([options]: [{ predicate?: unknown; queryKey?: readonly unknown[] }]) => options)).toEqual([
      { queryKey: ['msa', 'equipment-import', 41] },
      { predicate: isMsaEquipmentListQuery },
    ]);
  });
});
