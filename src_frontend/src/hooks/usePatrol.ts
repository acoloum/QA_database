
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { compactParams } from '../utils/queryParams';
import toast from 'react-hot-toast';
import { downloadResponseBlob } from '../utils/downloadFile';
import type { PatrolInspection, PatrolCreateInput, PatrolUpdateInput, SpcChartData } from '../types';
import { patrolKeys } from './queryKeys';

export interface PatrolSearchParams {
    page: number;
    per_page?: number;
    s_date?: string;
    e_date?: string;
    m_id?: string;
    op_id?: string;
    cust_id?: string;
    mat?: string;
    spec?: string;
}

export interface PatrolStatsParams {
    item: string;
    pos: string;
    m_id?: string;
    op_id?: string;
    cust_id?: string;
    mat?: string;
    spec?: string;
    s_date?: string;
    e_date?: string;
    study_version_id?: number;
}

export interface PatrolOptions {
    machines: { id: number; name: string }[];
    operators: { id: number; name: string }[];
    inspectors: { id: number; name: string }[];
    customers: { id: number; name: string }[];
}

export interface PatrolLiveLimitsParams {
    m_id?: string;
    op_id?: string;
    cust_id?: string;
    mat: string;
    spec: string;
    item: string;
    pos: string;
    exclude_main_id?: number;
}

export interface PatrolLiveLimits {
    found: boolean;
    reason?: string;
    x_cl?: number;
    x_ucl?: number;
    x_lcl?: number;
    r_cl?: number;
    r_ucl?: number;
    r_lcl?: number;
    recent_values?: { min: number; max: number }[];
}

// --- Queries ---

export const usePatrolOptions = () => {
    return useQuery({
        queryKey: patrolKeys.options,
        queryFn: async () => {
            const res = await api.get<PatrolOptions>('/patrol/options');
            return res.data;
        },
        staleTime: 1000 * 60 * 5, // 5 minutes
    });
};

export const usePatrolList = (params: PatrolSearchParams) => {
    return useQuery({
        queryKey: patrolKeys.list(params),
        queryFn: async () => {
            const res = await api.get<{ data: PatrolInspection[], pages: number, total: number }>('/patrol/history', {
                params: {
                    page: params.page,
                    ...compactParams({
                        per_page: params.per_page || undefined,
                        s_date: params.s_date,
                        e_date: params.e_date,
                        m_id: params.m_id,
                        op_id: params.op_id,
                        cust_id: params.cust_id,
                        mat: params.mat,
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

export const usePatrolDetail = (id: number | null) => {
    return useQuery({
        queryKey: patrolKeys.detail(id),
        queryFn: async () => {
            if (!id) return null;
            const res = await api.get(`/patrol/detail/${id}`);
            return res.data;
        },
        enabled: !!id,
        staleTime: 60 * 1000,
    });
};

export const usePatrolStats = (params: PatrolStatsParams) => {
    return useQuery({
        queryKey: patrolKeys.stats(params),
        queryFn: async () => {
            // Check required params if needed, or let backend handle it
            const res = await api.get<SpcChartData>('/patrol/spc', {
                params: {
                    // item/pos 一律送出：pos 為空字串代表「全段」，不可被過濾
                    item: params.item,
                    pos: params.pos,
                    ...compactParams({
                        m_id: params.m_id,
                        op_id: params.op_id,
                        cust_id: params.cust_id,
                        mat: params.mat,
                        spec: params.spec,
                        s_date: params.s_date,
                        e_date: params.e_date,
                    }),
                },
            });
            return res.data;
        },
        // Only fetch if item is provided (pos can be empty for "全段")
        enabled: !!params.item,
        staleTime: 5 * 60 * 1000,
    });
};

export const usePatrolLiveLimits = (params: PatrolLiveLimitsParams, enabled: boolean) => {
    return useQuery({
        queryKey: patrolKeys.liveLimits(params),
        queryFn: async () => {
            const res = await api.get<PatrolLiveLimits>('/patrol/live-limits', {
                params: {
                    // mat/spec/item/pos 一律送出（空字串有其語意），其餘有值才帶
                    mat: params.mat,
                    spec: params.spec,
                    item: params.item,
                    pos: params.pos,
                    ...compactParams({
                        m_id: params.m_id,
                        op_id: params.op_id,
                        cust_id: params.cust_id,
                        exclude_main_id: params.exclude_main_id || undefined,
                    }),
                },
            });
            return res.data;
        },
        enabled: enabled && !!params.mat && !!params.item,
        staleTime: 60 * 1000,
    });
};

export const useExportPatrolSpcReport = () => {
    return useMutation({
        mutationFn: async (params: PatrolStatsParams) => {
            const res = await api.get('/patrol/export', {
                params: {
                    item: params.item,
                    position: params.pos || '全段',
                    ...compactParams({
                        m_id: params.m_id,
                        op_id: params.op_id,
                        cust_id: params.cust_id,
                        mat: params.mat,
                        spec: params.spec,
                        s_date: params.s_date,
                        e_date: params.e_date,
                        study_version_id: params.study_version_id || undefined,
                    }),
                },
                responseType: 'blob',
            });
            downloadResponseBlob(res.data as BlobPart, `巡檢SPC報告_${params.item}.xlsx`);
        },
        onSuccess: () => {
            toast.success('SPC 報告匯出成功');
        },
        onError: () => {
            toast.error('SPC 報告匯出失敗');
        },
    });
};

export const useExportPatrolRawData = () => {
    return useMutation({
        mutationFn: async (params: PatrolSearchParams) => {
            const res = await api.get('/patrol/export', {
                params: compactParams({
                    s_date: params.s_date,
                    e_date: params.e_date,
                    m_id: params.m_id,
                    op_id: params.op_id,
                    cust_id: params.cust_id,
                    mat: params.mat,
                    spec: params.spec,
                }),
                responseType: 'blob',
            });
            downloadResponseBlob(res.data as BlobPart, '巡檢數據.xlsx');
        },
        onSuccess: () => {
            toast.success('巡檢資料匯出成功');
        },
        onError: () => {
            toast.error('匯出失敗，請重新整理後再試');
        },
    });
};

// --- Mutations ---

export const useCreatePatrol = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: PatrolCreateInput) => {
            const res = await api.post('/patrol/add', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('新增成功');
            queryClient.invalidateQueries({ queryKey: patrolKeys.root });
            queryClient.invalidateQueries({ queryKey: patrolKeys.statsRoot });
        },
    });
};

export const useUpdatePatrol = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id: _id, data }: { id: number; data: PatrolUpdateInput }) => {
            const res = await api.post('/patrol/update', data);
            return res.data;
        },
        onSuccess: (_data, variables) => {
            toast.success('更新成功');
            queryClient.invalidateQueries({ queryKey: patrolKeys.root });
            queryClient.invalidateQueries({ queryKey: patrolKeys.detail(variables.id) });
            queryClient.invalidateQueries({ queryKey: patrolKeys.statsRoot });
        },
    });
};

export const useDeletePatrol = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.post('/patrol/delete', { id });
            return res.data;
        },
        onSuccess: () => {
            toast.success('刪除成功');
            queryClient.invalidateQueries({ queryKey: patrolKeys.root });
            queryClient.invalidateQueries({ queryKey: patrolKeys.statsRoot });
        },
    });
};

export const useImportPatrol = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);
            const res = await api.post('/patrol/import', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            return res.data;
        },
        onSuccess: (data) => {
            toast.success(data.message || '匯入成功');
            queryClient.invalidateQueries({ queryKey: patrolKeys.root });
            queryClient.invalidateQueries({ queryKey: patrolKeys.statsRoot });
        },
    });
};

// --- 離群值管理（AIAG-VDA SPC 2026 §6.6）---

export interface PatrolDetailItem {
    識別碼: number;
    組別: number;
    測量項目: string;
    測量位置: string;
    最小值: number | null;
    最大值: number | null;
    排除統計: boolean;
    排除原因: string | null;
    排除者ID: number | null;
    排除時間: string | null;
}

export const usePatrolDetails = (mainId: number | null) =>
    useQuery<PatrolDetailItem[]>({
        queryKey: patrolKeys.details(mainId),
        queryFn: async () => (await api.get(`/patrol/${mainId}/details`)).data,
        enabled: mainId != null,
    });

export const useSetPatrolDetailExclusion = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (p: { id: number; excluded: boolean; reason: string }) =>
            (await api.patch(`/patrol-details/${p.id}/exclusion`, { 排除統計: p.excluded, 排除原因: p.reason })).data,
        onSuccess: (_data, variables) => {
            toast.success(variables.excluded ? '已標示為離群值' : '已恢復計入統計');
            queryClient.invalidateQueries({ queryKey: patrolKeys.detailsRoot });
            queryClient.invalidateQueries({ queryKey: patrolKeys.statsRoot });
        },
        onError: (err: Error) => {
            toast.error(`操作失敗：${err.message}`);
        },
    });
};
