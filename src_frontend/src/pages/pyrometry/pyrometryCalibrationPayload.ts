import type { Recorder, RecorderCalPoint, Thermocouple } from '../../types';

export const STD_TEMPS = [100, 200, 300, 400, 500, 600];
export const CHANNELS = Array.from({ length: 18 }, (_, index) => index + 1);

export type ThermocouplePointRow = { 標準溫度: string; 器差值: string };
export type RecorderGrid = Record<string, string>;
export type CalibrationFieldErrors = Record<string, string>;

export const cellKey = (channel: number, temperature: number) => `${channel}_${temperature}`;

const isBlank = (value: string | undefined) => value === undefined || value.trim() === '';
const isNumericText = (value: string) => Number.isFinite(Number(value));

export const validateThermocoupleRows = (rows: ThermocouplePointRow[]): CalibrationFieldErrors => {
  const errors: CalibrationFieldErrors = {};
  rows.forEach((row, index) => {
    if (!isBlank(row.標準溫度) && !isNumericText(row.標準溫度)) {
      errors[`${index}:標準溫度`] = `第 ${index + 1} 列標準溫度需為有效數字`;
    }
    if (!isBlank(row.器差值) && !isNumericText(row.器差值)) {
      errors[`${index}:器差值`] = `第 ${index + 1} 列器差值需為有效數字`;
    }
  });
  return errors;
};

export const buildThermocouplePayload = (
  meta: Omit<Partial<Thermocouple>, '識別碼' | '校正點'>,
  rows: ThermocouplePointRow[],
): Partial<Thermocouple> => ({
  ...meta,
  校正點: rows
    .filter(row => !isBlank(row.標準溫度) && !isBlank(row.器差值))
    .map(row => ({ 標準溫度: Number(row.標準溫度), 器差值: Number(row.器差值) })),
});

export const validateRecorderGrid = (grid: RecorderGrid): CalibrationFieldErrors => {
  const errors: CalibrationFieldErrors = {};
  CHANNELS.forEach(channel => STD_TEMPS.forEach(temperature => {
    const key = cellKey(channel, temperature);
    const value = grid[key];
    if (!isBlank(value) && !isNumericText(value)) {
      errors[key] = `CH${channel} / ${temperature}°C 器差值需為有效數字`;
    }
  }));
  return errors;
};

export const buildRecorderPayload = (
  meta: Omit<Partial<Recorder>, '識別碼' | '校正點'>,
  grid: RecorderGrid,
): Partial<Recorder> => {
  const 校正點: RecorderCalPoint[] = [];
  CHANNELS.forEach(channel => STD_TEMPS.forEach(temperature => {
    const value = grid[cellKey(channel, temperature)];
    if (!isBlank(value)) {
      校正點.push({ 頻道: channel, 標準溫度: temperature, 器差值: Number(value) });
    }
  }));
  return { ...meta, 校正點 };
};
