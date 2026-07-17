
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import { downloadResponseBlob } from '../utils/downloadFile';
import type { ShippingInspection, Inspector, Vendor, ToleranceResult, ShippingCreateInput, ShippingUpdateInput } from '../types';

export interface ShippingSearchParams {
    page: number;
    start_date?: string;
    end_date?: string;
    vendor?: string;
    material?: string;
    spec?: string;
}

export interface ShippingStatsParams {
    field: string;
    vendor?: string;
    material?: string;
    spec?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
}

// 1. Fetch Lists
export const useShippingList = (params: ShippingSearchParams) => {
    return useQuery({
        queryKey: ['shippingList', params],
        queryFn: async () => {
            const queryParams = new URLSearchParams();
            queryParams.append('page', params.page.toString());
            if (params.start_date) queryParams.append('start_date', params.start_date);
            if (params.end_date) queryParams.append('end_date', params.end_date);
            if (params.vendor) queryParams.append('vendor', params.vendor);
            if (params.material) queryParams.append('material', params.material);
            if (params.spec) queryParams.append('spec', params.spec);

            const res = await api.get<{ data: ShippingInspection[], total_pages: number }>(`/data?${queryParams.toString()}`);
            return res.data;
        },
        placeholderData: (previousData) => previousData,
        staleTime: 60 * 1000,
    });
};

export const useShippingStats = (params: ShippingStatsParams) => {
    return useQuery({
        queryKey: ['shippingStats', params],
        queryFn: async () => {
            if (!params.vendor && !params.material && !params.spec) return null;

            const queryParams = new URLSearchParams();
            queryParams.append('field', params.field);
            if (params.vendor) queryParams.append('vendor', params.vendor);
            if (params.material) queryParams.append('material', params.material);
            if (params.spec) queryParams.append('spec', params.spec);
            if (params.start_date) queryParams.append('start_date', params.start_date);
            if (params.end_date) queryParams.append('end_date', params.end_date);
            if (params.limit) queryParams.append('limit', params.limit.toString());

            const res = await api.get(`/stats?${queryParams.toString()}`);
            return res.data;
        },
        enabled: !!(params.vendor || params.material || params.spec),
        staleTime: 5 * 60 * 1000,
    });
};

// 2. Options
export const useInspectors = () => {
    return useQuery({
        queryKey: ['inspectors'],
        queryFn: async () => {
            const res = await api.get<Inspector[]>('/inspectors', { params: { group: '品保' } });
            return res.data;
        },
        staleTime: 60 * 60 * 1000,
    });
};

export const useVendors = () => {
    return useQuery({
        queryKey: ['vendors'],
        queryFn: async () => {
            const res = await api.get<Vendor[]>('/vendors');
            return res.data;
        },
        staleTime: 60 * 60 * 1000,
    });
};

// 3. Detail
export const useShippingDetail = (id: number | null) => {
    return useQuery({
        queryKey: ['shippingDetail', id],
        queryFn: async () => {
            if (!id) return null;
            const res = await api.get<ShippingInspection>(`/data/${id}`);
            return res.data;
        },
        enabled: !!id,
        staleTime: 60 * 1000,
    });
};

// 4. Mutations
export const useCreateShipping = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: ShippingCreateInput) => {
            const res = await api.post('/add', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('新增成功');
            queryClient.invalidateQueries({ queryKey: ['shippingList'] });
            queryClient.invalidateQueries({ queryKey: ['shippingStats'] });
        },
    });
};

export const useUpdateShipping = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id: _id, data }: { id: number; data: ShippingUpdateInput }) => {
            const res = await api.post('/update', data);
            return res.data;
        },
        onSuccess: (_data, variables) => {
            toast.success('更新成功');
            queryClient.invalidateQueries({ queryKey: ['shippingList'] });
            queryClient.invalidateQueries({ queryKey: ['shippingDetail', variables.id] });
            queryClient.invalidateQueries({ queryKey: ['shippingStats'] });
        },
    });
};

export const useDeleteShipping = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.post('/delete', { id });
            return res.data;
        },
        onSuccess: () => {
            toast.success('刪除成功');
            queryClient.invalidateQueries({ queryKey: ['shippingList'] });
            queryClient.invalidateQueries({ queryKey: ['shippingStats'] });
        },
    });
};

export const useImportShipping = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);
            const res = await api.post('/import', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            return res.data;
        },
        onSuccess: (data) => {
            toast.success(data.message || '匯入成功');
            queryClient.invalidateQueries({ queryKey: ['shippingList'] });
        },
    });
};

// 5. Helpers
export const useCheckTolerance = () => {
    return useMutation({
        mutationFn: async ({ vendor_id, material, spec }: { vendor_id: string | number, material: string, spec: string }) => {
            const res = await api.get<ToleranceResult>(`/tolerance/check?vendor_id=${vendor_id}&material=${encodeURIComponent(material)}&spec=${encodeURIComponent(spec)}`);
            return res.data;
        }
    });
};

// 6. SPC Report Export
export const useExportSpcReport = () => {
    return useMutation({
        mutationFn: async (params: ShippingStatsParams & { vendor?: string; material?: string; spec?: string }) => {
            const queryParams = new URLSearchParams();
            queryParams.append('field', params.field);
            if (params.vendor) queryParams.append('vendor', params.vendor);
            if (params.material) queryParams.append('material', params.material);
            if (params.spec) queryParams.append('spec', params.spec);
            if (params.start_date) queryParams.append('start_date', params.start_date);
            if (params.end_date) queryParams.append('end_date', params.end_date);

            const res = await api.get(`/spc-report?${queryParams.toString()}`, {
                responseType: 'blob'
            });

            downloadResponseBlob(res.data as BlobPart, `SPC報告_${params.field}.xlsx`);
        },
        onSuccess: () => {
            toast.success('SPC 報告匯出成功');
        },
        onError: () => {
            toast.error('SPC 報告匯出失敗');
        }
    });
};

// 7. 離群值管理（AIAG-VDA SPC 2026 §6.6）
export interface ShippingMeasurementItem {
    識別碼: number;
    組別: number;
    量測項目: string;
    測量位置: string;
    量測值: number | null;
    量測最小值: number | null;
    量測最大值: number | null;
    排除統計: boolean;
    排除原因: string | null;
}

export const useShippingMeasurements = (shippingId: number | null) =>
    useQuery<ShippingMeasurementItem[]>({
        queryKey: ['shipping-measurements', shippingId],
        queryFn: async () => (await api.get(`/data/${shippingId}/measurements`)).data,
        enabled: shippingId != null,
    });

export const useSetMeasurementExclusion = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (p: { id: number; excluded: boolean; reason: string }) =>
            (await api.patch(`/measurements/${p.id}/exclusion`, { 排除統計: p.excluded, 排除原因: p.reason })).data,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['shipping-measurements'] });
            queryClient.invalidateQueries({ queryKey: ['shippingStats'] });
        },
    });
};

export const useExportShippingData = () => {
    return useMutation({
        mutationFn: async (params: ShippingSearchParams) => {
            const res = await api.get('/export/excel', {
                params: {
                    vendor: params.vendor,
                    material: params.material,
                    spec: params.spec,
                    start_date: params.start_date,
                    end_date: params.end_date
                },
                responseType: 'blob'
            });
            downloadResponseBlob(res.data as BlobPart, '出貨檢驗數據.xlsx');
        },
        onSuccess: () => {
            toast.success('出貨檢驗資料匯出成功');
        },
        onError: () => {
            toast.error('匯出失敗');
        }
    });
};
