import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import api from '../services/api';
import {
  fetchSpcEvent, useAnalyzeSpcStudy, useApproveSpcResearch, useSaveSpcOcap, useSpcAssignees,
  useConfirmSpcTimeModel, useConfirmSpcTransformation, useSpcStudyHistory, useSubmitSpcStudy,
} from './useSpcStudies';

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
  unwrap: (response: { data: { data: unknown } }) => response.data.data,
}));

const createWrapper = (queryClient: QueryClient) =>
  ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

describe('SPC 研究 hooks', () => {
  beforeEach(() => vi.clearAllMocks());

  it('分析時傳送來源與目前篩選條件，並拆出標準回應 data', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { success: true, data: { id: 21, study_id: 7 } },
    });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const { result } = renderHook(() => useAnalyzeSpcStudy(), {
      wrapper: createWrapper(queryClient),
    });

    let returned: unknown;
    await act(async () => {
      returned = await result.current.mutateAsync({
        source: 'shipping',
        filters: { vendor: 'A廠', field: 'od' },
      });
    });

    expect(api.post).toHaveBeenCalledWith('/spc/studies/analyze', {
      source: 'shipping',
      filters: { vendor: 'A廠', field: 'od' },
    });
    expect(returned).toMatchObject({ id: 21, study_id: 7 });
  });

  it('機器研究只傳送巡檢固定流 filters 與受控條件 options', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { success: true, data: { id: 22, study_id: 8 } } });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const { result } = renderHook(() => useAnalyzeSpcStudy(), { wrapper: createWrapper(queryClient) });

    await act(async () => {
      await result.current.mutateAsync({
        source: 'patrol', analysis_family: 'machine',
        filters: { m_id: 7, mat: '6061', spec: '10x1', item: '外徑', pos: 'A' },
        options: { conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態' },
      });
    });

    expect(api.post).toHaveBeenCalledWith('/spc/studies/analyze', {
      source: 'patrol', analysis_family: 'machine',
      filters: { m_id: 7, mat: '6061', spec: '10x1', item: '外徑', pos: 'A' },
      options: { conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態' },
    });
  });

  it('核准機器研究使用 research 端點且維持研究快取失效範圍', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { success: true, data: { id: 22, study_id: 8, status: 'approved' } },
    });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useApproveSpcResearch(), { wrapper: createWrapper(queryClient) });

    await act(async () => {
      await result.current.mutateAsync({ versionId: 22, studyId: 8, reason: '已核對研究條件與績效證據' });
    });

    expect(api.post).toHaveBeenCalledWith('/spc/study-versions/22/approve-research', {
      reason: '已核對研究條件與績效證據',
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(3);
  });

  it('屬性研究保留 family 與受控 options，不影響既有呼叫格式', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { success: true, data: { id: 22, study_id: 8 } },
    });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const { result } = renderHook(() => useAnalyzeSpcStudy(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        source: 'shipping', filters: { vendor: 'A廠' }, analysis_family: 'attribute',
        options: { interval: 'day', chart_type: 'p' },
      });
    });

    expect(api.post).toHaveBeenCalledWith('/spc/studies/analyze', {
      source: 'shipping', filters: { vendor: 'A廠' }, analysis_family: 'attribute',
      options: { interval: 'day', chart_type: 'p' },
    });
  });

  it('送審成功後只使研究清單、單筆與歷程快取失效', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { success: true, data: { id: 21, study_id: 7, status: 'submitted' } },
    });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useSubmitSpcStudy(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({ versionId: 21, studyId: 7, reason: '資料已複核' });
    });
    await waitFor(() => expect(invalidateSpy).toHaveBeenCalledTimes(3));

    expect(api.post).toHaveBeenCalledWith('/spc/study-versions/21/submit', {
      reason: '資料已複核',
    });
    expect(invalidateSpy.mock.calls.map(([options]) => options)).toEqual([
      { queryKey: ['spcStudies'] },
      { queryKey: ['spcStudy', 7] },
      { queryKey: ['spcStudyHistory', 7] },
    ]);
  });

  it('完整時間模型與轉換確認使用後繼版本端點並使研究快取失效', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { success: true, data: { id: 23, study_id: 7 } } });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const time = renderHook(() => useConfirmSpcTimeModel(), { wrapper: createWrapper(queryClient) });
    const transformation = renderHook(() => useConfirmSpcTransformation(), { wrapper: createWrapper(queryClient) });

    await act(async () => {
      await time.result.current.mutateAsync({ versionId: 21, studyId: 7, model: 'D', reason: '已複核位置與變異變化' });
      await transformation.result.current.mutateAsync({ versionId: 23, studyId: 7, model: 'johnson_sb', reason: '已複核支撐域與往返證據' });
    });

    expect(api.post).toHaveBeenNthCalledWith(1, '/spc/study-versions/21/time-model', { model: 'D', reason: '已複核位置與變異變化' });
    expect(api.post).toHaveBeenNthCalledWith(2, '/spc/study-versions/23/transformation', { model: 'johnson_sb', reason: '已複核支撐域與往返證據' });
    expect(invalidateSpy).toHaveBeenCalledTimes(6);
  });

  it('只在啟用時查詢 SPC 可指派責任人', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { success: true, data: [{
        id: 8, username: 'qa-user', role: 'qa_supervisor', role_name: 'QA主管',
      }] },
    });
    const queryClient = new QueryClient();
    const { result } = renderHook(() => useSpcAssignees(true), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/spc/assignees');
    expect(result.current.data?.[0].role_name).toBe('QA主管');
  });

  it('停用責任人查詢時不會呼叫 API', () => {
    const queryClient = new QueryClient();
    const { result } = renderHook(() => useSpcAssignees(false), {
      wrapper: createWrapper(queryClient),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(api.get).not.toHaveBeenCalled();
  });

  it('研究歷程以頁碼與每頁筆數精準查詢', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        success: true,
        data: { items: [], total: 0, page: 2, per_page: 20, pages: 0 },
      },
    });
    const queryClient = new QueryClient();
    const { result } = renderHook(() => useSpcStudyHistory(9, 2), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/spc/studies/9/history', {
      params: { page: 2, per_page: 20 },
    });
    expect(result.current.data?.page).toBe(2);
  });

  it('OCAP 儲存後可用輕量事件 API 校正狀態', async () => {
    const event = { id: 81, status: 'closed', ocap: { id: 3 } };
    vi.mocked(api.get).mockResolvedValue({
      data: { success: true, data: event },
    });

    const returned = await fetchSpcEvent(81);

    expect(api.get).toHaveBeenCalledWith('/spc/events/81');
    expect(returned).toEqual(event);
  });

  it('儲存 OCAP 後回傳完整資料但不觸發整份研究重抓', async () => {
    const ocap = {
      id: 3, event_id: 81, investigation_6m: { summary: '模具磨耗' },
      remeasurement: null, process_adjustment: '更換模具',
      product_disposition: null, owner_id: 8, effectiveness: null,
      status: 'open', created_by: 1, updated_by: 1,
      created_at: '2026-07-19T01:00:00Z', updated_at: '2026-07-19T01:00:00Z',
    };
    vi.mocked(api.patch).mockResolvedValue({ data: { success: true, data: ocap } });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useSaveSpcOcap(), {
      wrapper: createWrapper(queryClient),
    });

    let returned: unknown;
    await act(async () => {
      returned = await result.current.mutateAsync({
        eventId: 81, ocapId: 3, payload: { process_adjustment: '更換模具' },
      });
    });

    expect(returned).toEqual(ocap);
    expect(invalidateSpy).not.toHaveBeenCalled();
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ['spcEvents'] });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ['spcOcap', 81] });
  });
});
