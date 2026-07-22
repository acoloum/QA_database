export interface MeasurementTolerance {
  lsl: number;
  usl: number;
}

/**
 * 這些項目量測值為 0 代表「未量測」（空白被存成 0），非真實量測：
 *   尺寸(外徑/內徑/厚度/長度)幾何上不可能為 0；硬度實測最小為 1.0，0 為未量測哨兵值。
 * 真圓度/同心度/真直度的 0 是理想值(真實好值)，不屬此集合。
 */
export const ZERO_AS_UNMEASURED_ITEMS = new Set(['外徑', '內徑', '厚度', '長度', '硬度', '韋伯氏硬度']);

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
  treatZeroAsUnmeasured = false,
) => {
  const parsed = parseShippingMeasurementNumber(value);
  if (parsed === null) return false;
  // 尺寸為 0 視為未量測，跳過（避免空白 0 造成假性超差）
  if (treatZeroAsUnmeasured && parsed === 0) return false;
  return parsed < tolerance.lsl || parsed > tolerance.usl;
};
