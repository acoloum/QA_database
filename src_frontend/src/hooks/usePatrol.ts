
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import { downloadResponseBlob } from '../utils/downloadFile';
import type { PatrolInspection, PatrolCreateInput, PatrolUpdateInput } from '../types';

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
}

export interface PatrolOptions {
    machines: { id: number; name: string }[];
    operators: { id: number; name: string }[];
    inspectors: { id: number; name: string }[];
    customers: { id: number; name: string }[];
}

// --- Queries ---

export const usePatrolOptions = () => {
    return useQuery({
        queryKey: ['patrolOptions'],
        queryFn: async () => {
            const res = await api.get<PatrolOptions>('/patrol/options');
            return res.data;
        },
        staleTime: 1000 * 60 * 5, // 5 minutes
    });
};

export const usePatrolList = (params: PatrolSearchParams) => {
    return useQuery({
        queryKey: ['patrolList', params],
        queryFn: async () => {
            const queryParams = new URLSearchParams();
            queryParams.append('page', params.page.toString());
            if (params.per_page) queryParams.append('per_page', params.per_page.toString());
            if (params.s_date) queryParams.append('s_date', params.s_date);
            if (params.e_date) queryParams.append('e_date', params.e_date);
            if (params.m_id) queryParams.append('m_id', params.m_id);
            if (params.op_id) queryParams.append('op_id', params.op_id);
            if (params.cust_id) queryParams.append('cust_id', params.cust_id);
            if (params.mat) queryParams.append('mat', params.mat);
            if (params.spec) queryParams.append('spec', params.spec);

            const res = await api.get<{ data: PatrolInspection[], pages: number, total: number }>(`/patrol/history?${queryParams.toString()}`);
            return res.data;
        },
        placeholderData: (previousData) => previousData,
        staleTime: 60 * 1000,
    });
};

export const usePatrolDetail = (id: number | null) => {
    return useQuery({
        queryKey: ['patrolDetail', id],
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
        queryKey: ['patrolStats', params],
        queryFn: async () => {
            // Check required params if needed, or let backend handle it
            const queryParams = new URLSearchParams();
            queryParams.append('item', params.item);
            queryParams.append('pos', params.pos);
            if (params.m_id) queryParams.append('m_id', params.m_id);
            if (params.op_id) queryParams.append('op_id', params.op_id);
            if (params.cust_id) queryParams.append('cust_id', params.cust_id);
            if (params.mat) queryParams.append('mat', params.mat);
            if (params.spec) queryParams.append('spec', params.spec);
            if (params.s_date) queryParams.append('s_date', params.s_date);
            if (params.e_date) queryParams.append('e_date', params.e_date);

            const res = await api.get(`/patrol/spc?${queryParams.toString()}`);
            return res.data;
        },
        // Only fetch if item is provided (pos can be empty for "全段")
        enabled: !!params.item,
        staleTime: 5 * 60 * 1000,
    });
};

export const useExportPatrolSpcReport = () => {
    return useMutation({
        mutationFn: async (params: PatrolStatsParams) => {
            const queryParams = new URLSearchParams();
            queryParams.append('item', params.item);
            queryParams.append('position', params.pos || '全段');
            if (params.m_id) queryParams.append('m_id', params.m_id);
            if (params.op_id) queryParams.append('op_id', params.op_id);
            if (params.cust_id) queryParams.append('cust_id', params.cust_id);
            if (params.mat) queryParams.append('mat', params.mat);
            if (params.spec) queryParams.append('spec', params.spec);
            if (params.s_date) queryParams.append('s_date', params.s_date);
            if (params.e_date) queryParams.append('e_date', params.e_date);

            const res = await api.get(`/patrol/export?${queryParams.toString()}`, { responseType: 'blob' });
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
            const queryParams = new URLSearchParams();
            if (params.s_date) queryParams.append('s_date', params.s_date);
            if (params.e_date) queryParams.append('e_date', params.e_date);
            if (params.m_id) queryParams.append('m_id', params.m_id);
            if (params.op_id) queryParams.append('op_id', params.op_id);
            if (params.cust_id) queryParams.append('cust_id', params.cust_id);
            if (params.mat) queryParams.append('mat', params.mat);
            if (params.spec) queryParams.append('spec', params.spec);

            const query = queryParams.toString();
            const res = await api.get(`/patrol/export${query ? `?${query}` : ''}`, { responseType: 'blob' });
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
            queryClient.invalidateQueries({ queryKey: ['patrolList'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
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
            queryClient.invalidateQueries({ queryKey: ['patrolList'] });
            queryClient.invalidateQueries({ queryKey: ['patrolDetail', variables.id] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
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
            queryClient.invalidateQueries({ queryKey: ['patrolList'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
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
            queryClient.invalidateQueries({ queryKey: ['patrolList'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
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
}

export const usePatrolDetails = (mainId: number | null) =>
    useQuery<PatrolDetailItem[]>({
        queryKey: ['patrol-details', mainId],
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
            queryClient.invalidateQueries({ queryKey: ['patrol-details'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
        },
        onError: (err: Error) => {
            toast.error(`操作失敗：${err.message}`);
        },
    });
};

// --- 管制界限凍結（AIAG-VDA SPC 2026 §9.4）---

export interface PatrolControlLimitsKey {
    material: string;
    spec: string;
    item: string;
    position: string;
}

export const useFreezePatrolLimits = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (key: PatrolControlLimitsKey & { note?: string }) =>
            (await api.post('/patrol/control-limits', key)).data,
        onSuccess: () => {
            toast.success('管制界限已凍結');
            queryClient.invalidateQueries({ queryKey: ['patrol-control-limits'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
        },
        onError: (err: Error) => {
            toast.error(`凍結失敗：${err.message}`);
        },
    });
};

export const useUnfreezePatrolLimits = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (key: PatrolControlLimitsKey) => {
            const params = new URLSearchParams({
                material: key.material, spec: key.spec, item: key.item, position: key.position,
            });
            return (await api.delete(`/patrol/control-limits?${params.toString()}`)).data;
        },
        onSuccess: () => {
            toast.success('已解除管制界限凍結');
            queryClient.invalidateQueries({ queryKey: ['patrol-control-limits'] });
            queryClient.invalidateQueries({ queryKey: ['patrolStats'] });
        },
        onError: (err: Error) => {
            toast.error(`解除失敗：${err.message}`);
        },
    });
};
