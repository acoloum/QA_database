import { describe, expect, it } from 'vitest';

import type { TusPoint } from '../../types';
import { evaluateTusPoint } from './tusEvaluation';

const point = (overrides: Partial<TusPoint> = {}): TusPoint => ({
  點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '', ...overrides,
});

describe('evaluateTusPoint', () => {
  it('校正後最高、最低溫皆在公差內判定合格，最大偏差取絕對值較大者', () => {
    const result = evaluateTusPoint(point({ 修正值: '-0.5', 最高溫: '183.5', 最低溫: '176' }), '180', '5');
    // 校正後 183.0 / 175.5 → 偏差 +3.0 / -4.5
    expect(result).toEqual({ maxDeviation: -4.5, pass: true });
  });

  it('偏差超出公差判定不合格', () => {
    expect(evaluateTusPoint(point({ 最高溫: '186', 最低溫: '179' }), '180', '5'))
      .toEqual({ maxDeviation: 6, pass: false });
  });

  it('偏差恰等於公差仍合格', () => {
    expect(evaluateTusPoint(point({ 最高溫: '185', 最低溫: '180' }), '180', '5').pass).toBe(true);
  });

  it('已排除的點位不判定', () => {
    expect(evaluateTusPoint(point({ 最高溫: '200', 最低溫: '170', 已排除: true }), '180', '5'))
      .toEqual({ maxDeviation: null, pass: null });
  });

  it('沒有溫度資料或設定溫度無效時不判定', () => {
    expect(evaluateTusPoint(point(), '180', '5')).toEqual({ maxDeviation: null, pass: null });
    expect(evaluateTusPoint(point({ 最高溫: '181' }), '', '5')).toEqual({ maxDeviation: null, pass: null });
  });

  it('只有單側溫度時以該側判定', () => {
    expect(evaluateTusPoint(point({ 最低溫: '174' }), '180', '5'))
      .toEqual({ maxDeviation: -6, pass: false });
  });

  it('公差空白時視為 0（與後端一致）', () => {
    expect(evaluateTusPoint(point({ 最高溫: '180.1', 最低溫: '180' }), '180', '').pass).toBe(false);
  });
});
