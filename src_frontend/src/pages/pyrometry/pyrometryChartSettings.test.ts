import { describe, expect, it } from 'vitest';

import { parsePyrometryChartNumber, resolvePyrometryChartSettings } from './pyrometryChartSettings';

describe('pyrometryChartSettings', () => {
  it('解析圖表數字時保留合法 0 並拒絕非法文字', () => {
    expect(parsePyrometryChartNumber('0', 180)).toBe(0);
    expect(parsePyrometryChartNumber('180.5', 180)).toBe(180.5);
    expect(parsePyrometryChartNumber('', 180)).toBe(180);
    expect(parsePyrometryChartNumber('180abc', 180)).toBe(180);
  });

  it('解析爐溫圖表設定值', () => {
    expect(resolvePyrometryChartSettings({ setpoint: '0', tolerance: '0' })).toEqual({
      setpointValue: 0,
      toleranceValue: 0,
    });
    expect(resolvePyrometryChartSettings({ setpoint: '', tolerance: 'bad' })).toEqual({
      setpointValue: 180,
      toleranceValue: 10,
    });
  });
});
