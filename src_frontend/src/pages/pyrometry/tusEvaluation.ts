import type { TusPoint } from '../../types';
import { parseSatNumber } from './satEvaluation';

const round2 = (value: number) => Math.round(value * 100) / 100;

/**
 * 單一 TUS 量測點即時判定，邏輯與後端 pyrometry_calculations.evaluate_tus 一致：
 * 校正後溫度＝量測值＋修正值，取最高／最低溫相對設定溫度偏差中絕對值較大者，|偏差| ≤ 公差即合格。
 * 已排除、無溫度資料或設定溫度無效時回傳 null（不判定）。
 */
export const evaluateTusPoint = (point: TusPoint, setpointText: string, toleranceText: string) => {
  const setpoint = parseSatNumber(setpointText);
  if (point.已排除 || setpoint === null) return { maxDeviation: null, pass: null };

  const tolerance = parseSatNumber(toleranceText) ?? 0;
  const correction = parseSatNumber(point.修正值) ?? 0;
  const deviations = [point.最高溫, point.最低溫]
    .map(parseSatNumber)
    .filter((value): value is number => value !== null)
    .map(value => value + correction - setpoint);
  if (deviations.length === 0) return { maxDeviation: null, pass: null };

  const worst = deviations.reduce((a, b) => (Math.abs(b) > Math.abs(a) ? b : a));
  return { maxDeviation: round2(worst), pass: Math.abs(worst) <= tolerance };
};
