import { describe, expect, it } from 'vitest';

import {
  getShippingInspectionItems,
  getShippingItemInputOffsets,
  resolvePrimaryHardness,
} from './shippingInspectionItems';

describe('resolvePrimaryHardness', () => {
  it('公差列「洛氏硬度」時比對洛氏硬度並標示 HRB', () => {
    expect(resolvePrimaryHardness(['外徑', '洛氏硬度'])).toEqual({
      toleranceKey: '洛氏硬度', label: '洛氏硬度(HRB)',
    });
  });

  it('公差僅列未指明標度的「硬度」時就比對「硬度」', () => {
    expect(resolvePrimaryHardness(['外徑', '硬度'])).toEqual({
      toleranceKey: '硬度', label: '硬度',
    });
  });

  it('同時存在時以「洛氏硬度」優先', () => {
    expect(resolvePrimaryHardness(['硬度', '洛氏硬度'])?.toleranceKey).toBe('洛氏硬度');
  });

  it('韋伯氏硬度不得被當成主硬度', () => {
    expect(resolvePrimaryHardness(['韋伯氏硬度'])).toBeNull();
  });

  it('公差尚未載入或查無時回傳 null 交由呼叫端沿用預設', () => {
    expect(resolvePrimaryHardness(undefined)).toBeNull();
    expect(resolvePrimaryHardness([])).toBeNull();
  });
});

describe('shippingInspectionItems', () => {
  it('returns base inspection items for normal vendors', () => {
    expect(getShippingInspectionItems('一般廠商').map(item => item.key)).toEqual([
      '外徑',
      '內徑',
      '厚度',
      '同心度',
      '長度',
      '硬度',
      '真直度',
    ]);
  });

  it('adds Antai-specific roundness and Webster hardness items', () => {
    const items = getShippingInspectionItems('安泰金屬');

    expect(items.map(item => item.key)).toEqual([
      '外徑',
      '內徑',
      '真圓度',
      '厚度',
      '同心度',
      '長度',
      '硬度',
      '韋伯氏硬度',
      '真直度',
    ]);
    expect(items.find(item => item.key === '硬度')?.label).toBe('洛氏硬度(HRB)');
  });

  it('公差列「硬度」時，安泰的硬度欄改為比對「硬度」而非洛氏硬度', () => {
    // 安泰 39.5*34.7*111 的公差項目登錄為未指明標度的「硬度」；
    // 原本依廠商硬編碼強制比對「洛氏硬度」會對不上而靜默不判定。
    const items = getShippingInspectionItems('安泰金屬', ['外徑', '硬度']);
    const hardness = items.find(item => item.key === '硬度');

    expect(hardness?.toleranceKey).toBe('硬度');
    expect(hardness?.label).toBe('硬度');
  });

  it('公差正名為「洛氏硬度」後，一般廠商的硬度欄也會跟著比對洛氏硬度', () => {
    // 正名 119 筆公差後，非安泰廠商若仍固定比對「硬度」會漏判
    const items = getShippingInspectionItems('久鼎', ['外徑', '洛氏硬度']);
    const hardness = items.find(item => item.key === '硬度');

    expect(hardness?.toleranceKey).toBe('洛氏硬度');
    expect(hardness?.label).toBe('洛氏硬度(HRB)');
  });

  it('公差尚未載入時沿用原本依廠商的預設，避免標籤閃動', () => {
    expect(getShippingInspectionItems('安泰金屬').find(i => i.key === '硬度'))
      .toMatchObject({ label: '洛氏硬度(HRB)', toleranceKey: '洛氏硬度' });
    expect(getShippingInspectionItems('久鼎').find(i => i.key === '硬度')?.label)
      .toBe('硬度');
  });

  it('韋伯氏硬度欄位不因公差未定義而消失（實際有 65 筆紀錄在無韋伯公差的規格上填值）', () => {
    const items = getShippingInspectionItems('安泰金屬', ['外徑', '洛氏硬度']);

    expect(items.map(item => item.key)).toContain('韋伯氏硬度');
  });

  it('calculates tab offsets based on item input width', () => {
    const items = getShippingInspectionItems('一般廠商');

    expect(getShippingItemInputOffsets(items)).toEqual({
      itemOffsets: [0, 2, 4, 6, 7, 8, 9],
      totalInputsPerGroup: 10,
    });
  });
});
