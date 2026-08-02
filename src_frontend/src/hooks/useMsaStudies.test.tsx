import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import {
  useAnalyzeMsaPlan,
  useApproveMsaResult,
  useCreateMsaStudy,
  useDownloadMsaReport,
  useMsaPlanTasks,
  useMsaStudies,
  useRecordMsaObservation,
  useSubmitMsaResult,
  useUpdateMsaStudy,
} from './useMsaStudies';

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  unwrap: (response: { data: { data: unknown } }) => response.data.data,
}));

const downloadSpy = vi.hoisted(() => vi.fn());
vi.mock('../utils/downloadFile', () => ({
  downloadResponseBlob: (...args: unknown[]) => downloadSpy(...args),
}));

const createWrapper = (queryClient: QueryClient) =>
  ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

const newClient = () => new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});

beforeEach(() => vi.clearAllMocks());

describe('MSA 研究資料層', () => {
  it('以有界分頁與白名單排序取得研究', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: { data: { items: [], page: 1, page_size: 25, total: 0 } },
    });
    const { result } = renderHook(
      () => useMsaStudies({ page: 1, page_size: 25, sort: 'study_no' }),
      { wrapper: createWrapper(newClient()) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/msa/studies', {
      params: { page: 1, page_size: 25, sort: 'study_no' },
    });
  });

  it('建立研究時送出識別資料', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: { data: { id: 1, study_no: 'MSA-2026-0001' } },
    });
    const { result } = renderHook(
      () => useCreateMsaStudy(), { wrapper: createWrapper(newClient()) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        study_type: 'grr_anova',
        measurement_purpose: 'product_control',
        characteristic: '外徑',
        unit: 'mm',
        lsl: 9.5,
        usl: 10.5,
      });
    });

    expect(api.post).toHaveBeenCalledWith('/msa/studies', {
      study_type: 'grr_anova',
      measurement_purpose: 'product_control',
      characteristic: '外徑',
      unit: 'mm',
      lsl: 9.5,
      usl: 10.5,
    });
  });

  it('更新研究時把 expected_updated_at 放進 payload 而非路徑', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({ data: { data: { id: 7 } } });
    const { result } = renderHook(
      () => useUpdateMsaStudy(), { wrapper: createWrapper(newClient()) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        studyId: 7,
        characteristic: '厚度',
        expected_updated_at: '2026-07-27T00:00:00+00:00',
      });
    });

    expect(api.patch).toHaveBeenCalledWith('/msa/studies/7', {
      characteristic: '厚度',
      expected_updated_at: '2026-07-27T00:00:00+00:00',
    });
  });

  it('盲測任務只在指定 plan 時才查詢', async () => {
    const { result, rerender } = renderHook(
      ({ planId }: { planId: number | null }) => useMsaPlanTasks(planId),
      {
        wrapper: createWrapper(newClient()),
        initialProps: { planId: null as number | null },
      },
    );

    expect(api.get).not.toHaveBeenCalled();

    vi.mocked(api.get).mockResolvedValueOnce({ data: { data: { items: [] } } });
    rerender({ planId: 12 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/msa/plans/12/tasks');
  });

  it('記錄觀測後只刷新該 plan 的任務快取', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { data: { id: 3 } } });
    const queryClient = newClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(
      () => useRecordMsaObservation(),
      { wrapper: createWrapper(queryClient) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        planId: 5, task_order: 1, numeric_value: '10.001',
      });
    });

    expect(api.post).toHaveBeenCalledWith('/msa/plans/5/observations', {
      task_order: 1, numeric_value: '10.001',
    });
    expect(invalidateSpy.mock.calls.map((call) => call[0])).toEqual([
      { queryKey: ['msa', 'plan-tasks', 5] },
    ]);
  });

  it('分析時送出畫面看到的計畫指紋', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { data: { id: 9 } } });
    const { result } = renderHook(
      () => useAnalyzeMsaPlan(), { wrapper: createWrapper(newClient()) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        planId: 5, expected_plan_hash: 'a'.repeat(64),
      });
    });

    expect(api.post).toHaveBeenCalledWith('/msa/plans/5/analyze', {
      expected_plan_hash: 'a'.repeat(64),
    });
  });

  it.each([
    ['送審', useSubmitMsaResult, 'submit'],
    ['核准', useApproveMsaResult, 'approve'],
  ] as const)('%s 時送出 expected_status 與理由', async (_label, hook, path) => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { data: { id: 4 } } });
    const { result } = renderHook(
      () => hook(), { wrapper: createWrapper(newClient()) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        resultId: 4, expected_status: 'submitted', reason: '證據充分',
      });
    });

    expect(api.post).toHaveBeenCalledWith(`/msa/results/4/${path}`, {
      expected_status: 'submitted', reason: '證據充分',
    });
  });

  it('條件接受送審時一併帶出處置措施與期限', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ data: { data: { id: 4 } } });
    const { result } = renderHook(
      () => useSubmitMsaResult(), { wrapper: createWrapper(newClient()) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        resultId: 4,
        expected_status: 'analyzed',
        reason: '條件接受',
        actions: ['加嚴抽樣'],
        due_date: '2026-10-31',
      });
    });

    expect(api.post).toHaveBeenCalledWith('/msa/results/4/submit', {
      expected_status: 'analyzed',
      reason: '條件接受',
      actions: ['加嚴抽樣'],
      due_date: '2026-10-31',
    });
  });
});

describe('MSA 報告下載', () => {
  it.each(['xlsx', 'pdf'] as const)(
    '以共用 axios 實例取得 %s 並以 blob 下載',
    async (format) => {
      const blob = new Blob(['x']);
      vi.mocked(api.get).mockResolvedValueOnce({ data: blob });
      const { result } = renderHook(
        () => useDownloadMsaReport(), { wrapper: createWrapper(newClient()) },
      );

      await act(async () => {
        await result.current.mutateAsync({
          resultId: 12, format, studyNo: 'MSA-2026-0001',
        });
      });

      expect(api.get).toHaveBeenCalledWith(
        `/msa/results/12/report.${format}`, { responseType: 'blob' },
      );
      expect(downloadSpy).toHaveBeenCalledWith(
        blob, `MSA_MSA-2026-0001_v12.${format}`, expect.any(String),
      );
    },
  );

  it('沒有研究編號時退回以結果版本命名', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: new Blob(['x']) });
    const { result } = renderHook(
      () => useDownloadMsaReport(), { wrapper: createWrapper(newClient()) },
    );

    await act(async () => {
      await result.current.mutateAsync({ resultId: 8, format: 'pdf' });
    });

    expect(downloadSpy).toHaveBeenCalledWith(
      expect.any(Blob), 'MSA_8.pdf', 'application/pdf',
    );
  });
});
