import type {
  CalibrationTemplatePoint,
  CalibrationTemplatePointInput,
} from '../../types/calibration';

export interface TemplatePointDraft {
  point_code: string;
  point_order: number;
  measurement_mode: string;
  nominal_value: string;
  unit: string;
  reference_input_mode: 'certified_value' | 'paired_reading';
  required_repetitions: string;
  error_lower_limit: string;
  error_upper_limit: string;
  evaluation_basis: 'all_readings' | 'mean_error';
  repeatability_rule: 'none' | 'range' | 'stddev';
  repeatability_limit: string;
  qualification_scope_code: string;
  qualification_range_start: string;
  qualification_range_end: string;
  uncertainty_required: boolean;
  required: boolean;
  instruction: string;
}

export const emptyTemplatePoint = (pointOrder: number): TemplatePointDraft => ({
  point_code: '',
  point_order: pointOrder,
  measurement_mode: '',
  nominal_value: '',
  unit: '',
  reference_input_mode: 'certified_value',
  required_repetitions: '3',
  error_lower_limit: '',
  error_upper_limit: '',
  evaluation_basis: 'all_readings',
  repeatability_rule: 'none',
  repeatability_limit: '',
  qualification_scope_code: '',
  qualification_range_start: '',
  qualification_range_end: '',
  uncertainty_required: false,
  required: true,
  instruction: '',
});

export const pointToDraft = (
  point: CalibrationTemplatePoint,
): TemplatePointDraft => ({
  point_code: point.point_code,
  point_order: point.point_order,
  measurement_mode: point.measurement_mode,
  nominal_value: point.nominal_value ?? '',
  unit: point.unit,
  reference_input_mode: point.reference_input_mode,
  required_repetitions: String(point.required_repetitions),
  error_lower_limit: point.error_lower_limit ?? '',
  error_upper_limit: point.error_upper_limit ?? '',
  evaluation_basis: point.evaluation_basis === 'mean_error'
    ? 'mean_error'
    : 'all_readings',
  repeatability_rule: (
    ['none', 'range', 'stddev'].includes(point.repeatability_rule)
      ? point.repeatability_rule
      : 'none'
  ) as TemplatePointDraft['repeatability_rule'],
  repeatability_limit: point.repeatability_limit ?? '',
  qualification_scope_code: point.qualification_scope_code ?? '',
  qualification_range_start: point.qualification_range_start ?? '',
  qualification_range_end: point.qualification_range_end ?? '',
  uncertainty_required: point.uncertainty_required,
  required: point.required,
  instruction: point.instruction ?? '',
});

const decimalOrNull = (value: string) => (
  value.trim() === '' ? null : value.trim()
);

const isDecimal = (value: string) => (
  value.trim() !== '' && Number.isFinite(Number(value))
);

export const validateTemplatePoints = (
  points: TemplatePointDraft[],
): string | null => {
  const codes = new Set<string>();
  for (const [index, point] of points.entries()) {
    const prefix = `校正點 ${index + 1}`;
    if (!point.point_code.trim()) return `${prefix}：校正點代碼為必填`;
    if (codes.has(point.point_code.trim())) return '校正點代碼不可重複';
    codes.add(point.point_code.trim());
    if (!point.measurement_mode.trim()) return `${prefix}：量測模式為必填`;
    if (!point.unit.trim()) return `${prefix}：單位為必填`;
    if (
      point.repeatability_rule === 'range'
      && !point.repeatability_limit.trim()
    ) return `${prefix}：極差上限為必填`;
    if (
      point.repeatability_rule === 'stddev'
      && !point.repeatability_limit.trim()
    ) return `${prefix}：標準差上限為必填`;
    if (!isDecimal(point.nominal_value)) return `${prefix}：名目值必須是數值`;
    if (!/^[1-9]\d*$/.test(point.required_repetitions)) {
      return `${prefix}：重複次數必須是正整數`;
    }
    if (!point.error_lower_limit.trim() && !point.error_upper_limit.trim()) {
      return `${prefix}：至少填寫一個誤差界限`;
    }
    if (
      point.error_lower_limit.trim()
      && !isDecimal(point.error_lower_limit)
    ) return `${prefix}：誤差下限必須是數值`;
    if (
      point.error_upper_limit.trim()
      && !isDecimal(point.error_upper_limit)
    ) return `${prefix}：誤差上限必須是數值`;
    if (
      point.error_lower_limit.trim()
      && point.error_upper_limit.trim()
      && Number(point.error_lower_limit) > Number(point.error_upper_limit)
    ) return `${prefix}：誤差下限不得大於上限`;
    if (
      point.repeatability_rule !== 'none'
      && (
        !isDecimal(point.repeatability_limit)
        || Number(point.repeatability_limit) < 0
      )
    ) return `${prefix}：重複性上限必須是非負數值`;
    if (
      Boolean(point.qualification_range_start.trim())
      !== Boolean(point.qualification_range_end.trim())
    ) return `${prefix}：資格範圍起點與終點必須同時填寫`;
  }
  return null;
};

export const pointDraftToInput = (
  point: TemplatePointDraft,
): CalibrationTemplatePointInput => ({
  point_order: point.point_order,
  point_code: point.point_code.trim(),
  measurement_mode: point.measurement_mode.trim(),
  nominal_value: decimalOrNull(point.nominal_value),
  unit: point.unit.trim(),
  reference_input_mode: point.reference_input_mode,
  required_repetitions: Number(point.required_repetitions),
  error_lower_limit: decimalOrNull(point.error_lower_limit),
  error_upper_limit: decimalOrNull(point.error_upper_limit),
  evaluation_basis: point.evaluation_basis,
  repeatability_rule: point.repeatability_rule,
  repeatability_limit: point.repeatability_rule === 'none'
    ? null
    : decimalOrNull(point.repeatability_limit),
  qualification_scope_code: point.qualification_scope_code.trim() || null,
  qualification_range_start: decimalOrNull(point.qualification_range_start),
  qualification_range_end: decimalOrNull(point.qualification_range_end),
  uncertainty_required: point.uncertainty_required,
  required: point.required,
  instruction: point.instruction.trim() || null,
});
