import { describe, expect, it } from 'vitest';

import type { SatPoint } from '../../types';
import {
  calculateSatReadingDisplay,
  evaluateSatPoint,
  parseSatNumber,
} from './satEvaluation';

describe('satEvaluation', () => {
  it('只接受完整且有限的數字文字', () => {
    expect(parseSatNumber('180.5')).toBe(180.5);
    expect(parseSatNumber('-0.2')).toBe(-0.2);
    expect(parseSatNumber('180abc')).toBeNull();
    expect(parseSatNumber('')).toBeNull();
  });

  it('計算 SAT 讀值差值、偏差與合格狀態', () => {
    expect(calculateSatReadingDisplay({
      reading: { 控制儀表讀值: '180', 校正測試讀值: '181.2' },
      correction: 0.1,
      tolerance: 1.5,
    })).toEqual({ diff: 1.2, deviation: 1.3, pass: true });
  });

  it('非法讀值不列為有效讀值，也不讓區域顯示全數合格', () => {
    const point: SatPoint = {
      控溫區: 'Zone1',
      頻道: 1,
      修正值: '0',
      readings: [
        { 控制儀表讀值: '180abc', 校正測試讀值: '181' },
        { 控制儀表讀值: '180', 校正測試讀值: '182' },
      ],
    };

    expect(evaluateSatPoint(point, '1')).toEqual({
      validCount: 1,
      passCount: 0,
      hasData: true,
      allPass: false,
    });
  });
});
