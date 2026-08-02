
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { compactParams } from '../utils/queryParams';
import toast from 'react-hot-toast';
import { downloadResponseBlob } from '../utils/downloadFile';
import { shippingKeys, masterDataKeys } from './queryKeys';
import type {
    ShippingInspection, Vendor, ToleranceResult, ShippingCreateInput,
    ShippingUpdateInput, SpcChartData,
} from '../types';

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
    study_version_id?: number;
}

// 1. Fetch Lists
export const useShippingList = (params: ShippingSearchParams) => {
    return useQuery({
        queryKey: shippingKeys.list(params),
        queryFn: async () => {
            const res = await api.get<{ data: ShippingInspection[], total_pages: number }>('/data', {
                params: {
                    page: params.page,
                    ...compactParams({
                        start_date: params.start_date,
                        end_date: params.end_date,
                        vendor: params.vendor,
                        material: params.material,
                        spec: params.spec,
                    }),
                },
            });
            return res.data;
        },
        placeholderData: (previousData) => previousData,
        staleTime: 60 * 1000,
    });
};

export const useShippingStats = (params: ShippingStatsParams) => {
    return useQuery({
        queryKey: shippingKeys.stats(params),
        queryFn: async () => {
            if (!params.vendor && !params.material && !params.spec) return null;

            const res = await api.get<SpcChartData>('/stats', {
                params: {
                    field: params.field,
                    ...compactParams({
                        vendor: params.vendor,
                        material: params.material,
                        spec: params.spec,
                        start_date: params.start_date,
                        end_date: params.end_date,
                        // limit=0 無意義，沿用原本的 truthy 判斷
                        limit: params.limit || undefined,
                    }),
                },
            });
            return res.data;
        },
        enabled: !!(params.vendor || params.material || params.spec),
        staleTime: 5 * 60 * 1000,
    });
};

// 2. Options
// 檢驗人員選項統一由 hooks/useInspectors 提供（key 含 group 參數），
// 避免此處重複定義與其他頁面共用 cache key 造成資料互相污染。
export const useVendors = () => {
    return useQuery({
        queryKey: masterDataKeys.vendors,
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
        queryKey: shippingKeys.detail(id),
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
            queryClient.invalidateQueries({ queryKey: shippingKeys.root });
            queryClient.invalidateQueries({ queryKey: shippingKeys.statsRoot });
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
            queryClient.invalidateQueries({ queryKey: shippingKeys.root });
            queryClient.invalidateQueries({ queryKey: shippingKeys.detail(variables.id) });
            queryClient.invalidateQueries({ queryKey: shippingKeys.statsRoot });
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
            queryClient.invalidateQueries({ queryKey: shippingKeys.root });
            queryClient.invalidateQueries({ queryKey: shippingKeys.statsRoot });
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
            queryClient.invalidateQueries({ queryKey: shippingKeys.root });
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
            const res = await api.get('/spc-report', {
                params: {
                    field: params.field,
                    ...compactParams({
                        vendor: params.vendor,
                        material: params.material,
                        spec: params.spec,
                        start_date: params.start_date,
                        end_date: params.end_date,
                        study_version_id: params.study_version_id || undefined,
                    }),
                },
                responseType: 'blob',
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
    排除者ID: number | null;
    排除時間: string | null;
}

export const useShippingMeasurements = (shippingId: number | null) =>
    useQuery<ShippingMeasurementItem[]>({
        queryKey: shippingKeys.measurements(shippingId),
        queryFn: async () => (await api.get(`/data/${shippingId}/measurements`)).data,
        enabled: shippingId != null,
    });

export const useSetMeasurementExclusion = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (p: { id: number; excluded: boolean; reason: string }) =>
            (await api.patch(`/measurements/${p.id}/exclusion`, { 排除統計: p.excluded, 排除原因: p.reason })).data,
        onSuccess: (_data, variables) => {
            toast.success(variables.excluded ? '已標示為離群值' : '已恢復計入統計');
            queryClient.invalidateQueries({ queryKey: shippingKeys.measurementsRoot });
            queryClient.invalidateQueries({ queryKey: shippingKeys.statsRoot });
        },
        onError: (err: Error) => {
            toast.error(`操作失敗：${err.message}`);
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
