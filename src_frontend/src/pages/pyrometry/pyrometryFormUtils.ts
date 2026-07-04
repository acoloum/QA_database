import type { SatPoint, SatReading, TusPoint } from '../../types';
import { sortChannels } from '../../components/pyrometry/channelSort';

export type ChartData = { 時間: string[]; 數值: Record<string, number[]> };
export type ItemRow = { 工件料號: string; 生產批號: string; 內外徑尺寸: string; 支數: string };
export type ReportFieldsResponse = Record<string, string | number | boolean | ItemRow[] | null | undefined>;
export type PyrometryUploadDestination = 'recorder' | 'sat' | 'furnace';

const ITEM_ROW_KEYS: (keyof ItemRow)[] = ['工件料號', '生產批號', '內外徑尺寸', '支數'];

const isItemRow = (value: unknown): value is ItemRow => {
  if (!value || typeof value !== 'object') return false;
  const row = value as Record<keyof ItemRow, unknown>;
  return ITEM_ROW_KEYS.every(key => typeof row[key] === 'string');
};

export const splitReportFields = (raw: ReportFieldsResponse = {}) => {
  const itemRows = Array.isArray(raw.料號批次)
    ? raw.料號批次.filter(isItemRow)
    : [];
  const meta: Record<string, string> = {};
  Object.entries(raw).forEach(([key, value]) => {
    if (key === '料號批次' || value === null || value === undefined) return;
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      meta[key] = String(value);
    }
  });
  return { itemRows, meta };
};

export const emptyReading = (): SatReading => ({ 控制儀表讀值: '', 校正測試讀值: '' });
export const emptyItemRow = (): ItemRow => ({ 工件料號: '', 生產批號: '', 內外徑尺寸: '', 支數: '' });
export const emptyTusPoint = (ch?: number): TusPoint => ({
  點位: '',
  熱電偶編號: '',
  頻道: ch ?? null,
  修正值: '',
  最高溫: '',
  最低溫: '',
  已排除: false,
  排除原因: '',
});
export const emptySatPoint = (ch?: number): SatPoint => ({
  控溫區: '',
  頻道: ch ?? null,
  修正值: '',
  readings: Array.from({ length: 10 }, emptyReading),
  已排除: false,
  排除原因: '',
});

export const parseOptionalChannel = (value: string): number | null => {
  const text = value.trim();
  if (!text) return null;
  const parsed = Number(text);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 99 ? parsed : null;
};

export const parseRangeIndex = (value: string | null | undefined, fallback = 0): number => {
  const text = String(value ?? '').trim();
  if (!text) return fallback;
  const parsed = Number(text);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback;
};

export const parseActiveZone = (
  value: string | null | undefined,
  fallback = 0,
  maxIndex?: number,
): number => {
  const parsed = parseRangeIndex(value, fallback);
  if (maxIndex == null) return parsed;
  return parsed <= maxIndex ? parsed : fallback;
};

export const computeRangeStats = (
  數值: Record<string, number[]>,
  start: number,
  end: number,
): { 名稱: string; 最高溫: number; 最低溫: number }[] =>
  sortChannels(Object.keys(數值)).map(ch => {
    const slice = 數值[ch].slice(start, end + 1).filter((v): v is number => v !== null && v !== undefined);
    return {
      名稱: ch,
      最高溫: slice.length ? Math.max(...slice) : 0,
      最低溫: slice.length ? Math.min(...slice) : 0,
    };
  });

const roundTemperature = (value: number): string => String(Math.round(value * 100) / 100);

const chartValuesInRange = (values: number[] = [], start: number, end: number): number[] =>
  values.slice(start, end + 1).filter((v): v is number => v !== null && v !== undefined);

export const applyChartRangeToTusPoints = (
  points: TusPoint[],
  chartData: ChartData,
  start: number,
  end: number,
): TusPoint[] => {
  const stats = computeRangeStats(chartData.數值, start, end);
  return points.map((point, index) => {
    const channelStats = stats[index];
    return channelStats
      ? { ...point, 最高溫: String(channelStats.最高溫), 最低溫: String(channelStats.最低溫) }
      : point;
  });
};

export const applyChartRangeToSatReadings = (
  points: SatPoint[],
  chartData: ChartData,
  start: number,
  end: number,
  targetField: keyof SatReading,
): SatPoint[] => {
  const channels = sortChannels(Object.keys(chartData.數值));
  return points.map((point, index) => {
    const channel = channels[index];
    if (!channel) return point;
    const values = chartValuesInRange(chartData.數值[channel], start, end);
    if (!values.length) return point;
    const readings = values.map((value, readingIndex) => ({
      控制儀表讀值: targetField === '控制儀表讀值'
        ? roundTemperature(value)
        : point.readings[readingIndex]?.控制儀表讀值 ?? '',
      校正測試讀值: targetField === '校正測試讀值'
        ? roundTemperature(value)
        : point.readings[readingIndex]?.校正測試讀值 ?? '',
    }));
    return { ...point, readings };
  });
};

export const addSatReadingToPoint = (point: SatPoint): SatPoint => ({
  ...point,
  readings: [...point.readings, emptyReading()],
});

export const removeSatReadingFromPoint = (point: SatPoint, readingIndex: number): SatPoint => ({
  ...point,
  readings: point.readings.filter((_, index) => index !== readingIndex),
});

export const inheritReportFields = (
  currentMeta: Record<string, string>,
  currentRows: ItemRow[],
  inherited: ReportFieldsResponse,
) => {
  const { itemRows, meta } = splitReportFields(inherited);
  return {
    meta: { ...currentMeta, ...meta },
    itemRows: itemRows.length ? itemRows : currentRows,
  };
};

export const detectSoakStartIndex = (
  數值: Record<string, number[]>,
  setpoint: number,
  tolerance: number,
): number => {
  const channels = Object.values(數值);
  if (!channels.length) return 0;
  const length = channels[0].length;
  if (length === 0 || !Number.isFinite(setpoint) || !Number.isFinite(tolerance)) return 0;
  const upper = setpoint + tolerance;
  const lower = setpoint - tolerance;
  for (let i = length - 1; i >= 0; i--) {
    const anyOut = channels.some(vals => {
      const v = vals[i];
      return v == null || v < lower || v > upper;
    });
    if (anyOut) {
      const start = i + 1;
      // 穩定期至少需保留 2 個資料點才視為有效偵測，否則回退為整段資料
      return start <= length - 2 ? start : 0;
    }
  }
  return 0;
};

export const applyParsedPyrometryData = ({
  destination,
  parsedData,
  tusPoints,
  satPoints,
  setpoint,
  tolerance,
}: {
  destination: PyrometryUploadDestination;
  parsedData: ChartData;
  tusPoints: TusPoint[];
  satPoints: SatPoint[];
  setpoint: number;
  tolerance: number;
}) => {
  const chartData = { 時間: parsedData.時間, 數值: parsedData.數值 };
  const lastIndex = Math.max(chartData.時間.length - 1, 0);
  const soakStart = detectSoakStartIndex(chartData.數值, setpoint, tolerance);

  if (destination === 'recorder') {
    return {
      chartData,
      rangeStart: soakStart,
      rangeEnd: lastIndex,
      tusPoints: applyChartRangeToTusPoints(tusPoints, chartData, soakStart, lastIndex),
    };
  }

  if (destination === 'sat') {
    return {
      satChartData: chartData,
      satRangeStart: soakStart,
      satRangeEnd: lastIndex,
      satPoints: applyChartRangeToSatReadings(satPoints, chartData, soakStart, lastIndex, '校正測試讀值'),
    };
  }

  return {
    furnaceChartData: chartData,
    furnaceRangeStart: soakStart,
    furnaceRangeEnd: lastIndex,
    satPoints: applyChartRangeToSatReadings(satPoints, chartData, soakStart, lastIndex, '控制儀表讀值'),
  };
};
