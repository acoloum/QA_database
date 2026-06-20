// ── CAPA 重設計（D0-D8）──────────────────────────────────────
import type { ActionTask } from './task';

export type CAPASeverity = 'Critical' | 'Major' | 'Minor';
export type CAPARigor = '完整8D' | '簡化5D';
export type CAPAStatus = '進行中' | '已結案';

export interface D7Action {
    type: string;
    checked: boolean;
    assignee_id?: number | null;
    due_date?: string | null;
    description?: string;
    part_nos?: string;
}

export interface CAPAProgress {
    total_steps: number;
    completed_steps: number;
    percent: number;
    step_status: Record<string, boolean>;
}

export interface CAPADetail {
    id: number;
    no: string;
    source_type: string;
    source_id: number;
    source_info: Record<string, string | null>;
    rigor: CAPARigor;
    status: CAPAStatus;
    progress: CAPAProgress;
    D0_symptom?: string | null;
    D0_criteria?: string[] | null;
    D0_severity?: CAPASeverity | null;
    D0_deadline?: string | null;
    D1_champion_id?: number | null;
    D1_leader_id?: number | null;
    D1_members?: number[] | null;
    D1_leader_name?: string | null;
    D1_champion_name?: string | null;
    D2_what?: string | null;
    D2_where?: string | null;
    D2_when?: string | null;
    D2_who?: string | null;
    D2_why?: string | null;
    D2_how?: string | null;
    D2_how_many?: string | null;
    D3_action?: string | null;
    D3_effective_date?: string | null;
    D3_verification?: string | null;
    D4_tool?: string | null;
    D4_five_why?: unknown[] | null;
    D4_fishbone?: Record<string, string[]> | null;
    D4_root_cause?: string | null;
    D5_action?: string | null;
    D5_planned_date?: string | null;
    D5_verify_plan?: string | null;
    D6_implement_date?: string | null;
    D6_result?: string | null;
    D6_verified?: boolean;
    D7_actions?: D7Action[];
    tasks?: ActionTask[];
    D8_close_date?: string | null;
    D8_confirmation?: string | null;
    D8_recognition?: string | null;
    created_at?: string;
    closed_at?: string | null;
}

export interface CAPAListItem {
    id: number;
    no: string;
    source_type: string;
    source_id: number;
    rigor: CAPARigor;
    status: CAPAStatus;
    severity?: string | null;
    owner?: string;
    create_date?: string;
    deadline?: string | null;
    progress_percent: number;
    vendor?: string | null;
    ncmr_description?: string | null;
}

export interface VendorPerformance {
  id: number;
  vendor_id: number;
  vendor_name?: string;
  period: string;
  inspection_count: number;
  defect_count: number;
  defect_rate: number;
  capa_count: number;
  avg_capa_days?: number | null;
  complaint_count: number;
  score: number;
  calculated_at?: string;
}

