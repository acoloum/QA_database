import { describe, expect, it } from 'vitest';
import { buildSpcChartModel } from './spcChartModel';
import type { SpcChartData } from '../types';

const statsData: SpcChartData = {
  labels: ['A', 'B', 'C'],
  ids: ['10', '11', '12'],
  dates: ['2026-06-01', '2026-06-02', '2026-06-03'],
  avgs: [10, 11, 16],
  ranges: [1, 2, 3],
  subgroup_sizes: [3, 3, 3],
  all_values: [9, 10, 10, 11, 12, 15, 16, 17],
  x_cl: 10,
  x_ucl: 15,
  x_lcl: 5,
  r_cl: 2,
  r_ucl: 4,
  r_lcl: 0,
  avg_subgroup_size: 3,
  tolerance: { found: true, USL: 15, LSL: 5 },
  process_capability: {
    available: true,
    usl: 15,
    lsl: 5,
    cpk: 1.2,
  },
  distribution_stats: {
    skewness: 0.1,
    kurtosis: 0.2,
    normality: 'good',
    normality_label: '良好',
  },
  cpk_trend: [
    { month: '2026-05', cpk: 1.1, count: 12 },
    { month: '2026-06', cpk: 1.2, count: 18 },
  ],
};

describe('buildSpcChartModel', () => {
  it('沒有統計資料時回傳空模型', () => {
    const model = buildSpcChartModel(null);

    expect(model.chartData).toBeNull();
    expect(model.ids).toEqual([]);
    expect(model.statsSummary).toBeNull();
  });

  it('建立 X-bar、R chart、摘要與直方圖資料', () => {
    const model = buildSpcChartModel(statsData);

    expect(model.ids).toEqual(['10', '11', '12']);
    expect(model.statsSummary).toMatchObject({
      count: 3,
      mean: '12.333',
      min: '10.000',
      max: '16.000',
    });
    expect(model.analysis?.violations.some(v => v.type === 'xbar')).toBe(true);
    expect(model.chartData?.xBar.datasets.some(dataset => dataset.label === 'USL')).toBe(true);
    expect(model.histogramData?.bins.length).toBeGreaterThan(1);
    expect(model.cpkTrend).toHaveLength(2);
  });

  it('依後端 rules_used 限縮 WECO 規則', () => {
    const base = {
      labels: Array.from({ length: 9 }, (_, i) => `P${i}`),
      ids: [], dates: [], subgroup_sizes: [], all_values: [],
      avgs: Array(9).fill(10.1),           // 連續9點同側 → run_9_same_side
      ranges: Array(9).fill(0.2),
      x_cl: 10, x_ucl: 10.9, x_lcl: 9.1, r_cl: 0.2, r_ucl: 0.5, r_lcl: 0,
      avg_subgroup_size: 5,
      tolerance: { found: false }, process_capability: { available: false },
      distribution_stats: {}, cpk_trend: [],
    };
    const withRule = buildSpcChartModel({
      ...base,
      stability: { evaluated: true, stable: false, violations: [], rules_used: ['run_9_same_side'] },
    } as never);
    expect(withRule.analysis!.violations.length).toBeGreaterThan(0);

    const withoutRule = buildSpcChartModel({
      ...base,
      stability: { evaluated: true, stable: true, violations: [], rules_used: ['beyond_limits'] },
    } as never);
    expect(withoutRule.analysis!.violations.length).toBe(0);
  });
});
