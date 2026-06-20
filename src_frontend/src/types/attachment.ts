// ── 附件 ──────────────────────────────────────────────────────
export interface Attachment {
    id: number;
    entity_type: string;
    entity_id: number;
    d_step?: string | null;
    file_name: string;
    mime_type: string;
    file_size: number;
    uploader_id?: number;
    created_at?: string;
}

