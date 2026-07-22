import { describe, expect, it } from 'vitest';

import { isMeasurementOutOfTolerance, parseShippingMeasurementNumber } from './shippingMeasurementNumber';

describe('shippingMeasurementNumber', () => {
  it('解析出貨量測數字時保留 0 並拒絕非法文字', () => {
    expect(parseShippingMeasurementNumber('0')).toBe(0);
    expect(parseShippingMeasurementNumber('9.8')).toBe(9.8);
    expect(parseShippingMeasurementNumber('9.8abc')).toBeNull();
    expect(parseShippingMeasurementNumber('   ')).toBeNull();
    expect(parseShippingMeasurementNumber(null)).toBeNull();
  });

  it('判斷量測值是否超出公差', () => {
    expect(isMeasurementOutOfTolerance('8.9', { lsl: 9, usl: 10 })).toBe(true);
    expect(isMeasurementOutOfTolerance('9.5', { lsl: 9, usl: 10 })).toBe(false);
    expect(isMeasurementOutOfTolerance('bad', { lsl: 9, usl: 10 })).toBe(false);
  });

  it('尺寸項目的 0 視為未量測時不判超差', () => {
    // 內徑/厚度等尺寸空白存成 0，開啟 treatZeroAsUnmeasured 後不應誤判超差
    expect(isMeasurementOutOfTolerance('0', { lsl: 9, usl: 10 }, true)).toBe(false);
    expect(isMeasurementOutOfTolerance(0, { lsl: 9, usl: 10 }, true)).toBe(false);
    // 未開啟時維持原行為（0 低於下限 → 超差）
    expect(isMeasurementOutOfTolerance('0', { lsl: 9, usl: 10 })).toBe(true);
    // 開啟時，非 0 的真實出界仍要判超差
    expect(isMeasurementOutOfTolerance('8.9', { lsl: 9, usl: 10 }, true)).toBe(true);
  });
});
