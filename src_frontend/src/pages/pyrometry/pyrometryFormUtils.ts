import type { SatPoint, SatReading, TusPoint } from '../../types';

export type ChartData = { 時間: string[]; 數值: Record<string, number[]> };
export type ItemRow = { 工件料號: string; 生產批號: string; 內外徑尺寸: string; 支數: string };
export type ReportFieldsResponse = Record<string, string | number | boolean | ItemRow[] | null | undefined>;

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
});
export const emptySatPoint = (ch?: number): SatPoint => ({
  控溫區: '',
  頻道: ch ?? null,
  修正值: '',
  readings: Array.from({ length: 10 }, emptyReading),
});

export const computeRangeStats = (
  數值: Record<string, number[]>,
  start: number,
  end: number,
): { 名稱: string; 最高溫: number; 最低溫: number }[] =>
  Object.keys(數值).map(ch => {
    const slice = 數值[ch].slice(start, end + 1).filter((v): v is number => v !== null && v !== undefined);
    return {
      名稱: ch,
      最高溫: slice.length ? Math.max(...slice) : 0,
      最低溫: slice.length ? Math.min(...slice) : 0,
    };
  });
