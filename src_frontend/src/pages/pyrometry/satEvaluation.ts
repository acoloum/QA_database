import type { SatPoint, SatReading } from '../../types';

const round2 = (value: number) => Math.round(value * 100) / 100;

export const parseSatNumber = (value: unknown) => {
  const text = String(value ?? '').trim();
  if (!/^[+-]?\d+(?:\.\d+)?$/.test(text)) return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
};

export const calculateSatReadingDisplay = ({
  reading,
  correction,
  tolerance,
}: {
  reading: SatReading;
  correction: number;
  tolerance: number;
}) => {
  const control = parseSatNumber(reading.控制儀表讀值);
  const test = parseSatNumber(reading.校正測試讀值);
  if (control === null || test === null) {
    return { diff: null, deviation: null, pass: null };
  }

  const diff = round2(test - control);
  const deviation = round2(diff + correction);
  return { diff, deviation, pass: Math.abs(deviation) <= tolerance };
};

export const evaluateSatPoint = (point: SatPoint, toleranceText: string) => {
  const tolerance = parseSatNumber(toleranceText) ?? 0;
  const correction = parseSatNumber(point.修正值) ?? 0;
  const hasData = point.readings.some(
    reading => reading.校正測試讀值 !== '' && reading.校正測試讀值 !== null,
  );
  const results = point.readings.map(reading =>
    calculateSatReadingDisplay({ reading, correction, tolerance }),
  );
  const validResults = results.filter(result => result.pass !== null);
  const passCount = validResults.filter(result => result.pass).length;

  return {
    validCount: validResults.length,
    passCount,
    hasData,
    allPass: hasData && validResults.length === point.readings.length && passCount === validResults.length,
  };
};
