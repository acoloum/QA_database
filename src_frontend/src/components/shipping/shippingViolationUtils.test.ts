import { describe, expect, it } from 'vitest';

import { evaluateShippingViolation } from './shippingViolationUtils';
import type { ShippingInspection } from '../../types';

const baseInspection = {
  材質: '6061',
  檢驗規格: '10mm',
  廠商中文名稱: 'A廠',
} as ShippingInspection;

describe('evaluateShippingViolation', () => {
  it('找不到公差時標記為未找到且不判 NG', () => {
    expect(evaluateShippingViolation(baseInspection, {})).toEqual({ found: false, hasViolation: false });
  });

  it('外徑 min/max 任一超出公差時判 NG', () => {
    const result = evaluateShippingViolation({
      ...baseInspection,
      measurements: {
        前段: {
          外徑: { value_min: 8.9, value_max: 10.2, is_ng: false },
        },
      },
    } as ShippingInspection, {
      '6061|||10mm|||A廠': {
        外徑: { lsl: 9, usl: 10 },
      },
    });

    expect(result).toEqual({ found: true, hasViolation: true });
  });

  it('單值量測項目落在公差內時判合格', () => {
    const result = evaluateShippingViolation({
      ...baseInspection,
      measurements: {
        前段: {
          硬度: { value_single: 55, is_ng: false },
        },
      },
    } as ShippingInspection, {
      '6061|||10mm|||A廠': {
        硬度: { lsl: 50, usl: 60 },
      },
    });

    expect(result).toEqual({ found: true, hasViolation: false });
  });

  it('分段複合鍵套用基礎項目公差判定 NG', () => {
    const result = evaluateShippingViolation({
      ...baseInspection,
      measurements: {
        '1': {
          '外徑@中段': { value_min: 8.9, value_max: 9.5, is_ng: false },
        },
      },
    } as ShippingInspection, {
      '6061|||10mm|||A廠': {
        外徑: { lsl: 9, usl: 10 },
      },
    });

    expect(result).toEqual({ found: true, hasViolation: true });
  });

  it('分段量測皆在公差內時判合格', () => {
    const result = evaluateShippingViolation({
      ...baseInspection,
      measurements: {
        '1': {
          '外徑@前段': { value_min: 9.2, value_max: 9.8, is_ng: false },
          '外徑@後段': { value_min: 9.1, value_max: 9.9, is_ng: false },
        },
      },
    } as ShippingInspection, {
      '6061|||10mm|||A廠': {
        外徑: { lsl: 9, usl: 10 },
      },
    });

    expect(result).toEqual({ found: true, hasViolation: false });
  });
});
