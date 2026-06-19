import { describe, expect, it } from 'vitest';

import {
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  computeRangeStats,
  splitReportFields,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';

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

  it('applies selected chart range to TUS max and min values', () => {
    const points = [{ 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' }];

    const result = applyChartRangeToTusPoints(points, {
      時間: ['00:00', '00:01', '00:02'],
      數值: { CH1: [180.1, 182.35, 181.2] },
    }, 1, 2);

    expect(result[0]).toMatchObject({ 最高溫: '182.35', 最低溫: '181.2' });
  });

  it('fills SAT test readings from chart values and preserves control readings', () => {
    const points = [{
      控溫區: 'Zone1',
      頻道: 13,
      修正值: '',
      readings: [
        { 控制儀表讀值: '180', 校正測試讀值: '' },
        { 控制儀表讀值: '181', 校正測試讀值: '' },
      ],
    }];

    const result = applyChartRangeToSatReadings(points, {
      時間: ['00:00', '00:01', '00:02'],
      數值: { CH13: [179.991, 180.456, 181.234] },
    }, 1, 2, '校正測試讀值');

    expect(result[0].readings).toEqual([
      { 控制儀表讀值: '180', 校正測試讀值: '180.46' },
      { 控制儀表讀值: '181', 校正測試讀值: '181.23' },
    ]);
  });

  it('fills furnace control readings and preserves SAT test readings', () => {
    const points = [{
      控溫區: 'Zone1',
      頻道: 13,
      修正值: '',
      readings: [
        { 控制儀表讀值: '', 校正測試讀值: '181' },
        { 控制儀表讀值: '', 校正測試讀值: '182' },
      ],
    }];

    const result = applyChartRangeToSatReadings(points, {
      時間: ['00:00', '00:01'],
      數值: { Furnace1: [180.111, 180.499] },
    }, 0, 1, '控制儀表讀值');

    expect(result[0].readings).toEqual([
      { 控制儀表讀值: '180.11', 校正測試讀值: '181' },
      { 控制儀表讀值: '180.5', 校正測試讀值: '182' },
    ]);
  });
});
