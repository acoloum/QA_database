import { describe, expect, it } from 'vitest';

import { isMeasurementOutOfTolerance, parseShippingMeasurementNumber } from './shippingMeasurementNumber';

describe('shippingMeasurementNumber', () => {
  it('解析出貨量測數字時保留 0 並拒絕非法文字', () => {
    expect(parseShippingMeasurementNumber('0')).toBe(0);
    expect(parseShippingMeasurementNumber('9.8')).toBe(9.8);
    expect(parseShippingMeasurementNumber('9.8abc')).toBeNull();
    expect(parseShippingMeasurementNumber(null)).toBeNull();
  });

  it('判斷量測值是否超出公差', () => {
    expect(isMeasurementOutOfTolerance('8.9', { lsl: 9, usl: 10 })).toBe(true);
    expect(isMeasurementOutOfTolerance('9.5', { lsl: 9, usl: 10 })).toBe(false);
    expect(isMeasurementOutOfTolerance('bad', { lsl: 9, usl: 10 })).toBe(false);
  });
});
