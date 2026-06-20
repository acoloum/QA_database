// 巡檢型別
export interface PatrolDetail {
    group: string;
    item: string;
    pos: string;
    min: number | null;
    max: number | null;
}

export interface PatrolInspection {
    id: number;
    date: string;
    machine_id?: number;
    machine_name?: string;
    m_name?: string;
    operator_id?: number;
    operator_name?: string;
    op_name?: string;
    inspector_id?: number;
    inspector_name?: string;
    customer_id?: number;
    customer_name?: string;
    cust_name?: string;
    material?: string;
    mat?: string;
    batch?: string;
    spec?: string;
    details?: PatrolDetail[];
    is_ng?: boolean;
    tol_found?: boolean;
}

export interface PatrolCreateInput {
    檢驗日期: string;
    機台ID?: number; // PatrolModal 舊版本可能傳入機台名稱而非 ID
    機台?: string; // PatrolModal 中使用的舊欄位名稱
    機台名稱?: string;
    作業員ID?: number; // PatrolModal 舊版本可能傳入人員名稱而非 ID
    主機手?: string; // PatrolModal 中使用的舊欄位名稱
    作業員姓名?: string;
    客戶名稱?: string; // PatrolModal 中使用的欄位
    檢驗人員ID?: number; // PatrolModal 舊版本可能傳入人員名稱而非 ID
    檢驗人員?: string; // PatrolModal 中使用的舊欄位名稱
    檢驗人員姓名?: string;
    材質?: string;
    原料批號?: string; // PatrolModal 中使用的欄位
    批號?: string;
    擠壓規格?: string; // PatrolModal 中使用的欄位
    規格?: string;
    details: PatrolDetail[];
}

export interface PatrolUpdateInput extends PatrolCreateInput {
    識別碼: number; // 更新時必須提供識別碼
}

