import type { ToleranceCreateInput } from '../../types';
import type { ToleranceDetailItem } from '../../hooks/useTolerance';

export interface ToleranceDetailRow {
  id: string;
  item: string;
  position: string;
  size_min: string;
  size_max: string;
  tol_min: string;
  tol_max: string;
  std: string;
  unit: string;
  remark: string;
}

export const createToleranceDetailRow = (id: string): ToleranceDetailRow => ({
  id,
  item: '',
  position: '',
  size_min: '',
  size_max: '',
  tol_min: '',
  tol_max: '',
  std: '',
  unit: 'mm',
  remark: '',
});

const numberToText = (value: number | null | undefined) => (value != null ? String(value) : '');

export const mapToleranceDetailToRow = (
  detail: ToleranceDetailItem,
  id: string,
): ToleranceDetailRow => ({
  id,
  item: detail.測量項目 ?? '',
  position: detail.測量位置 ?? '',
  size_min: numberToText(detail.尺寸下限),
  size_max: numberToText(detail.尺寸上限),
  tol_min: numberToText(detail.公差下限),
  tol_max: numberToText(detail.公差上限),
  std: numberToText(detail.標準值),
  unit: detail.單位 ?? 'mm',
  remark: detail.備註 ?? '',
});

const NUMERIC_FIELDS: Array<{ field: keyof ToleranceDetailRow; label: string }> = [
  { field: 'size_min', label: '尺寸下限' },
  { field: 'size_max', label: '尺寸上限' },
  { field: 'tol_min', label: '公差下限' },
  { field: 'tol_max', label: '公差上限' },
  { field: 'std', label: '標準值' },
];

const numberPattern = /^[+-]?\d+(\.\d+)?$/;

export const validateToleranceRows = (details: ToleranceDetailRow[]) => {
  const errors: Record<string, string> = {};

  details.forEach(row => {
    NUMERIC_FIELDS.forEach(({ field, label }) => {
      const value = row[field];
      if (value !== '' && !numberPattern.test(value)) {
        const itemLabel = row.item || '未命名明細';
        errors[`${row.id}:${field}`] = `「${itemLabel}」的${label}需為有效數字`;
      }
    });
  });

  return errors;
};

const toNumberOrNull = (value: string) => (value === '' ? null : parseFloat(value));

interface BuildTolerancePayloadParams {
  date: string;
  material: string;
  spec: string;
  vendorId: string;
  remark: string;
  details: ToleranceDetailRow[];
}

export const buildTolerancePayload = ({
  date,
  material,
  spec,
  vendorId,
  remark,
  details,
}: BuildTolerancePayloadParams): ToleranceCreateInput => ({
  建立日期: date,
  材質: material,
  規格: spec,
  廠商ID: vendorId ? parseInt(vendorId, 10) : null,
  備註: remark,
  details: details
    .filter(detail => detail.item)
    .map(detail => ({
      測量項目: detail.item,
      測量位置: detail.position,
      尺寸下限: toNumberOrNull(detail.size_min),
      尺寸上限: toNumberOrNull(detail.size_max),
      公差下限: toNumberOrNull(detail.tol_min),
      公差上限: toNumberOrNull(detail.tol_max),
      標準值: toNumberOrNull(detail.std),
      單位: detail.unit,
      備註: detail.remark,
    })),
});
