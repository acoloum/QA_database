import { describe, expect, it } from 'vitest';

import {
  buildSegmentKey,
  detectSegmentedKeys,
  expandSegmentedItems,
  hasMidRearSegmentValues,
  remapGroupsOnSegmentToggle,
  SEGMENT_POSITIONS,
} from './shippingSegmentUtils';
import type { ShippingItemConfig } from './shippingMeasurementUtils';

const items: ShippingItemConfig[] = [
  { label: '外徑', key: '外徑', type: 'minmax', segmentable: true },
  { label: '硬度', key: '硬度', type: 'single' },
];

describe('expandSegmentedItems', () => {
  it('未啟用分段時原樣回傳', () => {
    expect(expandSegmentedItems(items, new Set())).toEqual(items);
  });

  it('啟用分段的項目展開為前/中/後三列,公差鍵指回原項目', () => {
    const expanded = expandSegmentedItems(items, new Set(['外徑']));

    expect(expanded).toHaveLength(4);
    expect(expanded[0]).toMatchObject({
      label: '外徑(前)', key: '外徑@前段', toleranceKey: '外徑',
      baseKey: '外徑', position: '前段', type: 'minmax',
    });
    expect(expanded[1].key).toBe('外徑@中段');
    expect(expanded[2].key).toBe('外徑@後段');
    expect(expanded[3].key).toBe('硬度');
  });

  it('未標記 segmentable 的項目即使在集合中也不展開', () => {
    expect(expandSegmentedItems(items, new Set(['硬度']))).toEqual(items);
  });
});

describe('detectSegmentedKeys', () => {
  it('量測資料含「基鍵@」開頭的鍵即視為已分段', () => {
    const result = detectSegmentedKeys(
      { '1': { '外徑@前段': { value_min: 9.8, is_ng: false }, 硬度: { is_ng: false } } },
      items,
    );
    expect(result).toEqual(new Set(['外徑']));
  });

  it('無分段鍵時回傳空集合', () => {
    expect(detectSegmentedKeys({ '1': { 外徑: { is_ng: false } } }, items)).toEqual(new Set());
  });
});

describe('remapGroupsOnSegmentToggle', () => {
  it('開啟分段:單段值搬到前段,中/後段為空', () => {
    const groups = { '1': { 外徑: { value_min: '9.8', value_max: '10.2', is_ng: false }, 硬度: { is_ng: false } } };

    const next = remapGroupsOnSegmentToggle(groups, '外徑', true);

    expect(next['1']['外徑']).toBeUndefined();
    expect(next['1']['外徑@前段']).toEqual({ value_min: '9.8', value_max: '10.2', is_ng: false });
    expect(next['1']['外徑@中段']).toEqual({ is_ng: false });
    expect(next['1']['外徑@後段']).toEqual({ is_ng: false });
    expect(next['1']['硬度']).toEqual({ is_ng: false });
  });

  it('關閉分段:只保留前段值,中/後段捨棄', () => {
    const groups = {
      '1': {
        '外徑@前段': { value_min: '9.8', is_ng: false },
        '外徑@中段': { value_min: '9.9', is_ng: false },
        '外徑@後段': { value_min: '9.7', is_ng: false },
      },
    };

    const next = remapGroupsOnSegmentToggle(groups, '外徑', false);

    expect(next['1']['外徑']).toEqual({ value_min: '9.8', is_ng: false });
    expect(next['1']['外徑@前段']).toBeUndefined();
    expect(next['1']['外徑@中段']).toBeUndefined();
    expect(next['1']['外徑@後段']).toBeUndefined();
  });
});

describe('hasMidRearSegmentValues', () => {
  it('中段或後段有值時回傳 true', () => {
    expect(hasMidRearSegmentValues(
      { '1': { '外徑@中段': { value_min: '9.9', is_ng: false } } }, '外徑',
    )).toBe(true);
  });

  it('僅前段有值時回傳 false', () => {
    expect(hasMidRearSegmentValues(
      { '1': { '外徑@前段': { value_min: '9.8', is_ng: false }, '外徑@中段': { is_ng: false } } }, '外徑',
    )).toBe(false);
  });
});

describe('buildSegmentKey', () => {
  it('組出複合鍵', () => {
    expect(SEGMENT_POSITIONS).toEqual(['前段', '中段', '後段']);
    expect(buildSegmentKey('外徑', '前段')).toBe('外徑@前段');
  });
});
