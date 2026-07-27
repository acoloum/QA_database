import { QueryClientProvider } from '@tanstack/react-query';
// @ts-expect-error 封裝套件未重新匯出 QueryClient 型別；測試仍使用其真實執行期建構子。
import { QueryClient } from '@tanstack/query-core';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import {
  msaKeys,
  useCreateMsaEquipment,
  useMsaEquipment,
  useMsaEquipmentDetail,
  useMsaStatusEvent,
} from './useMsaEquipment';

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));

const createWrapper = (queryClient: QueryClient) => ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe('MSA 設備資料層', () => {
  beforeEach(() => vi.clearAllMocks());

  it('以原始有界分頁與白名單排序參數取得設備，且不同參數使用不同快取鍵', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { data: { items: [], page: 1, page_size: 25, total: 0 } },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const params = { page: 1, page_size: 25, sort: 'equipment_no' as const };
    const { result } = renderHook(() => useMsaEquipment(params), { wrapper: createWrapper(queryClient) });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.get).toHaveBeenCalledWith('/measurement-equipment', { params });
    expect(msaKeys.equipment(params)).not.toEqual(
      msaKeys.equipment({ page: 2, page_size: 25, sort: 'equipment_no' }),
    );
  });

  it('未提供設備識別碼時不會查詢明細', () => {
    const queryClient = new QueryClient();
    const { result } = renderHook(() => useMsaEquipmentDetail(null), {
      wrapper: createWrapper(queryClient),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(api.get).not.toHaveBeenCalled();
  });

  it('建立與狀態轉移送出完整 payload，並只使設備清單及受影響明細失效', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: { data: { id: 9, equipment_no: 'EQ-009', name: '高度規' } } })
      .mockResolvedValueOnce({ data: { data: { id: 12, equipment_id: 9, target_status: 'maintenance' } } });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const wrapper = createWrapper(queryClient);
    const create = renderHook(() => useCreateMsaEquipment(), { wrapper });
    const transition = renderHook(() => useMsaStatusEvent(), { wrapper });
    const payload = { equipment_no: 'EQ-009', name: '高度規', status: 'pending_review' as const };

    await act(async () => {
      await create.result.current.mutateAsync(payload);
      await transition.result.current.mutateAsync({
        equipmentId: 9,
        event_type: 'maintenance',
        expected_status: 'active',
        target_status: 'maintenance',
        reason: '進行治具調整',
        triggers_msa_restudy: true,
      });
    });

    expect(api.post).toHaveBeenNthCalledWith(1, '/measurement-equipment', payload);
    expect(api.post).toHaveBeenNthCalledWith(2, '/measurement-equipment/9/status-events', {
      event_type: 'maintenance', expected_status: 'active', target_status: 'maintenance',
      reason: '進行治具調整', triggers_msa_restudy: true,
    });
    expect(invalidateSpy.mock.calls.map(([options]: [{ queryKey: readonly unknown[] }]) => options)).toEqual([
      { queryKey: ['msa', 'equipment'] },
      { queryKey: ['msa', 'equipment'] },
      { queryKey: ['msa', 'equipment', 'detail', 9] },
    ]);
  });

  it('保留後端拒絕，不會將失敗 mutation 誤判為成功', async () => {
    const backendError = Object.assign(new Error('設備編號已存在'), {
      code: 'MSA_EQUIPMENT_NO_DUPLICATE', details: { equipment_no: 'EQ-009' },
    });
    vi.mocked(api.post).mockRejectedValue(backendError);
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const { result } = renderHook(() => useCreateMsaEquipment(), { wrapper: createWrapper(queryClient) });

    await act(async () => {
      await expect(result.current.mutateAsync({ equipment_no: 'EQ-009', name: '高度規' })).rejects.toBe(backendError);
    });
    expect(result.current.isError).toBe(true);
  });
});
