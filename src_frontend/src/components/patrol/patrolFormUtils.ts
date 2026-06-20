import type { PatrolCreateInput } from '../../types';
import type { ExtrusionToleranceCheckResult } from '../../hooks/useExtrusionTolerance';

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

  const value = parseFloat(valueText);
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

  const concentricity = parseFloat(maxText) - parseFloat(minText);
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
      min: detail.min === '' ? null : parseFloat(detail.min),
      max: detail.max === '' ? null : parseFloat(detail.max),
    }));

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
