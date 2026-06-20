export interface ToleranceValidationResult {
  is_valid: boolean;
  violates: {
    item: string;
    value: number;
    min: number;
    max: number;
  }[];
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
  is_valid?: boolean;
  violates?: ToleranceValidationResult['violates'];
  success: boolean;
  found: boolean;
  tolerances: ToleranceItem[];
  message?: string;
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
  item?: string;
  position?: string;
  size_min?: number | null;
  size_max?: number | null;
  tol_min?: number | null;
  tol_max?: number | null;
  std?: number | null;
  unit?: string;
  remark?: string;
  測量項目?: string;
  測量位置?: string;
  尺寸下限?: number | null;
  尺寸上限?: number | null;
  公差下限?: number | null;
  公差上限?: number | null;
  標準值?: number | null;
  單位?: string;
  備註?: string;
}

export interface ToleranceCreateInput {
  建立日期?: string;
  材質: string;
  規格: string;
  廠商ID?: number | null;
  備註?: string;
  details: ToleranceDetailParams[];
}

export interface ToleranceUpdateInput extends ToleranceCreateInput {
  識別碼: number;
}
