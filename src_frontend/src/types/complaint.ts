// ── 客訴 ─────────────────────────────────────────────────────
export type ComplaintType = 'quality' | 'warranty' | 'field_failure';
export type ComplaintStatus = '待處理' | '處理中' | '已結案';

export interface CustomerComplaint {
    id: number;
    complaint_no: string;
    customer: string;
    complaint_date: string;
    material?: string | null;
    spec?: string | null;
    extrusion_nos?: string[];
    description: string;
    severity?: string | null;
    defect_category?: string | null;
    complaint_type: ComplaintType;
    device_serial?: string | null;
    usage_env?: string | null;
    failure_hours?: number | null;
    initial_reply_deadline?: string | null;
    final_reply_deadline?: string | null;
    initial_reply?: string | null;
    initial_reply_date?: string | null;
    final_reply?: string | null;
    final_reply_date?: string | null;
    is_repeat: boolean;
    repeat_refs: string[];
    related_capa_id?: number | null;
    related_rework_id?: number | null;
    status: ComplaintStatus;
    created_by?: number | null;
    created_at?: string;
    overdue_days?: number;
    is_overdue?: boolean;
}

