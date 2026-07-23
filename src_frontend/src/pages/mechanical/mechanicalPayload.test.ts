import { describe, it, expect } from 'vitest';
import {
  JUDGED_ITEMS,
  buildMeasurements,
  emptyGrid,
  hydrateGrid,
  type MechGrid,
} from './mechanicalPayload';

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
