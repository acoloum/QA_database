import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import type { MsaCriteriaProfileSummary } from '../types/msa';
import {
  useApproveMsaCriteriaVersion,
  useCreateMsaCriteriaProfile,
  useMsaCriteria,
} from './useMsaCriteria';

vi.mock('../services/api', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

const createWrapper = (queryClient: QueryClient) => ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

describe('MSA 判定準則資料層', () => {
  beforeEach(() => vi.clearAllMocks());

  it('以原始分頁參數載入準則設定', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { data: { items: [], page: 1, page_size: 25, total: 0 } } });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useMsaCriteria({ page: 1, page_size: 25, sort: 'name', order: 'asc' }),
      { wrapper: createWrapper(queryClient) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.get).toHaveBeenCalledWith('/msa/criteria', {
      params: { page: 1, page_size: 25, sort: 'name', order: 'asc' },
    });
  });

  it('建立 profile 與核准草稿版本時送出後端契約 payload，並只刷新準則快取', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({ data: { data: { id: 5, name: '一般量測' } } })
      .mockResolvedValueOnce({ data: { data: { id: 13, profile_id: 5, status: 'approved' } } });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const wrapper = createWrapper(queryClient);
    const create = renderHook(() => useCreateMsaCriteriaProfile(), { wrapper });
    const approve = renderHook(() => useApproveMsaCriteriaVersion(), { wrapper });
    const profile = { name: '一般量測', applicable_study_types: ['grr', 'bias'] };

    await act(async () => {
      await create.result.current.mutateAsync(profile);
      await approve.result.current.mutateAsync({ versionId: 13, expected_status: 'draft' });
    });

    expect(api.post).toHaveBeenNthCalledWith(1, '/msa/criteria', profile);
    expect(api.post).toHaveBeenNthCalledWith(2, '/msa/criteria/versions/13/approve', {
      expected_status: 'draft',
    });
    expect(invalidateSpy.mock.calls.map((call) => call[0])).toEqual([
      { queryKey: ['msa', 'criteria'] },
      { queryKey: ['msa', 'criteria'] },
    ]);
  });

  it('建立 profile 時採用 route 實際回傳的無 versions 摘要型別', () => {
    const summary: MsaCriteriaProfileSummary = {
      id: 5, name: '一般量測', customer_scope: null, product_scope: null,
      product_family_scope: null, characteristic_scope: null,
      characteristic_importance: null, applicable_study_types: ['grr'], current_version_id: null,
    };

    expect('versions' in summary).toBe(false);
  });
});
