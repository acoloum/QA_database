import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { downloadBlob } from '../utils/downloadFile';
import {
  calibrationKeys,
  isCalibrationRecordListQuery,
  useDownloadCalibrationCertificate,
  useSaveCalibrationReadings,
} from './useCalibrations';

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));
vi.mock('../utils/downloadFile', () => ({ downloadBlob: vi.fn() }));

const createWrapper = (queryClient: QueryClient) => (
  { children }: { children: ReactNode },
) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;

describe('校正紀錄資料層', () => {
  beforeEach(() => vi.clearAllMocks());

  it('批次儲存讀值保留 expected_version 並只失效受影響校正快取', async () => {
    vi.mocked(api.put).mockResolvedValue({
      data: { data: { id: 41, row_version: 3, result: 'pass' } },
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useSaveCalibrationReadings(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        calibrationId: 41,
        expected_version: 2,
        points: [],
      });
    });

    expect(api.put).toHaveBeenCalledWith('/calibrations/41/readings', {
      expected_version: 2,
      points: [],
    });
    expect(invalidate.mock.calls.map((call) => call[0])).toEqual([
      { queryKey: calibrationKeys.record(41) },
      { predicate: isCalibrationRecordListQuery },
    ]);
  });

  it('讀值 mutation 不會失效其他校正明細', async () => {
    vi.mocked(api.put).mockResolvedValue({
      data: { data: { id: 41, row_version: 3, result: 'pass' } },
    });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    queryClient.setQueryData(calibrationKeys.record(41), { id: 41 });
    queryClient.setQueryData(calibrationKeys.record(42), { id: 42 });
    const { result } = renderHook(() => useSaveCalibrationReadings(), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.mutateAsync({
        calibrationId: 41,
        expected_version: 2,
        points: [],
      });
    });

    expect(queryClient.getQueryState(calibrationKeys.record(41))?.isInvalidated)
      .toBe(true);
    expect(queryClient.getQueryState(calibrationKeys.record(42))?.isInvalidated)
      .toBe(false);
  });

  it('證書透過共用認證 API 下載 blob', async () => {
    const certificate = new Blob(['certificate'], { type: 'application/pdf' });
    vi.mocked(api.get).mockResolvedValue({ data: certificate });
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const { result } = renderHook(
      () => useDownloadCalibrationCertificate(),
      { wrapper: createWrapper(queryClient) },
    );

    await act(async () => {
      await result.current.mutateAsync({
        attachmentId: 88,
        filename: 'CAL-88.pdf',
      });
    });

    expect(api.get).toHaveBeenCalledWith(
      '/attachments/88/download',
      { responseType: 'blob' },
    );
    expect(downloadBlob).toHaveBeenCalledWith(certificate, 'CAL-88.pdf');
  });
});
