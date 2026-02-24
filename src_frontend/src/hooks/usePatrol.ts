
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { PatrolInspection } from '../types';

export interface PatrolSearchParams {
    page: number;
    per_page?: number;
    s_date?: string;
    e_date?: string;
    m_id?: string;
    op_id?: string;
    mat?: string;
    spec?: string;
}

export interface PatrolStatsParams {
    item: string;
    pos: string;
    m_id?: string;
    op_id?: string;
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
            if (params.mat) queryParams.append('mat', params.mat);
            if (params.spec) queryParams.append('spec', params.spec);

            const res = await api.get<{ data: PatrolInspection[], pages: number, total: number }>(`/patrol/history?${queryParams.toString()}`);
            return res.data;
        },
        placeholderData: (previousData) => previousData,
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
            if (params.mat) queryParams.append('mat', params.mat);
            if (params.spec) queryParams.append('spec', params.spec);
            if (params.s_date) queryParams.append('s_date', params.s_date);
            if (params.e_date) queryParams.append('e_date', params.e_date);

            const res = await api.get(`/patrol/spc?${queryParams.toString()}`);
            return res.data;
        },
        // Only fetch if item is provided (pos can be empty for "全段")
        enabled: !!params.item,
    });
};

// --- Mutations ---

export const useCreatePatrol = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: any) => {
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
        mutationFn: async ({ id: _id, data }: { id: number; data: any }) => {
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
