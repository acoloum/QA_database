import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import {
  calibrationKeys,
  isCalibrationTemplateListQuery,
  useCalibrationTemplates,
  useUpdateCalibrationTemplateVersion,
} from './useCalibrationTemplates';

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), patch: vi.fn() },
}));

const createWrapper = (queryClient: QueryClient) => (
  { children }: { children: ReactNode },
) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;

describe('校正模板資料層', () => {
  beforeEach(() => vi.clearAllMocks());

  it('模板清單與明細使用互不污染的精確快取鍵', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { data: { items: [], page: 1, page_size: 25, total: 0 } },
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const params = { page: 1, page_size: 25, status: 'active' as const };
    const { result } = renderHook(() => useCalibrationTemplates(params), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(api.get).toHaveBeenCalledWith('/calibration-templates', { params });
    expect(calibrationKeys.templateLists()).not.toEqual(
      calibrationKeys.template(12),
    );
    expect(calibrationKeys.templateList(params)).not.toEqual(
      calibrationKeys.templateList({ ...params, page: 2 }),
    );
  });

  it('更新版本只失效模板清單與受影響明細，不波及其他明細', async () => {
    vi.mocked(api.patch).mockResolvedValue({
      data: { data: { id: 31, template_id: 8, row_version: 3 } },
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(
      () => useUpdateCalibrationTemplateVersion(),
      { wrapper: createWrapper(queryClient) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        templateId: 8,
        versionId: 31,
        expected_version: 2,
        revision_reason: '補充分辨率規則',
        points: [],
      });
    });

    expect(api.patch).toHaveBeenCalledWith(
      '/calibration-template-versions/31',
      {
        expected_version: 2,
        revision_reason: '補充分辨率規則',
        points: [],
      },
    );
    expect(invalidate.mock.calls.map((call) => call[0])).toEqual([
      { predicate: isCalibrationTemplateListQuery },
      { queryKey: calibrationKeys.template(8) },
    ]);
  });

  it('保留後端結構化錯誤物件供表單顯示欄位與版本衝突', async () => {
    const backendError = Object.assign(new Error('資料版本已更新'), {
      status: 409,
      code: 'CALIBRATION_VERSION_CONFLICT',
      details: { current_version: 4 },
      field: 'expected_version',
    });
    vi.mocked(api.patch).mockRejectedValue(backendError);
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const { result } = renderHook(
      () => useUpdateCalibrationTemplateVersion(),
      { wrapper: createWrapper(queryClient) },
    );

    await act(async () => {
      await expect(result.current.mutateAsync({
        templateId: 8,
        versionId: 31,
        expected_version: 2,
        points: [],
      })).rejects.toBe(backendError);
    });
  });
});
