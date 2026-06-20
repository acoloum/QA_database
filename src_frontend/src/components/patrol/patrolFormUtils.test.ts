import { describe, expect, it } from 'vitest';

import {
  buildPatrolPayload,
  calcPatrolLimits,
  isPatrolCellNG,
  isPatrolConcentricityNG,
  type PatrolDetailInput,
} from './patrolFormUtils';

const details: PatrolDetailInput[] = [
  { group: '第1組', pos: '前段', item: '厚度', min: '2.4', max: '3.0' },
  { group: '第1組', pos: '前段', item: '外徑', min: '84.9', max: '85.4' },
  { group: '第2組', pos: '中段', item: '外徑', min: '', max: '' },
];

describe('patrolFormUtils', () => {
  it('用擠壓規格解析值計算公差界限', () => {
    const limits = calcPatrolLimits(
      { 尺寸下限: null, 尺寸上限: null, 公差下限: -0.2, 公差上限: 0.2, 標準值: null },
      '厚度',
      { 外徑: 85, 厚度: 2.8 },
    );

    expect(limits).toEqual({ lsl: 2.5999999999999996, usl: 3 });
  });

  it('判斷巡檢單格量測值是否超出界限', () => {
    const isNg = isPatrolCellNG({
      details,
      tolerances: [{ 項目: '外徑', 位置: '', 尺寸下限: 85, 尺寸上限: 86, 公差下限: null, 公差上限: null, 標準值: null, 單位: 'mm' }],
      specStdValues: {},
      group: '第1組',
      pos: '前段',
      item: '外徑',
      type: 'min',
    });

    expect(isNg).toBe(true);
  });

  it('用厚度最大最小差判斷同心度 NG', () => {
    const isNg = isPatrolConcentricityNG({
      details,
      tolerances: [{ 項目: '同心度', 位置: '', 尺寸下限: null, 尺寸上限: null, 公差下限: 0, 公差上限: 0.4, 標準值: null, 單位: 'mm' }],
      specStdValues: {},
      group: '第1組',
      pos: '前段',
    });

    expect(isNg).toBe(true);
  });

  it('只把有輸入 min 或 max 的明細組成 payload', () => {
    const payload = buildPatrolPayload({
      editId: 12,
      date: '2026-06-20',
      machine: 'M1',
      operator: 'O1',
      inspector: 'I1',
      customer: 'C1',
      material: 'A6061',
      batch: 'B1',
      spec: '85*2.8',
      details,
    });

    expect(payload).toMatchObject({
      id: 12,
      檢驗日期: '2026-06-20',
      機台: 'M1',
      主機手: 'O1',
      檢驗人員: 'I1',
    });
    expect(payload.details).toEqual([
      { group: '第1組', item: '厚度', pos: '前段', min: 2.4, max: 3 },
      { group: '第1組', item: '外徑', pos: '前段', min: 84.9, max: 85.4 },
    ]);
  });
});
