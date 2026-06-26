import { describe, expect, it } from 'vitest';

import { buildFurnacePayload } from './furnaceFormPayload';

describe('buildFurnacePayload', () => {
  it('builds a trimmed payload with numeric defaults', () => {
    expect(buildFurnacePayload({
      爐號: ' F-01 ',
      名稱: ' 1號爐 ',
      製程類型: '',
      TUS點數: 12,
      SAT點數: 2,
      TUS頻率_月: 3,
      SAT頻率_月: 6,
      TUS允許公差: ' 10 ',
      SAT允許誤差: '',
      有效加熱區尺寸: '',
      儀器型式: '',
      CQI9等級: '',
      啟用狀態: true,
      備註: ' 備註 ',
    })).toMatchObject({
      爐號: 'F-01',
      名稱: '1號爐',
      TUS點數: 12,
      SAT點數: 2,
      TUS頻率_月: 3,
      SAT頻率_月: 6,
      TUS允許公差: '10',
      SAT允許誤差: '',
      備註: '備註',
    });
  });

  it('rejects empty or non-positive numeric fields', () => {
    expect(() => buildFurnacePayload({
      爐號: 'F-01',
      名稱: '1號爐',
      TUS點數: '',
      SAT點數: 2,
    })).toThrow('TUS點數');

    expect(() => buildFurnacePayload({
      爐號: 'F-01',
      名稱: '1號爐',
      TUS點數: 0,
      SAT點數: 2,
    })).toThrow('TUS點數');

    expect(() => buildFurnacePayload({
      爐號: 'F-01',
      名稱: '1號爐',
      TUS點數: 12,
      SAT點數: Number.NaN,
    })).toThrow('SAT點數');
  });
});
