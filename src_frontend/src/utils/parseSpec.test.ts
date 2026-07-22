import { describe, expect, it } from 'vitest';

import { parseSpec } from './parseSpec';

describe('parseSpec', () => {
  it('支援大寫 X 分隔的外徑厚度長度規格', () => {
    expect(parseSpec('62.5X2.3X450')).toEqual({
      外徑: 62.5,
      厚度: 2.3,
      內徑: 57.9,
      長度: 450,
    });
  });

  it('遇到部分非法數字時不使用 parseFloat 的截斷結果', () => {
    expect(parseSpec('62.5abc*2.3*450')).toEqual({});
  });

  it('四段式規格直接取用明列的內徑與厚度，不幾何回推', () => {
    // 外徑*內徑*厚度*長度；(33-26.5)/2=3.25 是錯誤回推值，厚度應為明列的 2.0
    expect(parseSpec('33*26.5*2.0*244')).toEqual({
      外徑: 33,
      內徑: 26.5,
      厚度: 2.0,
      長度: 244,
    });
    expect(parseSpec('22*20*1.8*4000')).toEqual({
      外徑: 22,
      內徑: 20,
      厚度: 1.8,
      長度: 4000,
    });
  });
});
