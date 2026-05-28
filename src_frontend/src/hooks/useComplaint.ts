import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { CustomerComplaint, PaginatedResponse } from '../types';

export interface ComplaintListParams {
    customer?: string;
    material?: string;
    spec?: string;
    status?: string;
    complaint_type?: string;
    date_from?: string;
    date_to?: string;
    is_repeat?: boolean;
    page?: number;
    per_page?: number;
}

// ── 客訴列表 ─────────────────────────────────────────────────
export const useComplaintList = (params: ComplaintListParams = {}) => {
    return useQuery({
        queryKey: ['complaintList', params],
        queryFn: async () => {
            const res = await api.get<PaginatedResponse<CustomerComplaint>>(
                '/complaints', { params }
            );
            return res.data;
        },
    });
};

// ── 客訴明細 ─────────────────────────────────────────────────
export const useComplaintDetail = (id: number | null) => {
    return useQuery({
        queryKey: ['complaintDetail', id],
        queryFn: async () => {
            const res = await api.get<CustomerComplaint>(`/complaints/${id}`);
            return res.data;
        },
        enabled: !!id,
    });
};

// ── 逾期客訴（Dashboard）─────────────────────────────────────
export const useOverdueComplaints = () => {
    return useQuery({
        queryKey: ['overdueComplaints'],
        queryFn: async () => {
            const res = await api.get<CustomerComplaint[]>('/complaints/overdue');
            return res.data;
        },
        refetchInterval: 5 * 60 * 1000,
    });
};

// ── 重複客訴（Dashboard）─────────────────────────────────────
export const useRecentRepeats = (days = 30) => {
    return useQuery({
        queryKey: ['recentRepeats', days],
        queryFn: async () => {
            const res = await api.get<CustomerComplaint[]>('/complaints/recent-repeats', {
                params: { days },
            });
            return res.data;
        },
        refetchInterval: 5 * 60 * 1000,
    });
};

// ── 建立客訴 ─────────────────────────────────────────────────
export const useCreateComplaint = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<CustomerComplaint>) => {
            const res = await api.post<CustomerComplaint>('/complaints', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('客訴建立成功');
            qc.invalidateQueries({ queryKey: ['complaintList'] });
        },
        onError: (err: Error) => {
            toast.error(`建立失敗：${err.message}`);
        },
    });
};

// ── 更新客訴 ─────────────────────────────────────────────────
export const useUpdateComplaint = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: Partial<CustomerComplaint> }) => {
            const res = await api.put<CustomerComplaint>(`/complaints/${id}`, data);
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('客訴已更新');
            qc.invalidateQueries({ queryKey: ['complaintList'] });
            qc.invalidateQueries({ queryKey: ['complaintDetail', vars.id] });
        },
        onError: (err: Error) => {
            toast.error(`更新失敗：${err.message}`);
        },
    });
};

// ── 刪除客訴 ─────────────────────────────────────────────────
export const useDeleteComplaint = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            await api.delete(`/complaints/${id}`);
        },
        onSuccess: () => {
            toast.success('客訴已刪除');
            qc.invalidateQueries({ queryKey: ['complaintList'] });
        },
    });
};

// ── 從客訴開立 CAPA ───────────────────────────────────────────
export const useOpenCapaFromComplaint = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (complaintId: number) => {
            const res = await api.post(`/complaints/${complaintId}/open-capa`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('CAPA 已開立');
            qc.invalidateQueries({ queryKey: ['complaintList'] });
            qc.invalidateQueries({ queryKey: ['capaList'] });
        },
        onError: (err: Error) => {
            toast.error(`開立失敗：${err.message}`);
        },
    });
};


// ── 從客訴開立重工 ────────────────────────────────────────────
export const useOpenReworkFromComplaint = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (complaintId: number) => {
            const res = await api.post(`/complaints/${complaintId}/open-rework`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('重工申請單已開立');
            qc.invalidateQueries({ queryKey: ['complaintList'] });
        },
        onError: (err: Error) => {
            toast.error(`開立失敗：${err.message}`);
        },
    });
};

// ── 統計查詢 ─────────────────────────────────────────────────
export const useComplaintStatsByCustomer = (params?: { date_from?: string; date_to?: string }) =>
    useQuery({
        queryKey: ['complaintStats', 'customer', params],
        queryFn: async () => {
            const res = await api.get('/complaints/stats/by-customer', { params });
            return res.data as { customer: string; total: number; repeat_count: number; repeat_rate: number }[];
        },
    });

export const useComplaintStatsByProduct = (params?: { date_from?: string; date_to?: string }) =>
    useQuery({
        queryKey: ['complaintStats', 'product', params],
        queryFn: async () => {
            const res = await api.get('/complaints/stats/by-product', { params });
            return res.data as { material: string; spec: string; total: number; repeat_count: number; repeat_rate: number }[];
        },
    });

export const useComplaintStatsByMonth = (params?: { date_from?: string; date_to?: string }) =>
    useQuery({
        queryKey: ['complaintStats', 'month', params],
        queryFn: async () => {
            const res = await api.get('/complaints/stats/by-month', { params });
            return res.data as { year_month: string; total: number }[];
        },
    });

export const useComplaintStatsWarranty = (params?: { date_from?: string; date_to?: string }) =>
    useQuery({
        queryKey: ['complaintStats', 'warranty', params],
        queryFn: async () => {
            const res = await api.get('/complaints/stats/warranty', { params });
            return res.data as {
                total: number;
                warranty_count: number;
                field_failure_count: number;
                avg_failure_hours: number | null;
                by_material: { material: string; total: number }[];
            };
        },
    });

// ── 常數 ─────────────────────────────────────────────────────
export const COMPLAINT_TYPE_LABELS: Record<string, string> = {
    quality:       '品質客訴',
    warranty:      '保固申請',
    field_failure: '現場故障',
};

export const COMPLAINT_STATUS_VARIANT: Record<string, string> = {
    '待處理': 'warning',
    '處理中': 'primary',
    '已結案': 'success',
};
