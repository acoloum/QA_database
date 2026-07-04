import { describe, expect, it } from 'vitest';

import {
  addSatReadingToPoint,
  applyParsedPyrometryData,
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  computeRangeStats,
  detectSoakStartIndex,
  inheritReportFields,
  parseActiveZone,
  parseOptionalChannel,
  parseRangeIndex,
  removeSatReadingFromPoint,
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

  it('aligns TUS max/min values by channel identity even when file columns are out of numeric order', () => {
    // 上傳檔案的欄位順序不保證是 TUS-1...TUS-12 遞增（例如記錄器實際接線/匯出順序），
    // TUS-10 在此故意排在第2欄，驗證表格列不會把其他通道的數值誤植到 TUS-10 或其他列上。
    const points = [
      { 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' },
      { 點位: 'TUS-2', 熱電偶編號: '', 頻道: 2, 修正值: '', 最高溫: '', 最低溫: '' },
      { 點位: 'TUS-3', 熱電偶編號: '', 頻道: 3, 修正值: '', 最高溫: '', 最低溫: '' },
      { 點位: 'TUS-10', 熱電偶編號: '', 頻道: 10, 修正值: '', 最高溫: '', 最低溫: '' },
    ];

    const result = applyChartRangeToTusPoints(points, {
      時間: ['00:00', '00:01'],
      數值: {
        'TUS-1': [400, 401],
        'TUS-10': [50, 52],
        'TUS-2': [402, 403],
        'TUS-3': [404, 405],
      },
    }, 0, 1);

    expect(result.find(p => p.點位 === 'TUS-1')).toMatchObject({ 最高溫: '401', 最低溫: '400' });
    expect(result.find(p => p.點位 === 'TUS-2')).toMatchObject({ 最高溫: '403', 最低溫: '402' });
    expect(result.find(p => p.點位 === 'TUS-3')).toMatchObject({ 最高溫: '405', 最低溫: '404' });
    expect(result.find(p => p.點位 === 'TUS-10')).toMatchObject({ 最高溫: '52', 最低溫: '50' });
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

  it('aligns SAT readings by channel identity even when file columns are out of numeric order', () => {
    const points = [
      { 控溫區: 'Zone1', 頻道: 13, 修正值: '', readings: [{ 控制儀表讀值: '', 校正測試讀值: '' }] },
      { 控溫區: 'Zone2', 頻道: 14, 修正值: '', readings: [{ 控制儀表讀值: '', 校正測試讀值: '' }] },
    ];

    const result = applyChartRangeToSatReadings(points, {
      時間: ['00:00'],
      數值: { 'SAT-14': [200], 'SAT-13': [180] },
    }, 0, 0, '校正測試讀值');

    expect(result[0].readings).toEqual([{ 控制儀表讀值: '', 校正測試讀值: '180' }]);
    expect(result[1].readings).toEqual([{ 控制儀表讀值: '', 校正測試讀值: '200' }]);
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

  it('adds and removes SAT readings without mutating the original point', () => {
    const point = {
      控溫區: 'Zone1',
      頻道: 13,
      修正值: '',
      readings: [{ 控制儀表讀值: '180', 校正測試讀值: '181' }],
    };

    const added = addSatReadingToPoint(point);
    expect(added.readings).toHaveLength(2);
    expect(point.readings).toHaveLength(1);

    const removed = removeSatReadingFromPoint(added, 0);
    expect(removed.readings).toEqual([{ 控制儀表讀值: '', 校正測試讀值: '' }]);
  });

  it('inherits report fields by merging metadata and replacing rows only when provided', () => {
    const currentMeta = { 客戶名稱: '原客戶', 測試條件: '滿爐' };
    const currentRows = [{ 工件料號: 'P-OLD', 生產批號: 'B-OLD', 內外徑尺寸: '40x3', 支數: '10' }];

    const result = inheritReportFields(currentMeta, currentRows, {
      客戶名稱: '新客戶',
      料號批次: [{ 工件料號: 'P-NEW', 生產批號: 'B-NEW', 內外徑尺寸: '50x3', 支數: '20' }],
    });

    expect(result.meta).toEqual({ 客戶名稱: '新客戶', 測試條件: '滿爐' });
    expect(result.itemRows).toEqual([
      { 工件料號: 'P-NEW', 生產批號: 'B-NEW', 內外徑尺寸: '50x3', 支數: '20' },
    ]);

    const noRows = inheritReportFields(currentMeta, currentRows, { 客戶名稱: '新客戶' });
    expect(noRows.itemRows).toBe(currentRows);
  });

  it('parses optional channel values without converting invalid text to NaN', () => {
    expect(parseOptionalChannel('')).toBeNull();
    expect(parseOptionalChannel('  ')).toBeNull();
    expect(parseOptionalChannel('13')).toBe(13);
    expect(parseOptionalChannel('13.5')).toBeNull();
    expect(parseOptionalChannel('abc')).toBeNull();
    expect(parseOptionalChannel('0')).toBeNull();
  });

  it('parses range and active zone indices with safe fallback', () => {
    expect(parseRangeIndex('2')).toBe(2);
    expect(parseRangeIndex('2.5', 1)).toBe(1);
    expect(parseRangeIndex('', 1)).toBe(1);
    expect(parseRangeIndex('-1', 1)).toBe(1);
    expect(parseActiveZone('1', 0, 2)).toBe(1);
    expect(parseActiveZone('5', 0, 2)).toBe(0);
  });

  it('applies parsed recorder data and returns the range plus updated TUS points', () => {
    const result = applyParsedPyrometryData({
      destination: 'recorder',
      parsedData: {
        時間: ['09:00', '09:10'],
        數值: { CH1: [180, 181] },
      },
      tusPoints: [{ 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' }],
      satPoints: [],
      // 不驗證自動偵測；setpoint/tolerance 為 NaN 讓 soakStart 退化為 0，維持舊行為
      setpoint: NaN,
      tolerance: NaN,
    });

    expect(result.chartData).toEqual({ 時間: ['09:00', '09:10'], 數值: { CH1: [180, 181] } });
    expect(result.rangeStart).toBe(0);
    expect(result.rangeEnd).toBe(1);
    expect(result.tusPoints?.[0]).toMatchObject({ 最高溫: '181', 最低溫: '180' });
  });

  it('applies parsed furnace data to SAT control readings', () => {
    const result = applyParsedPyrometryData({
      destination: 'furnace',
      parsedData: {
        時間: ['09:00'],
        數值: { F1: [180.123] },
      },
      tusPoints: [],
      satPoints: [{
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '',
        readings: [{ 控制儀表讀值: '', 校正測試讀值: '181' }],
      }],
      // 不驗證自動偵測；setpoint/tolerance 為 NaN 讓 soakStart 退化為 0，維持舊行為
      setpoint: NaN,
      tolerance: NaN,
    });

    expect(result.furnaceChartData).toEqual({ 時間: ['09:00'], 數值: { F1: [180.123] } });
    expect(result.furnaceRangeStart).toBe(0);
    expect(result.furnaceRangeEnd).toBe(0);
    expect(result.satPoints?.[0].readings).toEqual([
      { 控制儀表讀值: '180.12', 校正測試讀值: '181' },
    ]);
  });

  it('auto-detects TUS soak start from setpoint/tolerance and trims stats accordingly', () => {
    const result = applyParsedPyrometryData({
      destination: 'recorder',
      parsedData: {
        時間: ['09:00', '09:10', '09:20', '09:30'],
        數值: { CH1: [100, 150, 178, 182] },
      },
      tusPoints: [{ 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '', 最高溫: '', 最低溫: '' }],
      satPoints: [],
      setpoint: 180,
      tolerance: 5,
    });

    expect(result.rangeStart).toBe(2);
    expect(result.rangeEnd).toBe(3);
    expect(result.tusPoints?.[0]).toMatchObject({ 最高溫: '182', 最低溫: '178' });
  });

  it('auto-detects SAT soak start from setpoint/tolerance', () => {
    const result = applyParsedPyrometryData({
      destination: 'sat',
      parsedData: {
        時間: ['09:00', '09:10', '09:20', '09:30'],
        數值: { CH13: [100, 150, 178, 182] },
      },
      tusPoints: [],
      satPoints: [{
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '',
        readings: [
          { 控制儀表讀值: '180', 校正測試讀值: '' },
          { 控制儀表讀值: '180', 校正測試讀值: '' },
        ],
      }],
      setpoint: 180,
      tolerance: 5,
    });

    expect(result.satRangeStart).toBe(2);
    expect(result.satRangeEnd).toBe(3);
    expect(result.satPoints?.[0].readings).toEqual([
      { 控制儀表讀值: '180', 校正測試讀值: '178' },
      { 控制儀表讀值: '180', 校正測試讀值: '182' },
    ]);
  });

  it('auto-detects furnace body soak start from setpoint/tolerance', () => {
    const result = applyParsedPyrometryData({
      destination: 'furnace',
      parsedData: {
        時間: ['09:00', '09:10', '09:20', '09:30'],
        數值: { F1: [100, 150, 178, 182] },
      },
      tusPoints: [],
      satPoints: [{
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '',
        readings: [
          { 控制儀表讀值: '', 校正測試讀值: '181' },
          { 控制儀表讀值: '', 校正測試讀值: '182' },
        ],
      }],
      setpoint: 180,
      tolerance: 5,
    });

    expect(result.furnaceRangeStart).toBe(2);
    expect(result.furnaceRangeEnd).toBe(3);
    expect(result.satPoints?.[0].readings).toEqual([
      { 控制儀表讀值: '178', 校正測試讀值: '181' },
      { 控制儀表讀值: '182', 校正測試讀值: '182' },
    ]);
  });

  describe('detectSoakStartIndex', () => {
    it('finds the soak start index once all channels enter the tolerance band and stay there', () => {
      expect(detectSoakStartIndex({ CH1: [100, 150, 178, 182, 181, 180] }, 180, 5)).toBe(2);
    });

    it('returns 0 when every value is already within tolerance', () => {
      expect(detectSoakStartIndex({ CH1: [180, 181, 179, 180] }, 180, 5)).toBe(0);
    });

    it('returns 0 when the data never stabilizes (still out of range at the end)', () => {
      expect(detectSoakStartIndex({ CH1: [100, 110, 120, 130] }, 180, 5)).toBe(0);
    });

    it('returns 0 when fewer than 2 stable points remain at the tail', () => {
      expect(detectSoakStartIndex({ CH1: [100, 150, 170, 181] }, 180, 5)).toBe(0);
    });

    it('returns 0 when setpoint or tolerance is not a finite number', () => {
      expect(detectSoakStartIndex({ CH1: [180, 181] }, NaN, 5)).toBe(0);
      expect(detectSoakStartIndex({ CH1: [180, 181] }, 180, NaN)).toBe(0);
    });

    it('returns 0 when there are no channels', () => {
      expect(detectSoakStartIndex({}, 180, 5)).toBe(0);
    });

    it('uses the channel that stabilizes latest across multiple channels', () => {
      expect(detectSoakStartIndex({
        CH1: [175, 181, 180, 181],
        CH2: [100, 150, 178, 181],
      }, 180, 5)).toBe(2);
    });
  });
});
