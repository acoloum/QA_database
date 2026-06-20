import { describe, expect, it } from 'vitest';

import { formatNcmrQuantity } from './ncmrPageUtils';

describe('ncmrPageUtils', () => {
  it('格式化 NCMR 數量時保留 0', () => {
    expect(formatNcmrQuantity(0)).toBe('0');
    expect(formatNcmrQuantity('0')).toBe('0');
  });

  it('格式化 NCMR 數量時空值回傳空字串', () => {
    expect(formatNcmrQuantity(null)).toBe('');
    expect(formatNcmrQuantity(undefined)).toBe('');
    expect(formatNcmrQuantity('')).toBe('');
  });
});
