
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { compactParams } from '../utils/queryParams';
import toast from 'react-hot-toast';
import { downloadResponseBlob } from '../utils/downloadFile';
import type { ToleranceCreateInput, ToleranceUpdateInput } from '../types';
import { toleranceKeys } from './queryKeys';

// Types
export interface ToleranceData {
    id: number;
    material: string;
    spec: string;
    vendor_name: string;
    create_date: string;
    remark?: string;
    // ... potentially other fields
}

export interface ToleranceDetailMain {
    識別碼: number;
    建立日期: string;
    材質: string;
    規格: string;
    廠商ID?: number;
    廠商名稱?: string;
    備註?: string;
}

export interface ToleranceDetailItem {
    測量項目: string;
    測量位置: string;
    尺寸下限: number | null;
    尺寸上限: number | null;
    公差下限: number | null;
    公差上限: number | null;
    標準值: number | null;
    單位: string;
    備註: string;
    特性重要度?: string;
}

export interface ToleranceDetailResponse {
    main: ToleranceDetailMain;
    details: ToleranceDetailItem[];
}

export interface ToleranceSearchParams {
    page: number;
    page_size: number;
    material?: string;
    vendor_id?: string;
    spec?: string;
}

// 1. Fetch Options (Vendors)
export const useToleranceOptions = () => {
    return useQuery({
        queryKey: toleranceKeys.options,
        queryFn: async () => {
            const res = await api.get('/tolerance/options');
            return res.data.vendors || [];
        },
        staleTime: 5 * 60 * 1000, // 5 minutes
    });
};

// 2. Fetch List (Search)
export const useToleranceSearch = (params: ToleranceSearchParams) => {
    return useQuery({
        queryKey: toleranceKeys.list(params),
        queryFn: async () => {
            const res = await api.get('/tolerance/search', {
                params: {
                    page: params.page,
                    page_size: params.page_size,
                    ...compactParams({
                        material: params.material,
                        vendor_id: params.vendor_id,
                        spec: params.spec,
                    }),
                },
            });
            return res.data;
        },
        placeholderData: (previousData) => previousData, // Keep previous data while fetching new page
        staleTime: 5 * 60 * 1000, // 公差標準不常變動，5 分鐘內不重抓
    });
};

// 3. Fetch Detail
export const useToleranceDetail = (id: number | null, enabled = true) => {
    return useQuery({
        queryKey: toleranceKeys.detail(id),
        queryFn: async () => {
            if (!id) return null;
            const res = await api.get(`/tolerance/${id}`);
            return res.data as ToleranceDetailResponse;
        },
        enabled: enabled && !!id, // Only run if id is present
        staleTime: 5 * 60 * 1000, // 公差標準不常變動，5 分鐘內不重抓
    });
};

// 4. Create Mutation
export const useCreateTolerance = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: ToleranceCreateInput) => {
            const res = await api.post('/tolerance/add', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('新增成功');
            queryClient.invalidateQueries({ queryKey: toleranceKeys.root });
        },
    });
};

// 5. Update Mutation
export const useUpdateTolerance = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: ToleranceUpdateInput }) => {
            const res = await api.post(`/tolerance/update/${id}`, data);
            return res.data;
        },
        onSuccess: (_data, variables) => {
            toast.success('更新成功');
            queryClient.invalidateQueries({ queryKey: toleranceKeys.root });
            queryClient.invalidateQueries({ queryKey: toleranceKeys.detail(variables.id) });
        },
    });
};

// 6. Delete Mutation
export const useDeleteTolerance = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.post(`/tolerance/delete/${id}`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('刪除成功');
            queryClient.invalidateQueries({ queryKey: toleranceKeys.root });
        },
    });
};

// 7. Import Mutation
export const useImportTolerance = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);
            const res = await api.post('/tolerance/import', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            return res.data;
        },
        onSuccess: (data) => {
            toast.success(data.message || '匯入成功');
            queryClient.invalidateQueries({ queryKey: toleranceKeys.root });
        },
    });
};

export const useExportToleranceData = () => {
    return useMutation({
        mutationFn: async (params: ToleranceSearchParams) => {
            const res = await api.get('/tolerance/export', {
                params: compactParams({
                    material: params.material,
                    vendor_id: params.vendor_id,
                    spec: params.spec,
                }),
                responseType: 'blob',
            });
            downloadResponseBlob(res.data as BlobPart, '廠商公差資料.xlsx');
        },
        onSuccess: () => {
            toast.success('公差資料匯出成功');
        },
        onError: () => {
            toast.error('匯出失敗');
        },
    });
};
