import { describe, expect, it } from 'vitest';

import { parseDispositionNumberInput, parseNullableDispositionNumberInput } from './dispositionFormUtils';

describe('dispositionFormUtils', () => {
  it('處置必填數量解析非法值為 0 且保留 0', () => {
    expect(parseDispositionNumberInput('0')).toBe(0);
    expect(parseDispositionNumberInput('12')).toBe(12);
    expect(parseDispositionNumberInput('12abc')).toBe(0);
    expect(parseDispositionNumberInput('')).toBe(0);
  });

  it('處置可空數量解析空白與非法值為 null 且保留 0', () => {
    expect(parseNullableDispositionNumberInput('0')).toBe(0);
    expect(parseNullableDispositionNumberInput('12')).toBe(12);
    expect(parseNullableDispositionNumberInput('12abc')).toBeNull();
    expect(parseNullableDispositionNumberInput('')).toBeNull();
  });
});
