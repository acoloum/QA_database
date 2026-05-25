import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { CAPADetail, CAPAListItem, PaginatedResponse } from '../types';

export interface CapaListParams {
    source_type?: string;
    status?: string;
    date_from?: string;
    date_to?: string;
    customer?: string;
    page?: number;
    per_page?: number;
}

// ── CAPA 列表 ─────────────────────────────────────────────────
export const useCapaList = (params: CapaListParams = {}) => {
    return useQuery({
        queryKey: ['capaList', params],
        queryFn: async () => {
            const res = await api.get<PaginatedResponse<CAPAListItem>>('/capas', { params });
            return res.data;
        },
    });
};

// ── CAPA 明細 ─────────────────────────────────────────────────
export const useCapaDetail = (id: number | null) => {
    return useQuery({
        queryKey: ['capaDetail', id],
        queryFn: async () => {
            const res = await api.get<CAPADetail>(`/capas/${id}`);
            return res.data;
        },
        enabled: !!id,
    });
};

// ── 逾期 CAPA（Dashboard）────────────────────────────────────
export const useOverdueCapas = () => {
    return useQuery({
        queryKey: ['overdueCapas'],
        queryFn: async () => {
            const res = await api.get<CAPAListItem[]>('/capas/overdue');
            return res.data;
        },
        refetchInterval: 5 * 60 * 1000,
    });
};

// ── 步驟更新 ─────────────────────────────────────────────────
export const useUpdateCapaStep = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: Record<string, unknown> }) => {
            const res = await api.patch<CAPADetail>(`/capas/${id}/step`, data);
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('儲存成功');
            qc.invalidateQueries({ queryKey: ['capaDetail', vars.id] });
            qc.invalidateQueries({ queryKey: ['capaList'] });
        },
        onError: (err: Error) => {
            toast.error(`儲存失敗：${err.message}`);
        },
    });
};

// ── D6 Gate 查詢 ─────────────────────────────────────────────
export const useD6Gate = (capaId: number | null) => {
    return useQuery({
        queryKey: ['d6Gate', capaId],
        queryFn: async () => {
            const res = await api.get<{ d6_passed: boolean }>(`/capas/${capaId}/d6-gate`);
            return res.data;
        },
        enabled: !!capaId,
    });
};

// ── 結案 Gate 查詢 ─────────────────────────────────────────────
export const useCapaCloseGate = (capaId: number | null) => {
    return useQuery({
        queryKey: ['capaCloseGate', capaId],
        queryFn: async () => {
            const res = await api.get<{
                can_close: boolean;
                d6_passed: boolean;
                blocking_tasks: unknown[];
            }>(`/capas/${capaId}/close-gate`);
            return res.data;
        },
        enabled: !!capaId,
    });
};

// ── D8 結案 ───────────────────────────────────────────────────
export const useCloseCapa = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            id,
            D8_confirmation,
            D8_recognition,
        }: {
            id: number;
            D8_confirmation: string;
            D8_recognition?: string;
        }) => {
            const res = await api.post<CAPADetail>(`/capas/${id}/close`, {
                D8_confirmation,
                D8_recognition,
            });
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('CAPA 已結案');
            qc.invalidateQueries({ queryKey: ['capaDetail', vars.id] });
            qc.invalidateQueries({ queryKey: ['capaList'] });
            qc.invalidateQueries({ queryKey: ['overdueCapas'] });
        },
        onError: (err: Error) => {
            toast.error(`結案失敗：${err.message}`);
        },
    });
};

// ── 刪除 CAPA ─────────────────────────────────────────────────
export const useDeleteCapa = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            await api.delete(`/capas/${id}`);
        },
        onSuccess: () => {
            toast.success('CAPA 已刪除');
            qc.invalidateQueries({ queryKey: ['capaList'] });
        },
    });
};

// ── 從 NCMR 開立 CAPA ─────────────────────────────────────────
export const useOpenCapaFromNcmr = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            ncmrId,
            severity = 'Major',
        }: {
            ncmrId: number;
            severity?: string;
        }) => {
            const res = await api.post(`/ncmr/${ncmrId}/open-capa`, { severity });
            return res.data;
        },
        onSuccess: () => {
            toast.success('CAPA 已開立');
            qc.invalidateQueries({ queryKey: ['capaList'] });
            qc.invalidateQueries({ queryKey: ['ncmrList'] });
        },
        onError: (err: Error) => {
            toast.error(`開立失敗：${err.message}`);
        },
    });
};

// ── 常數 ─────────────────────────────────────────────────────
export const CAPA_SEVERITY_VARIANT: Record<string, string> = {
    Critical: 'danger',
    Major:    'warning',
    Minor:    'info',
};

export const CAPA_STATUS_VARIANT: Record<string, string> = {
    '進行中': 'primary',
    '已結案': 'success',
};

export const RIGOR_STEPS: Record<string, number[]> = {
    '完整8D': [0, 1, 2, 3, 4, 5, 6, 7, 8],
    '簡化5D':  [2, 3, 4, 6, 8],
};

export const D_STEP_LABELS: Record<number, string> = {
    0: 'D0 緊急應對',
    1: 'D1 成立團隊',
    2: 'D2 問題描述',
    3: 'D3 暫時對策',
    4: 'D4 根本原因',
    5: 'D5 永久對策',
    6: 'D6 實施驗證',
    7: 'D7 橫向展開',
    8: 'D8 結案確認',
};
