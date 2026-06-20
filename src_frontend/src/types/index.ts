export type * from './rework';
export type * from './tolerance';
export type * from './spc';

export interface PaginatedResponse<T> {
    data: T[];
    total: number;
    page: number;
    per_page: number;
}

export interface User {
    user_id: string;
    username: string;
    role: string;
    permissions?: Record<string, boolean>;
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
    role: string;
    error?: string;
}

export interface VerifyTokenResponse {
    valid: boolean;
    username: string;
    user_id: string;
    role: string;
    permissions?: Record<string, boolean>;
}

export interface UserRecord {
    id: number;
    username: string;
    role: string;
    inspector_id?: number | null;
    is_active: boolean;
    created_at: string | null;
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

// NCMR Types
// API 回傳中文欄位，前端 hook 會將其映射為英文欄位後回傳給元件
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
    // API 回傳的中文欄位（useNCMR hook 映射前的原始結構）
    識別碼?: number;
    單號?: string;
    日期?: string;
    發現日期?: string;
    來源?: string;
    廠商?: string;
    材質?: string;
    產品資訊?: string;
    產品數量?: number;
    不合格數量?: number | string;
    不良描述?: string;
    不良原因大類?: string;
    不良原因細項?: string;
    判定結果?: string;
    狀態?: string;
    CAR狀態?: string;
    car狀態?: string;
    CAPA狀態?: string;
    capa狀態?: string;
    重工狀態?: string;
    重工執行次數?: number;
}

export interface NCMRCreateInput {
    日期?: string;
    建立日期?: string;
    來源?: string; // 部分更新時（如 DispositionModal）不需要來源欄位
    廠商?: string;
    材質?: string;
    產品資訊?: string;
    產品數量?: number | string;
    批號?: string;
    不良描述?: string;
    不合格數量?: number | string; // NCMRModal 中使用的欄位
    不良原因大類?: string;
    不良原因細項?: string;
    判定結果?: string;
    檢驗人員姓名?: string;
    發現人員姓名?: string; // NCMRModal 中使用的欄位
}

export interface NCMRUpdateInput extends NCMRCreateInput {
    識別碼: number | null;
    狀態?: string; // DispositionModal 中使用的欄位
}

// Shipping Measurement Types
export interface ShippingMeasurementItem {
  lower_limit?: number | null;
  upper_limit?: number | null;
  value_min?: number | string | null;
  value_max?: number | string | null;
  value_single?: number | string | null;
  is_ng: boolean;
}

// key: group_num（字串），value: { [itemName]: ShippingMeasurementItem }
export type ShippingMeasurements = Record<string, Record<string, ShippingMeasurementItem>>;

// Shipping Types
export interface ShippingCreateInput {
    檢驗日期: string;
    檢驗人員ID?: number; // ShippingModal 使用人員名稱而非 ID
    檢驗人員姓名?: string;
    廠商ID?: number; // ShippingModal 使用廠商名稱而非 ID
    廠商中文名稱?: string;
    檢驗規格: string;
    材質: string;
    訂單號碼?: string;
    [key: string]: unknown;
}

export interface ShippingUpdateInput extends ShippingCreateInput {
    識別碼: number;
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
  id: number;
  date: string;
  material?: string;
  spec?: string;
  order_num?: string;
  group_count: number;
  inspector_id?: number;
  inspector_name?: string;
  vendor_id?: number;
  vendor_name?: string;
  is_ng: boolean;
  measurements: ShippingMeasurements;
  // 舊版中文欄位（後端回傳時仍包含，保留以相容過渡期）
  識別碼?: number;
  檢驗日期?: string;
  廠商中文名稱?: string;
  材質?: string;
  檢驗規格?: string;
  訂單號碼?: string;
  組數?: number;
  檢驗人員?: string | number;
  檢驗人員姓名?: string;
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
    [key: string]: unknown;
}

export interface CAPACreateInput {
    ncmr_id: number;
    業主姓名: string;
    判定結果?: string;
    [key: string]: unknown;
}

export interface CAPAUpdateInput extends CAPACreateInput {
    id: number;
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
    [key: string]: unknown;
}

export interface CARCreateInput {
    ncmr_id: number;
    業主姓名: string;
    [key: string]: unknown;
}

export interface CARUpdateInput extends CARCreateInput {
    id: number;
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

// Dashboard Stats Types
export type TrendDirection = 'up' | 'down' | 'stable';

// KPI 模組統計資料，trend 使用 string 相容 useDashboard hook 回傳的任意字串
export interface KpiModuleStats {
    current: number;
    previous?: number;
    pending: number;
    trend: string; // useDashboard hook 回傳 string，非嚴格限定 TrendDirection
    change_pct: number;
    ng_rate?: number | null;
    ng_count?: number;
}

export interface DashboardStats {
    shipping: KpiModuleStats;
    patrol: KpiModuleStats;
    ncmr: KpiModuleStats;
    rework: KpiModuleStats;
    capa: KpiModuleStats;
}

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

// ── CAPA 重設計（D0-D8）──────────────────────────────────────
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

// 不合格品處置明細（IATF 16949 §8.7）
export type DispositionType = '矯正重工' | '報廢' | '挑選全檢' | '讓步放行';

export interface NcmrDisposition {
    識別碼?: number;
    NCMR_ID?: number;
    處置類型: DispositionType;
    處置數量: number;
    處置人?: number | null;
    處置人姓名?: string;
    處置時間?: string;
    備註?: string | null;
    關聯重工單ID?: number | null;
    合格數?: number | null;
    不合格數?: number | null;
    是否超出客戶規格?: boolean;
    授權狀態?: '已取得' | '未取得' | null;
    授權文號?: string | null;
    授權有效期?: string | null;
    授權數量上限?: number | null;
    未授權放行理由?: string | null;
    是否風險項?: boolean;
}

export interface RiskRelease {
    NCMR單號: string;
    產品資訊: string;
    材質: string;
    廠商: string;
    處置數量: number;
    未授權放行理由: string;
    處置人姓名: string;
    處置時間: string;
}

// CQI-9 爐溫測試
export interface Furnace {
  識別碼: number;
  爐號: string;
  名稱: string;
  製程類型: string;
  TUS點數: number;
  SAT點數: number;
  TUS頻率_月: number;
  SAT頻率_月: number;
  TUS允許公差: string;
  SAT允許誤差: string;
  有效加熱區尺寸: string;
  儀器型式: string;
  CQI9等級: string;
  啟用狀態: boolean;
  備註: string;
}

export interface PyrometryTestRow {
  識別碼: number;
  爐號: string;
  測試類型: 'TUS' | 'SAT';
  季別: string;
  測試日期: string;
  是否合格: boolean;
  測試人員姓名: string;
}

export interface TusPoint {
  識別碼?: number;
  點位: string;
  熱電偶編號: string;
  頻道?: number | null;
  修正值: string | number | null;
  最高溫: string | number | null;
  最低溫: string | number | null;
  最大偏差?: string | number | null;
  是否合格?: boolean;
}

export interface SatReading {
  控制儀表讀值: string | number | null;
  校正測試讀值: string | number | null;
  差值?: string | number | null;
  偏差?: string | number | null;
  是否合格?: boolean;
}

export interface SatPoint {
  識別碼?: number;
  控溫區: string;
  頻道?: number | null;
  修正值: string | number | null;
  readings: SatReading[];
  差值?: string | number | null;
  偏差?: string | number | null;
  是否合格?: boolean;
}

export interface RecorderCalPoint {
  頻道: number;
  標準溫度: string | number;
  器差值: string | number;
}

export interface Recorder {
  識別碼: number;
  編號: string;
  校正日期: string | null;
  到期日: string | null;
  熱電偶補正值: string | number;
  啟用狀態: boolean;
  備註: string;
  校正點?: RecorderCalPoint[];
}

export interface ThermocoupleCalPoint {
  標準溫度: string | number;
  器差值: string | number;
}

export interface Thermocouple {
  識別碼: number;
  編號: string;
  型式: string;
  校正日期: string | null;
  到期日: string | null;
  啟用狀態: boolean;
  備註: string;
  校正點?: ThermocoupleCalPoint[];
}
