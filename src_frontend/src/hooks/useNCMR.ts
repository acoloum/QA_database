
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { NCMR, NCMRCreateInput, NCMRUpdateInput, NcmrDisposition, RiskRelease } from '../types';
import { ncmrKeys } from './queryKeys';

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

export const useNCMRList = (params: NCMRListParams = {}) => {
    return useQuery({
        queryKey: ncmrKeys.list(params),
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
        placeholderData: (previousData) => previousData,
        staleTime: 60 * 1000,
    });
};


export const useNCMRDetail = (id: number | null) => {
    return useQuery({
        queryKey: ncmrKeys.detail(id),
        queryFn: async () => {
            if (!id) return null;
            const res = await api.get(`/ncmr/${id}`);
            return res.data;
        },
        enabled: !!id,
        staleTime: 60 * 1000,
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
            queryClient.invalidateQueries({ queryKey: ncmrKeys.root, exact: false });
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
            queryClient.invalidateQueries({ queryKey: ncmrKeys.root, exact: false });
            if (variables.識別碼) {
                queryClient.invalidateQueries({ queryKey: ncmrKeys.detail(variables.識別碼), exact: false });
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
            queryClient.invalidateQueries({ queryKey: ncmrKeys.root, exact: false });
        },
    });
};


export const useCreateCAPA = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (ncmrId: number) => {
            const res = await api.post(`/ncmr/${ncmrId}/open-capa`, {});
            return res.data;
        },
        onSuccess: (_, ncmrId) => {
            toast.success('已成功建立 CAPA 單');
            queryClient.invalidateQueries({ queryKey: ncmrKeys.root, exact: false });
            queryClient.invalidateQueries({ queryKey: ncmrKeys.detail(ncmrId), exact: false });
        },
    });
};

// --- 不合格品處置（IATF §8.7）---

export const useDispositions = (ncmrId: number | null) => {
    return useQuery({
        queryKey: ncmrKeys.dispositions(ncmrId),
        queryFn: async () => {
            if (!ncmrId) return [];
            const res = await api.get<NcmrDisposition[]>(`/ncmr/${ncmrId}/dispositions`);
            return res.data;
        },
        enabled: !!ncmrId,
        staleTime: 60 * 1000,
    });
};

export const useCreateDisposition = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ ncmrId, data }: { ncmrId: number; data: NcmrDisposition }) => {
            const res = await api.post(`/ncmr/${ncmrId}/dispositions`, data);
            return res.data;
        },
        onSuccess: (_, variables) => {
            toast.success('已新增處置');
            queryClient.invalidateQueries({ queryKey: ncmrKeys.dispositions(variables.ncmrId), exact: false });
        },
    });
};

export const useUpdateDisposition = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: NcmrDisposition }) => {
            const res = await api.put(`/ncmr/dispositions/${id}`, data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('已更新處置');
            queryClient.invalidateQueries({ queryKey: ncmrKeys.dispositionsRoot, exact: false });
        },
    });
};

export const useDeleteDisposition = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.delete(`/ncmr/dispositions/${id}`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('已刪除處置');
            queryClient.invalidateQueries({ queryKey: ncmrKeys.dispositionsRoot, exact: false });
        },
    });
};

export const useNcmrReworks = (ncmrId: number | null) => {
    return useQuery({
        queryKey: ncmrKeys.reworks(ncmrId),
        queryFn: async () => {
            if (!ncmrId) return [];
            const res = await api.get<{ 識別碼: number; 申請單號: string; 狀態: string }[]>(`/ncmr/${ncmrId}/reworks`);
            return res.data;
        },
        enabled: !!ncmrId,
        staleTime: 60 * 1000,
    });
};

export const useRiskReleases = () => {
    return useQuery({
        queryKey: ncmrKeys.riskReleases,
        queryFn: async () => {
            const res = await api.get<RiskRelease[]>('/ncmr/risk-releases');
            return res.data;
        },
        staleTime: 60 * 1000,
    });
};
