import type { SatPoint, TusPoint } from '../../types';
import {
  emptyItemRow,
  emptyReading,
  splitReportFields,
  type ChartData,
  type ItemRow,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';

type CurveData = {
  時間?: string[];
  數值?: Record<string, number[]>;
  穩定開始?: number;
  穩定結束?: number;
  爐體時間?: string[];
  爐體數值?: Record<string, number[]>;
  爐體穩定開始?: number;
  爐體穩定結束?: number;
};

type MainData = {
  爐子ID?: string | number | null;
  測試類型?: 'TUS' | 'SAT';
  測試日期?: string | null;
  季別?: string | null;
  設定溫度?: string | number | null;
  允許公差?: string | number | null;
  測試人員?: string | number | null;
  測試儀器編號?: string | null;
  標準校正儀器編號?: string | null;
  儀器校正到期日?: string | null;
  備註?: string | null;
};

export type PyrometryEditData = {
  main?: MainData;
  tus_points?: TusPoint[];
  sat_points?: SatPoint[];
  曲線資料?: CurveData | null;
  報告欄位?: ReportFieldsResponse;
};

export type PyrometryEditFormState = {
  furnaceId: string;
  testType: 'TUS' | 'SAT';
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
  activeZone: number;
  chartData: ChartData | null;
  rangeStart: number;
  rangeEnd: number;
  satChartData: ChartData | null;
  satRangeStart: number;
  satRangeEnd: number;
  furnaceChartData: ChartData | null;
  furnaceRangeStart: number;
  furnaceRangeEnd: number;
  itemRows: ItemRow[];
  reportMeta: Record<string, string>;
};

const toText = (value: string | number | null | undefined) => value == null ? '' : String(value);

const lastIndex = (items?: unknown[]) => Math.max((items?.length ?? 1) - 1, 0);

export const buildPyrometryEditFormState = (editData: PyrometryEditData): PyrometryEditFormState => {
  const main = editData.main ?? {};
  const curve = editData.曲線資料;
  const testType = main.測試類型 ?? 'TUS';
  const { itemRows, meta } = splitReportFields(editData.報告欄位 || {});

  const state: PyrometryEditFormState = {
    furnaceId: toText(main.爐子ID),
    testType,
    testDate: toText(main.測試日期),
    quarter: toText(main.季別),
    setpoint: toText(main.設定溫度),
    tolerance: toText(main.允許公差),
    testerId: main.測試人員 ? String(main.測試人員) : '',
    testInstrument: toText(main.測試儀器編號),
    stdInstrument: toText(main.標準校正儀器編號),
    calDueDate: toText(main.儀器校正到期日),
    note: toText(main.備註),
    tusPoints: (editData.tus_points ?? []).map((point, index) => ({
      ...point,
      點位: /^P\d+$/.test(point.點位 || '') ? `TUS-${index + 1}` : (point.點位 || `TUS-${index + 1}`),
      頻道: point.頻道 ?? (index + 1),
    })),
    satPoints: (editData.sat_points ?? []).map((point, index) => ({
      ...point,
      頻道: point.頻道 ?? (13 + index),
      readings: point.readings?.length ? point.readings : [emptyReading()],
    })),
    activeZone: 0,
    chartData: null,
    rangeStart: 0,
    rangeEnd: 0,
    satChartData: null,
    satRangeStart: 0,
    satRangeEnd: 0,
    furnaceChartData: null,
    furnaceRangeStart: 0,
    furnaceRangeEnd: 0,
    itemRows: itemRows.length ? itemRows : [emptyItemRow()],
    reportMeta: meta,
  };

  if (curve?.時間 && curve.數值) {
    const chart = { 時間: curve.時間, 數值: curve.數值 };
    if (testType === 'TUS') {
      state.chartData = chart;
      state.rangeStart = curve.穩定開始 ?? 0;
      state.rangeEnd = curve.穩定結束 ?? lastIndex(curve.時間);
    } else {
      state.satChartData = chart;
      state.satRangeStart = curve.穩定開始 ?? 0;
      state.satRangeEnd = curve.穩定結束 ?? lastIndex(curve.時間);
    }
  }

  if (curve?.爐體數值) {
    const furnaceTime = curve.爐體時間 || curve.時間 || [];
    state.furnaceChartData = { 時間: furnaceTime, 數值: curve.爐體數值 };
    state.furnaceRangeStart = curve.爐體穩定開始 ?? 0;
    state.furnaceRangeEnd = curve.爐體穩定結束 ?? lastIndex(furnaceTime);
  }

  return state;
};
