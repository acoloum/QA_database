export type * from './common';
export type * from './patrol';
export type * from './ncmr';
export type * from './shipping';
export type * from './ca';
export type * from './dashboard';
export type * from './attachment';
export type * from './task';
export type * from './complaint';
export type * from './capa';
export type * from './pyrometry';
export type * from './rework';
export type * from './tolerance';
export type * from './spc';

// ===== 機械性質檢驗 =====
export type MechItem = 'EC值' | '硬度' | '抗拉強度' | '降伏強度' | '伸長率';
export type MechLocation = '爐門' | '爐頂';

export interface MechanicalBatch {
  序號: number;
  擠製編號: string;
  爐具編號: string;
}

export interface MechanicalMeasurement {
  量測項目: MechItem;
  測量位置: MechLocation;
  取樣序: number;
  量測值: number | null;
  下限?: number | null;
  是否超差?: boolean;
}

export interface MechanicalTestListItem {
  識別碼: number;
  產品尺寸: string;
  材質: string;
  測試日期: string | null;
  擠製編號: string;
  T4溫度時間: string;
  T6溫度時間: string;
  是否NG: boolean;
  備註: string;
}

export interface MechanicalTestDetail {
  main: {
    識別碼: number;
    產品尺寸: string;
    材質: string;
    廠商ID: number | null;
    測試日期: string | null;
    T4溫度時間: string;
    T6溫度時間: string;
    備註: string;
    是否NG: boolean;
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
