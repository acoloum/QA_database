import type { SatPoint, TusPoint } from '../../types';
import type { ChartData, ItemRow } from './pyrometryFormUtils';

export type PyrometryTestType = 'TUS' | 'SAT';

export interface BuildPyrometryPayloadInput {
  furnaceId: string;
  testType: PyrometryTestType;
  testDate: string;
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

export const buildPyrometryPayload = ({
  furnaceId,
  testType,
  testDate,
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
}: BuildPyrometryPayloadInput) => {
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
    爐子ID: Number(furnaceId),
    測試類型: testType,
    測試日期: testDate,
    設定溫度: setpoint,
    允許公差: tolerance,
    測試人員: testerId ? Number(testerId) : null,
    測試儀器編號: testInstrument,
    標準校正儀器編號: stdInstrument,
    儀器校正到期日: calDueDate || null,
    備註: note,
    points: testType === 'TUS' ? tusPoints : satPoints,
    曲線資料: curveData,
    報告欄位: { ...reportMeta, 料號批次: itemRows },
  };
};
