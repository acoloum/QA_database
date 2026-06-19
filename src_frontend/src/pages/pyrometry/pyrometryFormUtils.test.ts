import { describe, expect, it } from 'vitest';

import { computeRangeStats, splitReportFields, type ReportFieldsResponse } from './pyrometryFormUtils';

describe('pyrometryFormUtils', () => {
  it('splits report item rows from scalar metadata', () => {
    const raw = {
      客戶名稱: '測試客戶',
      預估總重量: 12,
      是否急件: true,
      料號批次: [
        { 工件料號: 'P-001', 生產批號: 'B-001', 內外徑尺寸: '40x3', 支數: '10' },
        { 工件料號: '缺欄位', 生產批號: 'B-002', 內外徑尺寸: '40x3' },
      ],
    } as unknown as ReportFieldsResponse;

    const result = splitReportFields(raw);

    expect(result.meta).toEqual({
      客戶名稱: '測試客戶',
      預估總重量: '12',
      是否急件: 'true',
    });
    expect(result.itemRows).toEqual([
      { 工件料號: 'P-001', 生產批號: 'B-001', 內外徑尺寸: '40x3', 支數: '10' },
    ]);
  });

  it('computes max and min values inside the selected range', () => {
    const stats = computeRangeStats({
      CH1: [180, 181, 183, 182],
      CH2: [179, 178, 180, 181],
    }, 1, 2);

    expect(stats).toEqual([
      { 名稱: 'CH1', 最高溫: 183, 最低溫: 181 },
      { 名稱: 'CH2', 最高溫: 180, 最低溫: 178 },
    ]);
  });
});
