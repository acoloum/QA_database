import { describe, expect, it } from 'vitest';

import {
  updateItemRowAt,
  updateSatFieldAt,
  updateSatReadingAt,
  updateTusPointAt,
} from './pyrometryPointUpdates';

describe('pyrometryPointUpdates', () => {
  it('updates TUS channel values without mutating the original list', () => {
    const points = [{ 點位: 'P1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' }];

    const result = updateTusPointAt(points, 0, '頻道', '2');

    expect(result[0].頻道).toBe(2);
    expect(points[0].頻道).toBe(1);
  });

  it('updates SAT readings and preserves other readings', () => {
    const points = [{
      控溫區: 'Z1',
      頻道: 13,
      修正值: '',
      readings: [
        { 控制儀表讀值: '180', 校正測試讀值: '181' },
        { 控制儀表讀值: '182', 校正測試讀值: '183' },
      ],
    }];

    const result = updateSatReadingAt(points, 0, 1, '校正測試讀值', '184');

    expect(result[0].readings[1].校正測試讀值).toBe('184');
    expect(result[0].readings[0].校正測試讀值).toBe('181');
  });

  it('updates SAT channel and report item rows immutably', () => {
    const sat = [{ 控溫區: 'Z1', 頻道: 13, 修正值: '', readings: [] }];
    expect(updateSatFieldAt(sat, 0, '頻道', '')[0].頻道).toBeNull();

    const rows = [{ 工件料號: 'A', 生產批號: '', 內外徑尺寸: '', 支數: '' }];
    expect(updateItemRowAt(rows, 0, '工件料號', 'B')[0].工件料號).toBe('B');
    expect(rows[0].工件料號).toBe('A');
  });
});
