import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

import api from '../services/api';
import { compactParams } from '../utils/queryParams';
import { downloadBlob } from '../utils/downloadFile';
import type { Furnace, PyrometryDashboardRow, PyrometryTestRow, Recorder, Thermocouple } from '../types';
import type { PyrometryPayload } from '../pages/pyrometry/pyrometryPayload';

export interface PyrometryTestFilters {
  furnace_id?: string;
  test_type?: string;
  quarter?: string;
  is_pass?: string;
  date_from?: string;
  date_to?: string;
}

export interface PyrometryTestListParams {
  page: number;
  pageSize?: number;
  filters: PyrometryTestFilters;
}

export const pyrometryKeys = {
  furnaces: ['furnaces'] as const,
  furnacesActive: ['furnaces-active'] as const,
  furnaceTrend: (id: number | null) => ['tus-trend', id] as const,
  recorders: ['recorders'] as const,
  thermocouples: ['thermocouples'] as const,
  dashboard: ['pyrometry-dashboard'] as const,
  tests: ['pyrometry-tests'] as const,
  testList: (params: PyrometryTestListParams) => ['pyrometry-tests', params.page, params.filters] as const,
  testDetail: (id: number | null) => ['pyrometry-test-detail', id] as const,
};

export const getPyrometryErrorMessage = (error: unknown, fallback: string) => {
  const apiError = error as { response?: { data?: { error?: string; message?: string } } };
  return apiError.response?.data?.error || apiError.response?.data?.message || fallback;
};

export const useFurnaces = (options: { activeOnly?: boolean } = {}) =>
  useQuery({
    queryKey: options.activeOnly ? pyrometryKeys.furnacesActive : pyrometryKeys.furnaces,
    queryFn: () => api
      .get<{ data: Furnace[] }>(`/pyrometry/furnaces${options.activeOnly ? '?active_only=1' : ''}`)
      .then(r => r.data.data),
  });

export const useFurnaceTusTrend = (furnaceId: number | null) =>
  useQuery({
    queryKey: pyrometryKeys.furnaceTrend(furnaceId),
    queryFn: () => furnaceId
      ? api.get<{ data: { 測試日期: string; 均勻度極差: string | number; 最大正偏差: string | number; 最大負偏差: string | number; 是否合格: boolean }[] }>(
          `/pyrometry/furnaces/${furnaceId}/tus-trend`,
        ).then(r => r.data.data)
      : Promise.resolve(null),
    enabled: !!furnaceId,
  });

export const useSaveFurnace = (editId?: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id = editId ?? null, payload }: { id?: number | null; payload: Partial<Furnace> }) =>
      id ? api.put(`/pyrometry/furnaces/${id}`, payload) : api.post('/pyrometry/furnaces', payload),
    onSuccess: (_data, variables) => {
      toast.success(variables.id || editId ? '爐子設備已更新' : '爐子設備已新增');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.furnaces });
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.furnacesActive });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '爐子設備儲存失敗')),
  });
};

export const useDeleteFurnace = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/pyrometry/furnaces/${id}`),
    onSuccess: () => {
      toast.success('爐子設備已刪除');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.furnaces });
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.furnacesActive });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '爐子設備刪除失敗')),
  });
};

export const useRecorders = () =>
  useQuery({
    queryKey: pyrometryKeys.recorders,
    queryFn: () => api.get<{ data: Recorder[] }>('/pyrometry/recorders').then(r => r.data.data),
  });

export const useRecorderDetail = () =>
  useMutation({
    mutationFn: (id: number) => api.get<{ data: Recorder }>(`/pyrometry/recorders/${id}`).then(r => r.data.data),
  });

export const useSaveRecorder = (editId?: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id = editId ?? null, payload }: { id?: number | null; payload: Partial<Recorder> }) =>
      id ? api.put(`/pyrometry/recorders/${id}`, payload) : api.post('/pyrometry/recorders', payload),
    onSuccess: (_data, variables) => {
      toast.success(variables.id || editId ? '記錄器校正已更新' : '記錄器校正已新增');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.recorders });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '記錄器校正儲存失敗')),
  });
};

export const useDeleteRecorder = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/pyrometry/recorders/${id}`),
    onSuccess: () => {
      toast.success('記錄器校正已刪除');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.recorders });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '記錄器校正刪除失敗')),
  });
};

export const useThermocouples = () =>
  useQuery({
    queryKey: pyrometryKeys.thermocouples,
    queryFn: () => api.get<{ data: Thermocouple[] }>('/pyrometry/thermocouples').then(r => r.data.data),
  });

export const useThermocoupleDetail = () =>
  useMutation({
    mutationFn: (id: number) => api.get<{ data: Thermocouple }>(`/pyrometry/thermocouples/${id}`).then(r => r.data.data),
  });

export const useSaveThermocouple = (editId?: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id = editId ?? null, payload }: { id?: number | null; payload: Partial<Thermocouple> }) =>
      id ? api.put(`/pyrometry/thermocouples/${id}`, payload) : api.post('/pyrometry/thermocouples', payload),
    onSuccess: (_data, variables) => {
      toast.success(variables.id || editId ? '熱電偶校正已更新' : '熱電偶校正已新增');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.thermocouples });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '熱電偶校正儲存失敗')),
  });
};

export const useDeleteThermocouple = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/pyrometry/thermocouples/${id}`),
    onSuccess: () => {
      toast.success('熱電偶校正已刪除');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.thermocouples });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '熱電偶校正刪除失敗')),
  });
};

export const usePyrometryDashboard = () =>
  useQuery({
    queryKey: pyrometryKeys.dashboard,
    queryFn: () => api.get<{ data: PyrometryDashboardRow[] }>('/pyrometry/dashboard').then(r => r.data.data),
  });

export const usePyrometryTests = (params: PyrometryTestListParams) =>
  useQuery({
    queryKey: pyrometryKeys.testList(params),
    queryFn: () => {
      return api.get<{ data: PyrometryTestRow[]; total: number; total_pages: number }>(
        '/pyrometry/tests',
        {
          params: {
            page: params.page,
            page_size: params.pageSize ?? 20,
            ...compactParams(params.filters),
          },
        },
      ).then(r => r.data);
    },
  });

export const usePyrometryTestDetail = (editId: number | null) =>
  useQuery({
    queryKey: pyrometryKeys.testDetail(editId),
    queryFn: () => api.get(`/pyrometry/tests/${editId}`).then(r => r.data),
    enabled: !!editId,
  });

export const useLoadPyrometryTestDetail = () =>
  useMutation({
    mutationFn: (id: number) => api.get(`/pyrometry/tests/${id}`).then(r => r.data),
    onError: error => toast.error(getPyrometryErrorMessage(error, '爐溫測試資料載入失敗')),
  });

export const useSavePyrometryTest = (editId?: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id = editId ?? null, payload }: { id?: number | null; payload: PyrometryPayload }) =>
      id ? api.put(`/pyrometry/tests/${id}`, payload) : api.post('/pyrometry/tests', payload),
    onSuccess: (_data, variables) => {
      toast.success(variables.id || editId ? '爐溫測試已更新' : '爐溫測試已新增');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.tests });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '爐溫測試儲存失敗')),
  });
};

export const useDeletePyrometryTest = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/pyrometry/tests/${id}`),
    onSuccess: () => {
      toast.success('爐溫測試已刪除');
      queryClient.invalidateQueries({ queryKey: pyrometryKeys.tests });
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '爐溫測試刪除失敗')),
  });
};

export const useExportPyrometryTest = () =>
  useMutation({
    mutationFn: async (id: number) => {
      const res = await api.get(`/pyrometry/tests/${id}/export`, { responseType: 'blob' });
      downloadBlob(res.data as Blob, `pyrometry_${id}.xlsx`);
    },
    onSuccess: () => toast.success('爐溫測試報告已匯出'),
    onError: error => toast.error(getPyrometryErrorMessage(error, '爐溫測試報告匯出失敗')),
  });

export const usePyrometryCorrections = () =>
  useMutation({
    mutationFn: ({ setpoint, type, count, channels }: { setpoint: number; type: 'TUS' | 'SAT'; count: number; channels?: string }) => {
      return api.get<{ success: boolean; data: number[] }>('/pyrometry/corrections', {
        params: { setpoint, type, count, ...compactParams({ channels }) },
      }).then(r => r.data);
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '補正值載入失敗')),
  });

export const useParsePyrometryData = () =>
  useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return api.post<{
        success: boolean;
        data: { 時間: string[]; 通道: { 名稱: string }[]; 數值: Record<string, number[]> };
      }>('/pyrometry/parse-data', formData, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data);
    },
    onError: error => toast.error(getPyrometryErrorMessage(error, '曲線資料解析失敗')),
  });

export const useTusTestOnDate = () =>
  useMutation({
    mutationFn: ({ furnaceId, testDate }: { furnaceId: string; testDate: string }) =>
      api.get<{ success: boolean; data: { 識別碼: number }[] }>(
        `/pyrometry/tests?furnace_id=${furnaceId}&test_type=TUS&date_from=${testDate}&date_to=${testDate}&page_size=1`,
      ).then(r => r.data),
  });
