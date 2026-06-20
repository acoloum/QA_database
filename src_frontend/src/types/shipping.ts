// 出貨量測型別
export interface ShippingMeasurementItem {
  lower_limit?: number | null;
  upper_limit?: number | null;
  value_min?: number | string | null;
  value_max?: number | string | null;
  value_single?: number | string | null;
  is_ng: boolean;
}

// key 為 group_num（字串），value 為各量測項目
export type ShippingMeasurements = Record<string, Record<string, ShippingMeasurementItem>>;

// 出貨型別
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

