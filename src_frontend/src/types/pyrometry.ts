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
