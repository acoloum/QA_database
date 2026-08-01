import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

import api from '../services/api';
import type { VendorPerformance } from '../types';

export const useVendorPerformanceList = (period: string) =>
  useQuery({
    queryKey: ['vendorPerformance', period],
    queryFn: async () => {
      const res = await api.get<{ success: boolean; data: VendorPerformance[] }>(
        '/vendor-performance', { params: { period } }
      );
      return res.data.data;
    },
  });

export const useVendorPerformanceHistory = (vendorId: number, months = 6) =>
  useQuery({
    queryKey: ['vendorPerformanceHistory', vendorId, months],
    queryFn: async () => {
      const res = await api.get<{ success: boolean; data: VendorPerformance[] }>(
        `/vendor-performance/${vendorId}/history`, { params: { months } }
      );
      return res.data.data;
    },
    enabled: vendorId > 0,
  });

const getRefreshErrorMessage = (err: unknown): string => {
  if (err && typeof err === 'object' && 'response' in err) {
    const axiosErr = err as { response?: { data?: { error?: string; message?: string } } };
    return axiosErr.response?.data?.error ?? axiosErr.response?.data?.message ?? '重新計算失敗，請稍後再試';
  }
  return '重新計算失敗，請稍後再試';
};

export const useRefreshVendorPerformance = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (period: string) => {
      const res = await api.post<{ success: boolean; data: { period: string; updated: number } }>(
        '/vendor-performance/refresh', { period }
      );
      return res.data.data;
    },
    onSuccess: (_data, period) => {
      toast.success('績效快照已重新計算');
      // 精確失效：只清掉該期間的評比清單，並刷新走勢（歷史可能涵蓋該期間）
      queryClient.invalidateQueries({ queryKey: ['vendorPerformance', period] });
      queryClient.invalidateQueries({ queryKey: ['vendorPerformanceHistory'] });
    },
    onError: err => toast.error(getRefreshErrorMessage(err)),
  });
};
