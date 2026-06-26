import { describe, expect, it } from 'vitest';

import { parseCapaOpenId } from './capaPageUtils';

describe('parseCapaOpenId', () => {
  it('parses valid editId and openId query params', () => {
    expect(parseCapaOpenId(new URLSearchParams('editId=12'))).toBe(12);
    expect(parseCapaOpenId(new URLSearchParams('openId=8'))).toBe(8);
  });

  it('rejects empty, zero, and invalid ids', () => {
    expect(parseCapaOpenId(new URLSearchParams('editId='))).toBeNull();
    expect(parseCapaOpenId(new URLSearchParams('editId=0'))).toBeNull();
    expect(parseCapaOpenId(new URLSearchParams('editId=abc'))).toBeNull();
  });
});
