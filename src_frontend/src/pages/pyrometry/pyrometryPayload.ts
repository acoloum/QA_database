import type { SatPoint, TusPoint } from '../../types';
import type { ChartData, ItemRow } from './pyrometryFormUtils';

export type PyrometryTestType = 'TUS' | 'SAT';

export interface BuildPyrometryPayloadInput {
  furnaceId: string;
  testType: PyrometryTestType;
  testDate: string;
  quarter: string;
  setpoint: string;
  tolerance: string;
  testerId: string;
  testInstrument: string;
  stdInstrument: string;
  calDueDate: string;
  note: string;
  tusPoints: TusPoint[];
  satPoints: SatPoint[];
  chartData: ChartData | null;
  rangeStart: number;
  rangeEnd: number;
  satChartData: ChartData | null;
  satRangeStart: number;
  satRangeEnd: number;
  furnaceChartData: ChartData | null;
  furnaceRangeStart: number;
  furnaceRangeEnd: number;
  reportMeta: Record<string, string>;
  itemRows: ItemRow[];
}

export interface PyrometryPayload {
  爐子ID: number;
  測試類型: PyrometryTestType;
  測試日期: string;
  季別: string;
  設定溫度: string;
  允許公差: string;
  測試人員: number | null;
  測試儀器編號: string;
  標準校正儀器編號: string;
  儀器校正到期日: string | null;
  備註: string;
  points: TusPoint[] | SatPoint[];
  曲線資料: Record<string, unknown> | null;
  報告欄位: Record<string, string | ItemRow[]>;
}

const parseRequiredPositiveId = (value: string, label: string) => {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`請選擇${label}`);
  }
  return parsed;
};

export const buildPyrometryPayload = ({
  furnaceId,
  testType,
  testDate,
  quarter,
  setpoint,
  tolerance,
  testerId,
  testInstrument,
  stdInstrument,
  calDueDate,
  note,
  tusPoints,
  satPoints,
  chartData,
  rangeStart,
  rangeEnd,
  satChartData,
  satRangeStart,
  satRangeEnd,
  furnaceChartData,
  furnaceRangeStart,
  furnaceRangeEnd,
  reportMeta,
  itemRows,
}: BuildPyrometryPayloadInput): PyrometryPayload => {
  const curveData = testType === 'TUS'
    ? (chartData ? {
        時間: chartData.時間,
        數值: chartData.數值,
        穩定開始: rangeStart,
        穩定結束: rangeEnd,
      } : null)
    : (satChartData ? {
        時間: satChartData.時間,
        數值: satChartData.數值,
        穩定開始: satRangeStart,
        穩定結束: satRangeEnd,
        爐體時間: furnaceChartData?.時間 || null,
        爐體數值: furnaceChartData?.數值 || null,
        爐體穩定開始: furnaceChartData ? furnaceRangeStart : null,
        爐體穩定結束: furnaceChartData ? furnaceRangeEnd : null,
      } : (furnaceChartData ? {
        爐體時間: furnaceChartData.時間,
        爐體數值: furnaceChartData.數值,
        爐體穩定開始: furnaceRangeStart,
        爐體穩定結束: furnaceRangeEnd,
      } : null));

  return {
    爐子ID: parseRequiredPositiveId(furnaceId, '爐子'),
    測試類型: testType,
    測試日期: testDate,
    季別: quarter,
    設定溫度: setpoint,
    允許公差: tolerance,
    測試人員: testerId ? parseRequiredPositiveId(testerId, '測試人員') : null,
    測試儀器編號: testInstrument,
    標準校正儀器編號: stdInstrument,
    儀器校正到期日: calDueDate || null,
    備註: note,
    points: testType === 'TUS' ? tusPoints : satPoints,
    曲線資料: curveData,
    報告欄位: { ...reportMeta, 料號批次: itemRows },
  };
};
