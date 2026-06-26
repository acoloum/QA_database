export interface MeasurementTolerance {
  lsl: number;
  usl: number;
}

export const parseShippingMeasurementNumber = (value: number | string | null | undefined) => {
  if (value == null) return null;
  const text = typeof value === 'string' ? value.trim() : value;
  if (text === '') return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
};

export const isMeasurementOutOfTolerance = (
  value: number | string | null | undefined,
  tolerance: MeasurementTolerance,
) => {
  const parsed = parseShippingMeasurementNumber(value);
  return parsed !== null && (parsed < tolerance.lsl || parsed > tolerance.usl);
};
