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
});
