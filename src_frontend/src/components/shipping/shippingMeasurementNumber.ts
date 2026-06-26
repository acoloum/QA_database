export interface MeasurementTolerance {
  lsl: number;
  usl: number;
}

export const parseShippingMeasurementNumber = (value: number | string | null | undefined) => {
  if (value == null || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export const isMeasurementOutOfTolerance = (
  value: number | string | null | undefined,
  tolerance: MeasurementTolerance,
) => {
  const parsed = parseShippingMeasurementNumber(value);
  return parsed !== null && (parsed < tolerance.lsl || parsed > tolerance.usl);
};
