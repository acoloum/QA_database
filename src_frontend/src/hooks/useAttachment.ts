import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { Attachment } from '../types';
import { attachmentKeys } from './queryKeys';

// ── 查詢附件清單 ─────────────────────────────────────────────
export const useAttachments = (
    entityType: string,
    entityId: number | null,
    dStep?: string,
) => {
    return useQuery({
        queryKey: attachmentKeys.list(entityType, entityId, dStep),
        queryFn: async () => {
            const params: Record<string, string | number> = {
                entity_type: entityType,
                entity_id:   entityId!,
            };
            if (dStep) params.d_step = dStep;
            const res = await api.get<Attachment[]>('/attachments', { params });
            return res.data;
        },
        enabled: !!entityId,
    });
};

// ── 上傳附件 ─────────────────────────────────────────────────
export const useUploadAttachment = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (payload: {
            file: File;
            entity_type: string;
            entity_id: number;
            d_step?: string;
            purpose?: string;
        }) => {
            const form = new FormData();
            form.append('file',        payload.file);
            form.append('entity_type', payload.entity_type);
            form.append('entity_id',   String(payload.entity_id));
            if (payload.d_step) form.append('d_step', payload.d_step);
            if (payload.purpose) form.append('purpose', payload.purpose);

            // 交由瀏覽器與 Axios 自動附加 multipart boundary，避免共用標頭破壞 FormData。
            const res = await api.post<Attachment>('/attachments/upload', form);
            return res.data;
        },
        onSuccess: (_data, vars) => {
            toast.success('附件上傳成功');
            qc.invalidateQueries({
                queryKey: attachmentKeys.list(vars.entity_type, vars.entity_id),
            });
        },
        onError: (err: Error) => {
            toast.error(`上傳失敗：${err.message}`);
        },
    });
};

// ── 刪除附件 ─────────────────────────────────────────────────
export const useDeleteAttachment = (entityType: string, entityId: number) => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (attachmentId: number) => {
            await api.delete(`/attachments/${attachmentId}`);
        },
        onSuccess: () => {
            toast.success('附件已刪除');
            qc.invalidateQueries({
                queryKey: attachmentKeys.list(entityType, entityId),
            });
        },
        onError: (err: Error) => {
            toast.error(`刪除失敗：${err.message}`);
        },
    });
};

// ── 下載 URL ─────────────────────────────────────────────────
export const getAttachmentDownloadUrl = (attachmentId: number) =>
    `/api/attachments/${attachmentId}/download`;
