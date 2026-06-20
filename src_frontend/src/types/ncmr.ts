// NCMR 型別
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
    建立日期?: string;
    發現日期?: string;
    來源?: string;
    廠商?: string;
    材質?: string;
    產品資訊?: string;
    產品數量?: number;
    批號?: string;
    不合格數量?: number | string;
    不良描述?: string;
    不良原因大類?: string;
    不良原因細項?: string;
    發現人員姓名?: string;
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

