// ===== 機械性質檢驗 =====
export type MechItem = 'EC值' | '硬度' | '抗拉強度' | '降伏強度' | '伸長率';
export type MechLocation = '爐門' | '爐頂';
export type MechanicalJudgementStatus = 'NG' | 'OK' | 'NO_SPEC' | 'INCOMPLETE';

export interface MechanicalTraceNumber {
  識別碼?: number;
  序號: number;
  編號: string;
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
  下限?: number | null;
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
  T4溫度時間: string | null;
  T6溫度時間: string | null;
  是否NG: boolean;
  判定狀態: MechanicalJudgementStatus;
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
  batches: MechanicalBatch[];
  measurements: MechanicalMeasurement[];
}

export interface MechanicalTestPayload {
  產品尺寸: string;
  材質: string;
  廠商ID?: number | null;
  測試日期?: string | null;
  T4溫度時間?: string;
  T6溫度時間?: string;
  備註?: string;
  batches: MechanicalBatch[];
  measurements: MechanicalMeasurement[];
}
