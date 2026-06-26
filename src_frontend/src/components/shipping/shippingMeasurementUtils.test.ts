import { describe, expect, it } from 'vitest';
import { calculateShippingViolations } from './shippingMeasurementUtils';
import type { ToleranceResult } from '../../types';

const tolerance: ToleranceResult = {
  success: true,
  found: true,
  tolerances: [
    {
      項目: '外徑',
      標準值: null,
      公差上限: null,
      公差下限: null,
      尺寸上限: 10,
      尺寸下限: 5,
      單位: 'mm',
    },
    {
      項目: '同心度',
      標準值: null,
      公差上限: null,
      公差下限: null,
      尺寸上限: 0.2,
      尺寸下限: null,
      單位: 'mm',
    },
  ],
};

describe('calculateShippingViolations', () => {
  it('標記 min/max 與 single 超出公差的欄位', () => {
    const violations = calculateShippingViolations({
      items: [
        { label: '外徑', key: '外徑', type: 'minmax' },
        { label: '同心度', key: '同心度', type: 'single' },
      ],
      groupKeys: ['1'],
      groups: {
        '1': {
          外徑: { value_min: '4.9', value_max: '9.8', is_ng: false },
          同心度: { value_single: '0.25', is_ng: false },
        },
      },
      tolerance,
      spec: '10',
    });

    expect(violations).toEqual({
      '1:外徑:value_min': true,
      '1:同心度:value_single': true,
    });
  });

  it('使用 toleranceKey 對應規格標準值計算相對公差', () => {
    const violations = calculateShippingViolations({
      items: [
        { label: '顯示長度', key: '顯示長度', toleranceKey: '長度', type: 'single' },
      ],
      groupKeys: ['1'],
      groups: {
        '1': {
          顯示長度: { value_single: '100.6', is_ng: false },
        },
      },
      tolerance: {
        success: true,
        found: true,
        tolerances: [
          {
            項目: '長度',
            標準值: null,
            公差上限: 0.5,
            公差下限: -0.5,
            尺寸上限: null,
            尺寸下限: null,
            單位: 'mm',
          },
        ],
      },
      spec: '10*8*100',
    });

    expect(violations).toEqual({
      '1:顯示長度:value_single': true,
    });
  });

  it('沒有公差資料時回傳空物件', () => {
    expect(calculateShippingViolations({
      items: [{ label: '外徑', key: '外徑', type: 'minmax' }],
      groupKeys: ['1'],
      groups: {},
      tolerance: null,
      spec: '',
    })).toEqual({});
  });
});
