export interface User {
    user_id: string;
    username: string;
}

export interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
}

export interface LoginResponse {
    token: string;
    username: string;
    user_id: string;
    error?: string;
}

export interface VerifyTokenResponse {
    valid: boolean;
    username: string;
    user_id: string;
}

// Rework Interfaces
export interface ReworkApplication {
    識別碼: number;
    申請單號: string;
    申請日期: string;
    NCMR_ID: number;
    ncmr_number?: string;
    申請人員姓名: string;
    部門: string;
    產品資訊: string;
    重工數量: number;
    緊急程度: '普通' | '重要' | '緊急';
    狀態: '申請中' | '已核准' | '執行中' | '已完成' | '已拒絕';
    申請原因?: string;
    預計完成日期?: string;
    審核狀態?: string;
    審核意見?: string;
    廠商?: string;
    材質?: string;
    批號?: string;
}

export interface ToleranceResult {
    is_valid: boolean;
    violates: {
        item: string;
        value: number;
        min: number;
        max: number;
    }[];
}

// Patrol Types
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
    material?: string;
    mat?: string;
    batch?: string;
    spec?: string;
    details?: PatrolDetail[];
}

// NCMR Types
export interface NCMR {
    id: number;
    no?: string; // 單號
    date: string;
    source: string;
    vendor?: string;
    material?: string;
    product_info?: string;
    product_qty?: number;
    batch?: string;
    defect_desc?: string;
    defect_qty?: number;
    inspector_name?: string;
    result?: string; // 判定結果
    defect_category?: string;
    defect_reason?: string;
    status: string;
    car_status?: string;
    capa_status?: string;
    rework_status?: string;
    rework_count?: number;
}

export interface ReworkStatistics {
    application_stats: {
        total_applications: number;
        in_progress: number;
        completed: number;
        approved: number;
        rejected: number;
        total_rework_quantity: number;
    };
    department_stats: { department: string; count: number }[];
    cost_stats: {
        total_cost: number;
        labor_cost: number;
        material_cost: number;
        equipment_cost: number;
    };
}

export interface Inspector {
    id: number;
    name: string;
}

export interface Vendor {
    id: number;
    name: string;
}

export interface ShippingInspection {
    識別碼: number;
    檢驗日期: string;
    檢驗人員姓名: string;
    廠商中文名稱: string;
    檢驗規格: string;
    材質: string;
    訂單號碼?: string;
    // Dynamic measurement fields
    [key: string]: any;
}

export interface ToleranceItem {
    項目: string;
    標準值: number | null;
    公差上限: number | null;
    公差下限: number | null;
    尺寸上限: number | null;
    尺寸下限: number | null;
    單位: string;
}

export interface ToleranceResult {
    success: boolean;
    found: boolean;
    tolerances: ToleranceItem[];
    message?: string;
}

export interface ReworkExecution {
    識別碼?: number;
    重工單號: number;
    負責人員姓名: string;
    執行部門: string;
    協同人員?: string;
    開始時間: string;
    預計完成時間?: string;
    實際完成時間?: string;
    使用設備?: string;
    SOP編號?: string;
    完成數量: number;
    不良數量: number;
    重工方式?: string;
    耗材記錄?: string;
    執行狀況?: string;
    異常狀況?: string;
    良率?: string;
}

export interface ReworkInspection {
    識別碼?: number;
    重工單號: number;
    檢驗日期: string;
    檢驗人員姓名: string;
    檢驗項目?: string;
    檢驗標準?: string;
    檢驗結果: string;
    不良數量: number;
    檢驗備註?: string;
}

export interface ReworkCost {
    識別碼?: number;
    重工單號: number;
    記錄日期?: string;
    記錄人員姓名?: string;
    成本類型: '人工' | '材料' | '設備' | '其他';
    成本項目: string;
    單位成本: number;
    數量: number;
    總成本?: number;
    備註?: string;
}

export interface CAPA {
    id: number;
    no?: string; // 8D單號
    ncmr_id: number;
    ncmr_no?: string;
    create_date: string;
    owner_name: string;
    status: string;
    // Dynamic D1-D8 fields
    [key: string]: any;
}

export interface CAR {
    id: number;
    no: string; // 單號
    ncmr_id: number;
    ncmr_no?: string;
    create_date: string;
    owner_name: string;
    status: string;
    // Dynamic D-fields
    [key: string]: any;
}

export interface CA_Detail<T> {
    ncmr: {
        發現日期: string;
        廠商: string;
        材質: string;
        產品資訊: string;
        來源: string;
        不良描述: string;
    };
    main: T; // CAPA or CAR data
}

export interface ToleranceStandard {
    id: number;
    material: string;
    spec: string;
    vendor_id?: number;
    vendor_name?: string;
    remark?: string;
    create_date: string;
    details?: ToleranceDetailParams[];
}

export interface ToleranceDetailParams {
    item: string;
    position: string;
    size_min: number | null;
    size_max: number | null;
    tol_min: number | null;
    tol_max: number | null;
    std: number | null;
    unit: string;
    remark: string;
}

// SPC Types
export interface SpcViolation {
    label: string;
    reasons: string[];
    type: 'xbar' | 'r';
}

export interface ProcessCapability {
    available: boolean;
    usl?: number;
    lsl?: number;
    cp?: number;
    cpk?: number;
    cpu?: number;
    cpl?: number;
    pp?: number;
    ppk?: number;
    ppu?: number;
    ppl?: number;
    sigma_within?: number;
    sigma_overall?: number;
    ppm?: {
        upper: number;
        lower: number;
        total: number;
    };
}

export interface DistributionStats {
    skewness?: number;
    kurtosis?: number;
    normality?: 'good' | 'moderate' | 'poor';
    normality_label?: string;
}

export interface CpkTrend {
    month: string;
    cpk: number;
    count: number;
}

export interface ToleranceLimits {
    USL?: number | null;
    LSL?: number | null;
    公差上限?: number | null;
    公差下限?: number | null;
    尺寸上限?: number | null;
    尺寸下限?: number | null;
    found: boolean;
}

export interface SpcChartData {
    labels: string[];
    ids: string[];
    dates: string[];
    avgs: number[];
    ranges: number[];
    subgroup_sizes: number[];
    all_values: number[];
    x_cl: number;
    x_ucl: number;
    x_lcl: number;
    r_cl: number;
    r_ucl: number;
    r_lcl: number;
    avg_subgroup_size: number;
    tolerance: ToleranceLimits;
    process_capability: ProcessCapability;
    distribution_stats: DistributionStats;
    cpk_trend: CpkTrend[];
}

export interface HistogramBin {
    label: string;
    count: number;
    min: number;
    max: number;
}
