import type { MachineStudyFilters, MachineStudyOptions } from '../../../hooks/useSpcStudies';

export interface MachineConditionInput {
  m_id: string;
  mat: string;
  spec: string;
  item: string;
  pos: string;
  conditions_confirmed: boolean;
  condition_reason: string;
}

export interface MachineStudyRequest {
  filters: MachineStudyFilters;
  options: MachineStudyOptions;
}

const trim = (value: string) => value.trim();
const validMachineId = (value: string) => /^[1-9]\d*$/.test(value);
const validReason = (value: string) => trim(value).length >= 2 && trim(value).length <= 500;

export const hasFixedMachineStream = (value: MachineConditionInput) => validMachineId(value.m_id)
  && [value.mat, value.spec, value.item, value.pos].every(item => Boolean(trim(item)));

export const hasValidMachineConditions = (value: MachineConditionInput) =>
  value.conditions_confirmed && validReason(value.condition_reason);

/** 同時供初次分析與重建候選使用，避免把空白機台轉成 0。 */
export const buildMachineStudyRequest = (value: MachineConditionInput): MachineStudyRequest | null => {
  if (!hasFixedMachineStream(value) || !hasValidMachineConditions(value)) return null;
  return {
    filters: { m_id: Number(value.m_id), mat: trim(value.mat), spec: trim(value.spec), item: trim(value.item), pos: trim(value.pos) },
    options: { conditions_confirmed: true, condition_reason: trim(value.condition_reason) },
  };
};
