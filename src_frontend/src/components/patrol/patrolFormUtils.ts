import type { PatrolCreateInput, PatrolUpdateInput } from '../../types';
import type { ExtrusionToleranceCheckResult } from '../../hooks/useExtrusionTolerance';
import { analyzeWECO, analyzeRChartWECO } from '../../utils/spcAnalysis';

export interface PatrolDetailInput {
  group: string;
  item: string;
  pos: string;
  min: string;
  max: string;
}

export type PatrolTolerance = NonNullable<ExtrusionToleranceCheckResult['tolerances']>[number];

export const getPatrolDetailValue = (
  details: PatrolDetailInput[],
  group: string,
  pos: string,
  item: string,
  type: 'min' | 'max',
) => {
  const detail = details.find(d => d.group === group && d.pos === pos && d.item === item);
  return detail ? detail[type] : '';
};

export const calcPatrolLimits = (
  tolerance: Pick<PatrolTolerance, '尺寸下限' | '尺寸上限' | '公差下限' | '公差上限' | '標準值'>,
  item: string | undefined,
  specStdValues: Record<string, number>,
) => {
  if (tolerance.尺寸下限 != null || tolerance.尺寸上限 != null) {
    return { lsl: tolerance.尺寸下限 ?? null, usl: tolerance.尺寸上限 ?? null };
  }

  const standardValue = tolerance.標準值 ?? (item != null ? (specStdValues[item] ?? null) : null);
  if (standardValue != null) {
    return {
      lsl: tolerance.公差下限 != null ? standardValue - Math.abs(tolerance.公差下限) : null,
      usl: tolerance.公差上限 != null ? standardValue + Math.abs(tolerance.公差上限) : null,
    };
  }

  return { lsl: null, usl: null };
};

interface PatrolNgParams {
  details: PatrolDetailInput[];
  tolerances: PatrolTolerance[];
  specStdValues: Record<string, number>;
}

interface PatrolCellNgParams extends PatrolNgParams {
  group: string;
  pos: string;
  item: string;
  type: 'min' | 'max';
}

export const isPatrolCellNG = ({
  details,
  tolerances,
  specStdValues,
  group,
  pos,
  item,
  type,
}: PatrolCellNgParams): boolean => {
  const tolerance = tolerances.find(t => t.項目 === item);
  if (!tolerance) return false;

  const valueText = getPatrolDetailValue(details, group, pos, item, type);
  if (valueText === '') return false;

  const value = parsePatrolMeasurement(valueText);
  if (value === null) return false;
  const { lsl, usl } = calcPatrolLimits(tolerance, item, specStdValues);
  if (lsl != null && value < lsl) return true;
  if (usl != null && value > usl) return true;
  return false;
};

interface PatrolConcentricityNgParams extends PatrolNgParams {
  group: string;
  pos: string;
}

export const isPatrolConcentricityNG = ({
  details,
  tolerances,
  specStdValues,
  group,
  pos,
}: PatrolConcentricityNgParams): boolean => {
  const tolerance = tolerances.find(t => t.項目 === '同心度');
  if (!tolerance) return false;

  const minText = getPatrolDetailValue(details, group, pos, '厚度', 'min');
  const maxText = getPatrolDetailValue(details, group, pos, '厚度', 'max');
  if (minText === '' || maxText === '') return false;

  const minValue = parsePatrolMeasurement(minText);
  const maxValue = parsePatrolMeasurement(maxText);
  if (minValue === null || maxValue === null) return false;

  const concentricity = maxValue - minValue;
  const { lsl, usl } = calcPatrolLimits(tolerance, '同心度', specStdValues);
  const effectiveLsl = lsl ?? (tolerance.公差下限 != null ? tolerance.公差下限 : null);
  const effectiveUsl = usl ?? (tolerance.公差上限 != null ? tolerance.公差上限 : null);

  if (effectiveLsl != null && concentricity < effectiveLsl) return true;
  if (effectiveUsl != null && concentricity > effectiveUsl) return true;
  return false;
};

interface BuildPatrolPayloadParams {
  editId: number | null;
  date: string;
  machine: string;
  operator: string;
  inspector: string;
  customer: string;
  material: string;
  batch: string;
  spec: string;
  details: PatrolDetailInput[];
}

export const getValidPatrolDetails = (details: PatrolDetailInput[]) =>
  details
    .filter(detail => detail.min !== '' || detail.max !== '')
    .map(detail => ({
      group: detail.group,
      item: detail.item,
      pos: detail.pos,
      min: parsePatrolMeasurement(detail.min),
      max: parsePatrolMeasurement(detail.max),
    }));

export const parsePatrolMeasurement = (value: string) => {
  if (value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export const buildPatrolPayload = ({
  editId,
  date,
  machine,
  operator,
  inspector,
  customer,
  material,
  batch,
  spec,
  details,
}: BuildPatrolPayloadParams): PatrolCreateInput & { id: number | null } => ({
  id: editId,
  檢驗日期: date,
  機台: machine,
  主機手: operator,
  客戶名稱: customer,
  材質: material,
  原料批號: batch,
  擠壓規格: spec,
  檢驗人員: inspector,
  details: getValidPatrolDetails(details),
});

export const buildPatrolUpdatePayload = (params: BuildPatrolPayloadParams & { editId: number }): PatrolUpdateInput => {
  const payload = buildPatrolPayload(params);
  return {
    ...payload,
    id: params.editId,
  };
};

const GROUP_LABELS = (count: number) => Array.from({ length: count }, (_, i) => `第${i + 1}組`);

// 修正浮點數減法誤差（如 85.2 - 84.8 會得到 0.4000000000000057），量測值僅需保留至微米等級精度
const roundMeasurement = (value: number): number => Math.round(value * 1e6) / 1e6;

interface BuildLiveGroupSeriesParams {
  recentValues: { min: number; max: number }[];
  details: PatrolDetailInput[];
  pos: string;
  item: string;
  groupCount: number;
}

export const buildLiveGroupSeries = ({
  recentValues, details, pos, item, groupCount,
}: BuildLiveGroupSeriesParams): { means: number[]; ranges: number[] } => {
  const history = recentValues.map(({ min, max }) => ({ min, max }));

  const currentGroups = GROUP_LABELS(groupCount)
    .map(group => {
      const minText = getPatrolDetailValue(details, group, pos, item, 'min');
      const maxText = getPatrolDetailValue(details, group, pos, item, 'max');
      if (minText === '' || maxText === '') return null;
      const min = parsePatrolMeasurement(minText);
      const max = parsePatrolMeasurement(maxText);
      if (min === null || max === null) return null;
      return { min, max };
    })
    .filter((pair): pair is { min: number; max: number } => pair !== null);

  const combined = [...history, ...currentGroups];
  return {
    means: combined.map(({ min, max }) => roundMeasurement((min + max) / 2)),
    ranges: combined.map(({ min, max }) => roundMeasurement(Math.abs(max - min))),
  };
};

export interface PatrolLiveViolation {
  chartKind: 'location' | 'variation';
  label: string;
  hint: string;
}

const LOCATION_HINTS: Record<string, string> = {
  'Rule 1: 超出控制限': '單點急劇偏移，先重量一次確認非量測失誤；屬實則檢查機頭壓力/料溫瞬間波動',
  'Rule 2: 連續9點同側': '製程中心已偏移，非單純波動，建議依 5M（人機料法環）排查後調整模具定位',
  'Rule 3: 連續6點趨勢': '持續漂移，典型成因是模具磨耗或螺桿轉速緩慢飄移，建議檢查/微調模具間隙與牽引速度',
};

const VARIATION_HINT = '量測值波動變大，較可能是設備穩定度或原料問題，非模具位置問題';

interface EvaluatePatrolLiveStabilityParams {
  means: number[];
  ranges: number[];
  xCl: number;
  xUcl: number;
  xLcl: number;
  rCl: number;
  rUcl: number;
  rLcl: number;
}

export const evaluatePatrolLiveStability = ({
  means, ranges, xCl, xUcl, xLcl, rCl, rUcl, rLcl: _rLcl,
}: EvaluatePatrolLiveStabilityParams): PatrolLiveViolation | null => {
  if (means.length === 0) return null;
  const lastIndex = means.length - 1;
  const labels = means.map((_, i) => String(i));

  const location = analyzeWECO(means, xCl, xUcl, xLcl, labels);
  const lastLocationViolation = location.violations.find(v => v.label === labels[lastIndex]);
  if (lastLocationViolation) {
    const reason = lastLocationViolation.reasons[0];
    return {
      chartKind: 'location',
      label: reason,
      hint: LOCATION_HINTS[reason] ?? LOCATION_HINTS['Rule 1: 超出控制限'],
    };
  }

  const variation = analyzeRChartWECO(ranges, rCl, rUcl, labels);
  const lastVariationViolation = variation.violations.find(v => v.label === labels[lastIndex]);
  if (lastVariationViolation) {
    return {
      chartKind: 'variation',
      label: lastVariationViolation.reasons[0],
      hint: VARIATION_HINT,
    };
  }

  return null;
};
