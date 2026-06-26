import { describe, expect, it } from 'vitest';

import {
  getShippingInspectionItems,
  getShippingItemInputOffsets,
} from './shippingInspectionItems';

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

  it('calculates tab offsets based on item input width', () => {
    const items = getShippingInspectionItems('一般廠商');

    expect(getShippingItemInputOffsets(items)).toEqual({
      itemOffsets: [0, 2, 4, 6, 7, 8, 9],
      totalInputsPerGroup: 10,
    });
  });
});
