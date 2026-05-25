import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { CARADetail } from '../types';

// ── CARA 明細 ─────────────────────────────────────────────────
export const useCARADetail = (id: number | null) =>
    useQuery({
        queryKey: ['caraDetail', id],
        queryFn: async () => {
            const res = await api.get<CARADetail>(`/caras/${id}`);
            return res.data;
        },
        enabled: !!id,
    });

// ── 步驟更新 ─────────────────────────────────────────────────
export const useUpdateCARAStep = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: Record<string, unknown> }) => {
            const res = await api.patch<CARADetail>(`/caras/${id}/step`, data);
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('儲存成功');
            qc.invalidateQueries({ queryKey: ['caraDetail', vars.id] });
            qc.invalidateQueries({ queryKey: ['caraList'] });
        },
        onError: (err: Error) => {
            toast.error(`儲存失敗：${err.message}`);
        },
    });
};

// ── D8 結案 ───────────────────────────────────────────────────
export const useCloseCARA = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, D8_confirmation }: { id: number; D8_confirmation: string }) => {
            const res = await api.post<CARADetail>(`/caras/${id}/close`, { D8_confirmation });
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('CARA 已結案');
            qc.invalidateQueries({ queryKey: ['caraDetail', vars.id] });
            qc.invalidateQueries({ queryKey: ['caraList'] });
        },
        onError: (err: Error) => {
            toast.error(`結案失敗：${err.message}`);
        },
    });
};

// ── 刪除 CARA ─────────────────────────────────────────────────
export const useDeleteCARA = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            await api.delete(`/caras/${id}`);
        },
        onSuccess: () => {
            toast.success('CARA 已刪除');
            qc.invalidateQueries({ queryKey: ['caraList'] });
        },
    });
};

export const CARA_STEP_LABELS: Record<number, string> = {
    2: 'D2 問題描述',
    3: 'D3 暫時對策',
    4: 'D4 根本原因',
    6: 'D6 實施驗證',
    8: 'D8 結案確認',
};
