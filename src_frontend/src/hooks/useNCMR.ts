
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { NCMR, NCMRCreateInput, NCMRUpdateInput } from '../types';

// --- Queries ---

// --- 清單 API 篩選參數型別 ---

export interface NCMRListParams {
    page?: number;
    per_page?: number;
    date_from?: string;
    date_to?: string;
    source?: string;
    vendor?: string;
    material?: string;
    product_info?: string;
    status?: string;
}

export interface CARListParams {
    page?: number;
    per_page?: number;
    date_from?: string;
    date_to?: string;
    vendor?: string;
    material?: string;
    product_info?: string;
    status?: string;
}

export type CAPAListParams = CARListParams;

export const useNCMRList = (params: NCMRListParams = {}) => {
    return useQuery({
        queryKey: ['ncmrList', params],
        queryFn: async () => {
            const res = await api.get<{
                data: NCMR[];
                total: number;
                page: number;
                per_page: number;
            }>('/ncmr', { params });
            const mapped = res.data.data.map((item: NCMR) => ({
                id: item.識別碼 ?? item.id,
                no: item.單號 || item.no,
                date: item.日期 || item.發現日期 || item.date,
                source: item.來源 || item.source,
                vendor: item.廠商 || item.vendor,
                material: item.材質 || item.material,
                product_info: item.產品資訊 || item.product_info,
                product_qty: item.產品數量 || item.product_qty,
                defect_qty: item.不合格數量 != null ? Number(item.不合格數量) : item.defect_qty,
                defect_desc: item.不良描述 || item.defect_desc,
                defect_category: item.不良原因大類 || item.defect_category,
                defect_reason: item.不良原因細項 || item.defect_reason,
                result: item.判定結果 || item.result,
                status: item.狀態 || item.status,
                car_status: item.CAR狀態 || item.car狀態 || item.car_status,
                capa_status: item.CAPA狀態 || item.capa狀態 || item.capa_status,
                rework_status: item.重工狀態 || item.rework_status,
                rework_count: item.重工執行次數 || item.rework_count,
            } as NCMR));
            return {
                data: mapped,
                total: res.data.total,
                page: res.data.page,
                per_page: res.data.per_page,
            };
        },
    });
};

export const useCARAList = (params: CARListParams = {}) => {
    return useQuery({
        queryKey: ['caraList', params],
        queryFn: async () => {
            const res = await api.get<{
                data: Record<string, unknown>[];
                total: number;
                page: number;
                per_page: number;
            }>('/caras', { params });
            const mapped = res.data.data.map((item) => ({
                id: item['id'] as number,
                no: item['no'],
                ncmr_no: item['ncmr_no'] || item['ncmr_id'],
                source: item['source'],
                vendor: item['vendor'],
                material: item['material'],
                product: item['product'],
                create_date: item['created_at'],
                owner: item['owner'],
                status: item['status'],
            }));
            return {
                data: mapped,
                total: res.data.total,
                page: res.data.page,
                per_page: res.data.per_page,
            };
        },
    });
};

export const useCAPAList = (params: CAPAListParams = {}) => {
    return useQuery({
        queryKey: ['capaList', params],
        queryFn: async () => {
            const res = await api.get<{
                data: Record<string, unknown>[];
                total: number;
                page: number;
                per_page: number;
            }>('/capa', { params });
            const mapped = res.data.data.map((item) => ({
                id: item['識別碼'] as number,
                no: item['8D單號'] || item['識別碼'],
                ncmr_no: item['NCMR單號'] || ('#' + item['NCMR_ID']),
                source: item['來源'],
                vendor: item['廠商'],
                material: item['材質'],
                spec: item['規格'],
                create_date: item['ncmr_date'] || item['建立日期'],
                owner: item['負責人員姓名'],
                status: item['狀態'],
            }));
            return {
                data: mapped,
                total: res.data.total,
                page: res.data.page,
                per_page: res.data.per_page,
            };
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
        staleTime: 1000 * 60 * 10, // 10 分鐘
    });
};

// --- Mutations ---

export const useCreateNCMR = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: NCMRCreateInput) => {
            const res = await api.post('/ncmr/add', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('新增成功');
            queryClient.invalidateQueries({ queryKey: ['ncmrList'], exact: false });
        },
    });
};

export const useUpdateNCMR = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: NCMRUpdateInput) => {
            // Data should contain '識別碼' (id)
            const res = await api.post('/ncmr/update', data);
            return res.data;
        },
        onSuccess: (_, variables) => {
            toast.success('更新成功');
            queryClient.invalidateQueries({ queryKey: ['ncmrList'], exact: false });
            if (variables.識別碼) {
                queryClient.invalidateQueries({ queryKey: ['ncmrDetail', variables.識別碼], exact: false });
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
            queryClient.invalidateQueries({ queryKey: ['ncmrList'], exact: false });
        },
    });
};

export const useCreateCARA = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (ncmrId: number) => {
            const res = await api.post('/cara/create', { ncmr_id: ncmrId });
            return res.data;
        },
        onSuccess: (data) => {
            if (data.success) {
                toast.success(`CAR單號：${data.car_number} 已成功建立！`);
            }
            queryClient.invalidateQueries({ queryKey: ['ncmrList'], exact: false });
            queryClient.invalidateQueries({ queryKey: ['ncmrDetail'], exact: false });
        },
    });
};

export const useCreateCAPA = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (ncmrId: number) => {
            const res = await api.post('/capa/create', { ncmr_id: ncmrId });
            return res.data;
        },
        onSuccess: () => {
            toast.success('已成功建立 CAPA 單');
            queryClient.invalidateQueries({ queryKey: ['ncmrList'], exact: false });
            queryClient.invalidateQueries({ queryKey: ['ncmrDetail'], exact: false });
        },
    });
};
