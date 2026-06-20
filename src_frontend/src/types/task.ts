// ── 橫展任務 ─────────────────────────────────────────────────
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'waived';
export type TaskCategory =
    | 'pfmea' | 'control_plan' | 'sop' | 'training'
    | 'cross_part' | 'customer_notify' | 'other';

export interface ActionTask {
    id: number;
    task_no: string;
    source_type: string;
    source_id: number;
    category: TaskCategory;
    title?: string;
    description?: string;
    assignee_id?: number;
    assignee_name?: string;
    due_date?: string | null;
    status: TaskStatus;
    completion_proof?: string | null;
    waiver_reason?: string | null;
    is_overdue?: boolean;
    overdue_days?: number;
    created_at?: string;
}

