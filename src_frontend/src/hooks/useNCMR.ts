
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';

// --- Queries ---

export const useNCMRList = (status?: string) => {
    return useQuery({
        queryKey: ['ncmrList', status],
        queryFn: async () => {
            const params = status ? { status } : {};
            const res = await api.get<any[]>('/ncmr', { params });
            // Map the data to ensure consistent structure if needed, 
            // but for now we'll return raw data and let component map it or map it here.
            // Component mapping:
            return res.data.map((item: any) => ({
                id: item.識別碼,
                no: item.單號 || String(item.識別碼),
                date: item.日期 || item.發現日期,
                source: item.來源,
                vendor: item.廠商,
                material: item.材質,
                product_info: item.產品資訊,
                product_qty: item.產品數量,
                defect_desc: item.不良描述,
                defect_category: item.不良原因大類,
                defect_reason: item.不良原因細項,
                result: item.判定結果,
                status: item.狀態,
                car_status: item.CAR狀態 || item.car狀態,
                capa_status: item.CAPA狀態 || item.capa狀態,
                rework_status: item.重工狀態,
                rework_count: item.重工執行次數
            }));
        },
    });
};

export const useNCMRDetail = (id: number | null) => {
    return useQuery({
        queryKey: ['ncmrDetail', id],
        queryFn: async () => {
            if (!id) return null;
            const res = await api.get(`/ncmr/${id}`);
            return res.data;
        },
        enabled: !!id,
    });
};

export const useInspectors = () => {
    return useQuery({
        queryKey: ['inspectors'],
        queryFn: async () => {
            const res = await api.get<{ name: string }[]>('/inspectors');
            return res.data;
        },
        staleTime: 1000 * 60 * 60, // 1 hour
    });
};

// --- Mutations ---

export const useCreateNCMR = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: any) => {
            const res = await api.post('/ncmr/add', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('新增成功');
            queryClient.invalidateQueries({ queryKey: ['ncmrList'] });
        },
    });
};

export const useUpdateNCMR = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: any) => {
            // Data should contain '識別碼' (id)
            const res = await api.post('/ncmr/update', data);
            return res.data;
        },
        onSuccess: (_, variables) => {
            toast.success('更新成功');
            queryClient.invalidateQueries({ queryKey: ['ncmrList'] });
            if (variables.識別碼) {
                queryClient.invalidateQueries({ queryKey: ['ncmrDetail', variables.識別碼] });
            }
        },
    });
};

export const useDeleteNCMR = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.post('/ncmr/delete', { id });
            return res.data;
        },
        onSuccess: () => {
            toast.success('刪除成功');
            queryClient.invalidateQueries({ queryKey: ['ncmrList'] });
        },
    });
};

export const useCreateCARA = () => {
    // const queryClient = useQueryClient(); // Might need to invalidate if it affects NCMR status
    return useMutation({
        mutationFn: async (ncmrId: number) => {
            const res = await api.post('/cara/create', { ncmr_id: ncmrId });
            return res.data;
        },
        onSuccess: (data) => {
            if (data.success) {
                toast.success(`CAR單號：${data.car_number} 已成功建立！`);
            }
        },
    });
};

export const useCreateCAPA = () => {
    return useMutation({
        mutationFn: async (ncmrId: number) => {
            const res = await api.post('/capa/create', { ncmr_id: ncmrId });
            return res.data;
        },
        onSuccess: () => {
            toast.success('已成功建立 CAPA 單');
        },
    });
};
