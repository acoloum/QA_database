import { describe, it, expect } from 'vitest';
import {
  JUDGED_ITEMS,
  SPEC_DRIVEN_ITEMS,
  buildMeasurements,
  buildTraceNumbers,
  duplicateTraceNumberIndexes,
  emptyGrid,
  emptyTraceNumber,
  hydrateGrid,
  hydrateTraceNumbers,
  itemLimits,
  removeTraceNumber,
  visibleSpecDrivenItems,
  type MechGrid,
} from './mechanicalPayload';

describe('visibleSpecDrivenItems', () => {
  it('公差查無這兩項時都不顯示', () => {
    expect(visibleSpecDrivenItems({ lower: { 硬度: 90 }, upper: {} })).toEqual([]);
    expect(visibleSpecDrivenItems(undefined)).toEqual([]);
  });

  it('公差有登錄就顯示，各自認自己的判定邊', () => {
    const limits = { lower: { 韋伯氏硬度: 15 }, upper: { 真直度: 0.3 } };
    expect(visibleSpecDrivenItems(limits)).toEqual(['韋伯氏硬度', '真直度']);
  });

  it('公差只登錄其中一項時只顯示該項', () => {
    expect(visibleSpecDrivenItems({ lower: {}, upper: { 真直度: 0.3 } })).toEqual(['真直度']);
  });

  it('已有數值的項目即使查無公差也不隱藏（避免既有數值變孤兒）', () => {
    const limits = { lower: {}, upper: {} };
    expect(visibleSpecDrivenItems(limits, new Set(['韋伯氏硬度']))).toEqual(['韋伯氏硬度']);
  });

  it('itemLimits 只回傳該項受管制的那一邊', () => {
    const limits = { lower: { 韋伯氏硬度: 15 }, upper: { 真直度: 0.3 } };
    expect(itemLimits(limits, '韋伯氏硬度')).toEqual([15, undefined]);
    expect(itemLimits(limits, '真直度')).toEqual([undefined, 0.3]);
    expect(itemLimits(limits, 'EC值')).toEqual([undefined, undefined]);
  });

  it('選填項目不與必測項目重疊（必測才納入完成判定與免測）', () => {
    for (const item of SPEC_DRIVEN_ITEMS) {
      expect(JUDGED_ITEMS).not.toContain(item);
    }
  });
});

describe('mechanicalPayload', () => {
  it('emptyGrid 常態每項有爐門/爐頂取樣1兩格', () => {
    const grid = emptyGrid();
    expect(grid['硬度']['爐門'][1]).toBe('');
    expect(grid['硬度']['爐頂'][1]).toBe('');
  });

  it('buildMeasurements 僅輸出有值的格子', () => {
    const grid: MechGrid = emptyGrid();
    grid['硬度']['爐門'][1] = '70';
    grid['硬度']['爐頂'][1] = '73';
    const out = buildMeasurements(grid);
    expect(out).toContainEqual({ 量測項目: '硬度', 測量位置: '爐門', 取樣序: 1, 量測值: 70 });
    expect(out).toContainEqual({ 量測項目: '硬度', 測量位置: '爐頂', 取樣序: 1, 量測值: 73 });
    // 空格不輸出
    expect(out.some((m) => m.量測項目 === '抗拉強度')).toBe(false);
  });

  it('buildMeasurements 含第2取樣（異常加測）', () => {
    const grid: MechGrid = emptyGrid();
    grid['硬度']['爐門'][2] = '69';
    const out = buildMeasurements(grid);
    expect(out).toContainEqual({ 量測項目: '硬度', 測量位置: '爐門', 取樣序: 2, 量測值: 69 });
  });

  it('hydrateGrid 由明細還原表單', () => {
    const grid = hydrateGrid([
      { 量測項目: '硬度', 測量位置: '爐門', 取樣序: 1, 量測值: 70 },
      { 量測項目: 'EC值', 測量位置: '爐頂', 取樣序: 1, 量測值: 42 },
    ]);
    expect(grid['硬度']['爐門'][1]).toBe('70');
    expect(grid['EC值']['爐頂'][1]).toBe('42');
  });

  it('JUDGED_ITEMS 為四項判定性質（不含 EC）', () => {
    expect(JUDGED_ITEMS).toEqual(['硬度', '抗拉強度', '降伏強度', '伸長率']);
  });

  it('buildMeasurements 空白字元（僅空格或 tab）視為未輸入，不輸出', () => {
    const grid: MechGrid = emptyGrid();
    grid['硬度']['爐門'][1] = '  ';
    grid['硬度']['爐頂'][1] = '\t';
    const out = buildMeasurements(grid);
    expect(out.some((m) => m.量測項目 === '硬度' && m.測量位置 === '爐門')).toBe(false);
    expect(out.some((m) => m.量測項目 === '硬度' && m.測量位置 === '爐頂')).toBe(false);
  });

  it('buildMeasurements 非數值垃圾輸入（如 "abc"）不輸出該格，而非輸出 null', () => {
    const grid: MechGrid = emptyGrid();
    grid['硬度']['爐門'][1] = 'abc';
    const out = buildMeasurements(grid);
    expect(out.some((m) => m.量測項目 === '硬度' && m.測量位置 === '爐門')).toBe(false);
  });

  it('buildMeasurements 與 hydrateGrid 往返後資料一致', () => {
    const grid: MechGrid = emptyGrid();
    grid['硬度']['爐門'][1] = '70';
    const measurements = buildMeasurements(grid);
    const roundTripped = hydrateGrid(measurements);
    expect(roundTripped['硬度']['爐門'][1]).toBe('70');
  });

  it('buildMeasurements 有輸入時包含 EC值', () => {
    const grid: MechGrid = emptyGrid();
    grid['EC值']['爐門'][1] = '42';
    const out = buildMeasurements(grid);
    expect(out).toContainEqual({ 量測項目: 'EC值', 測量位置: '爐門', 取樣序: 1, 量測值: 42 });
  });
});

describe('機械性質追溯編號 helper', () => {
  it('移除空白、trim 並重新編為連續序號', () => {
    expect(buildTraceNumbers([
      { 序號: 1, 編號: ' E001 ' },
      { 序號: 2, 編號: ' ' },
      { 序號: 3, 編號: 'E002' },
    ])).toEqual([
      { 序號: 1, 編號: 'E001' },
      { 序號: 2, 編號: 'E002' },
    ]);
  });

  it('同清單 trim 後相同值標示所有重複列', () => {
    expect([...duplicateTraceNumberIndexes([
      { 序號: 1, 編號: ' E001' },
      { 序號: 2, 編號: 'E001 ' },
      { 序號: 3, 編號: 'e001' },
    ])]).toEqual([0, 1]);
  });

  it('hydrate 空陣列時保留一列空白輸入', () => {
    expect(hydrateTraceNumbers([])).toEqual([emptyTraceNumber(1)]);
  });

  it('刪除後只重排該份清單且至少保留一列', () => {
    const current = [
      { 序號: 1, 編號: 'A' },
      { 序號: 2, 編號: 'B' },
    ];
    expect(removeTraceNumber(current, 0)).toEqual([{ 序號: 1, 編號: 'B' }]);
    expect(removeTraceNumber([{ 序號: 1, 編號: 'A' }], 0)).toEqual([
      { 序號: 1, 編號: '' },
    ]);
  });
});
