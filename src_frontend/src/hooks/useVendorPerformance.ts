import { useQuery } from '@tanstack/react-query';
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
