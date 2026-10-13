// ===== 機械性質檢驗 =====
export type MechItem =
  | 'EC值'
  | '硬度'
  | '韋伯氏硬度'
  | '真直度'
  | '抗拉強度'
  | '降伏強度'
  | '伸長率';
export type MechLocation = '爐門' | '爐頂';
export type MechanicalJudgementStatus = 'NG' | 'OK' | 'NO_SPEC' | 'INCOMPLETE';

export interface MechanicalTraceNumber {
  識別碼?: number;
  序號: number;
  編號: string;
}

/** 可標記免測的項目；韋伯氏硬度／真直度為選填項目，不納入免測機制。 */
export type MechWaivableItem = Exclude<MechItem, 'EC值' | '韋伯氏硬度' | '真直度'>;

/** 免測項目：設備故障等原因無法量測時標記，該項目不列入完成判定。 */
export interface MechanicalWaivedItem {
  項目: MechWaivableItem;
  原因: string;
}

/** @deprecated 僅供舊 detail response 相容，新增前端不得使用。 */
export interface MechanicalBatch {
  序號: number;
  擠製編號: string | null;
  爐具編號: string | null;
}

export interface MechanicalMeasurement {
  量測項目: MechItem;
  測量位置: MechLocation;
  取樣序: number;
  量測值: number | null;
  /** 判定邊依項目而定：力學特性與硬度受下限管制，真直度受上限管制。 */
  下限?: number | null;
  上限?: number | null;
  是否超差?: boolean;
  排除統計?: boolean;
  排除原因?: string | null;
  排除者ID?: number | null;
  排除時間?: string | null;
}

export interface MechanicalTestListItem {
  識別碼: number;
  產品尺寸: string;
  材質: string;
  測試日期: string | null;
  擠製編號: string;
  T4爐號: string;
  T4溫度時間: string | null;
  T6溫度時間: string | null;
  是否NG: boolean;
  判定狀態: MechanicalJudgementStatus;
  免測?: string;
  備註: string | null;
}

export interface MechanicalTestDetail {
  main: {
    識別碼: number;
    產品尺寸: string;
    材質: string;
    廠商ID: number | null;
    測試日期: string | null;
    T4溫度時間: string | null;
    T6溫度時間: string | null;
    備註: string | null;
    是否NG: boolean;
    判定狀態: MechanicalJudgementStatus;
  };
  extrusion_numbers: MechanicalTraceNumber[];
  t4_furnace_numbers: MechanicalTraceNumber[];
  /** @deprecated 舊前端相容欄位。 */
  batches?: MechanicalBatch[];
  measurements: MechanicalMeasurement[];
  waived_items?: MechanicalWaivedItem[];
}

export interface MechanicalTestPayload {
  產品尺寸: string;
  材質: string;
  廠商ID?: number | null;
  測試日期?: string | null;
  T4溫度時間?: string;
  T6溫度時間?: string;
  備註?: string;
  extrusion_numbers: MechanicalTraceNumber[];
  t4_furnace_numbers: MechanicalTraceNumber[];
  measurements: MechanicalMeasurement[];
  waived_items: MechanicalWaivedItem[];
}

/** 疑似異常值會判定的項目（與 SPC 分析範圍一致） */
export type MechSuspectItem = '硬度' | '抗拉強度' | '降伏強度' | '伸長率';

/** 疑似異常量測值：同項目同材質 5 倍 IQR 以外或 0／負值 */
export interface MechanicalSuspectMeasurement {
  識別碼: number;
  檢驗ID: number;
  測試日期: string | null;
  材質: string;
  產品尺寸: string;
  量測項目: MechSuspectItem;
  測量位置: MechLocation;
  取樣序: number;
  量測值: number;
  /** 同組資料不足（少於最低筆數）時不估計範圍，以下三欄為 null */
  同組中位數: number | null;
  正常下界: number | null;
  正常上界: number | null;
  同組筆數: number;
  同爐次其他值: {
    測量位置: MechLocation;
    取樣序: number;
    量測值: number;
    排除統計: boolean;
  }[];
  提示: string;
  排除統計: boolean;
  排除原因: string | null;
  排除時間: string | null;
}
