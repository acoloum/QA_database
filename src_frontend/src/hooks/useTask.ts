import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';
import type { ActionTask, TaskStatus, PaginatedResponse } from '../types';
import { normalizeTaskListResponse } from './taskResponseUtils';

export interface TaskListParams {
    source_type?: string;
    source_id?: number;
    status?: TaskStatus;
    category?: string;
    assignee_id?: number;
    due_from?: string;
    due_to?: string;
    page?: number;
    per_page?: number;
}

// ── 任務列表 ─────────────────────────────────────────────────
export const useTaskList = (params: TaskListParams = {}) => {
    return useQuery({
        queryKey: ['taskList', params],
        queryFn: async () => {
            const res = await api.get<PaginatedResponse<ActionTask>>('/tasks', { params });
            return res.data;
        },
    });
};

// ── 我的待辦 ─────────────────────────────────────────────────
export const useMyTasks = () => {
    return useQuery({
        queryKey: ['myTasks'],
        queryFn: async () => {
            const res = await api.get<ActionTask[]>('/tasks/my');
            return res.data;
        },
        refetchInterval: 5 * 60 * 1000, // 每 5 分鐘自動重新整理
    });
};

// ── 依來源查詢任務（CAPA 明細頁）────────────────────────────
export const useTasksBySource = (sourceType: string, sourceId: number | null) => {
    return useQuery({
        queryKey: ['tasks', sourceType, sourceId],
        queryFn: async () => {
            const res = await api.get<ActionTask[]>('/tasks', {
                params: { source_type: sourceType, source_id: sourceId },
            });
            return normalizeTaskListResponse(res.data);
        },
        enabled: !!sourceId,
    });
};

// ── 建立任務 ─────────────────────────────────────────────────
export const useCreateTask = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: {
            source_type: string;
            source_id: number;
            category: string;
            description?: string;
            assignee_id?: number;
            due_date?: string;
        }) => {
            const res = await api.post<ActionTask>('/tasks', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('任務建立成功');
            qc.invalidateQueries({ queryKey: ['taskList'] });
            qc.invalidateQueries({ queryKey: ['myTasks'] });
        },
    });
};

// ── 更新任務狀態 ──────────────────────────────────────────────
export const useUpdateTaskStatus = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (payload: {
            taskId: number;
            status: TaskStatus;
            completion_proof?: string;
            waiver_reason?: string;
        }) => {
            const { taskId, ...body } = payload;
            const res = await api.patch<ActionTask>(`/tasks/${taskId}/status`, body);
            return res.data;
        },
        onSuccess: () => {
            toast.success('任務狀態已更新');
            qc.invalidateQueries({ queryKey: ['taskList'] });
            qc.invalidateQueries({ queryKey: ['myTasks'] });
            qc.invalidateQueries({ queryKey: ['tasks'] });
        },
        onError: (err: Error) => {
            toast.error(`更新失敗：${err.message}`);
        },
    });
};

// ── 刪除任務 ─────────────────────────────────────────────────
export const useDeleteTask = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (taskId: number) => {
            await api.delete(`/tasks/${taskId}`);
        },
        onSuccess: () => {
            toast.success('任務已刪除');
            qc.invalidateQueries({ queryKey: ['taskList'] });
            qc.invalidateQueries({ queryKey: ['myTasks'] });
        },
    });
};

// ── 結案 gate 檢查 ────────────────────────────────────────────
export const useCloseGate = (sourceType: string, sourceId: number | null) => {
    return useQuery({
        queryKey: ['closeGate', sourceType, sourceId],
        queryFn: async () => {
            const res = await api.get<{
                can_close: boolean;
                blocking_tasks: ActionTask[];
            }>('/tasks/check-gate', { params: { source_type: sourceType, source_id: sourceId } });
            return res.data;
        },
        enabled: !!sourceId,
    });
};

// ── 任務類別中文標籤 ──────────────────────────────────────────
export const TASK_CATEGORY_LABELS: Record<string, string> = {
    pfmea:           'PFMEA 更新',
    control_plan:    '管制計畫更新',
    sop:             'SOP 更新',
    training:        '教育訓練',
    cross_part:      '跨料號橫展',
    customer_notify: '客戶通知',
    other:           '其他',
};

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
    pending:     '待辦中',
    in_progress: '進行中',
    completed:   '已完成',
    waived:      '已豁免',
};

export const TASK_STATUS_VARIANT: Record<TaskStatus, string> = {
    pending:     'warning',
    in_progress: 'primary',
    completed:   'success',
    waived:      'secondary',
};
