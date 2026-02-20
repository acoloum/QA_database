
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { ShippingInspection, Inspector, Vendor, ToleranceResult } from '../types';

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
    });
};

// 2. Options
export const useInspectors = () => {
    return useQuery({
        queryKey: ['inspectors'],
        queryFn: async () => {
            const res = await api.get<Inspector[]>('/inspectors');
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
    });
};

// 4. Mutations
export const useCreateShipping = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: any) => {
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
        mutationFn: async ({ id: _id, data }: { id: number; data: any }) => {
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
