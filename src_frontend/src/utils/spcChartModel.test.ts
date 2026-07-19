import { describe, expect, it } from 'vitest';
import { buildSpcChartModel, mergeOngoingStudyForDisplay } from './spcChartModel';
import type { SpcChartData } from '../types';

const statsData: SpcChartData = {
  schema_version: '2026.1',
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
  charts: {
    chart_type: 'xbar_s',
    subgroup_sizes: [3, 3, 3],
    sigma_within: 1,
    location: {
      statistic: 'xbar', values: [10, 11, 16],
      cl: [10, 10, 10], ucl: [15, 12, 15], lcl: [5, 8, 5],
    },
    variation: {
      statistic: 's', values: [1, 0.1, 3],
      cl: [2, 2, 2], ucl: [4, 4, 4], lcl: [0.5, 0.5, 0.5],
    },
  },
  stability: {
    evaluated: true,
    stable: false,
    rules_used: ['beyond_limits'],
    violations: [
      { index: 2, window_start: 2, window_end: 2, rule: 'beyond_limits', label: '單點超出管制界限', chart_kind: 'location' },
      { index: 1, window_start: 1, window_end: 1, rule: 'beyond_limits', label: '單點超出管制界限', chart_kind: 'variation' },
    ],
    location: {
      evaluated: true, stable: false, chart_kind: 'location', rules_used: ['beyond_limits'],
      violations: [{ index: 2, window_start: 2, window_end: 2, rule: 'beyond_limits', label: '單點超出管制界限', chart_kind: 'location' }],
    },
    variation: {
      evaluated: true, stable: false, chart_kind: 'variation', rules_used: ['beyond_limits'],
      violations: [{ index: 1, window_start: 1, window_end: 1, rule: 'beyond_limits', label: '單點超出管制界限', chart_kind: 'variation' }],
    },
  },
};

describe('buildSpcChartModel', () => {
  it('沒有統計資料時回傳空模型', () => {
    const model = buildSpcChartModel(null);

    expect(model.chartData).toBeNull();
    expect(model.ids).toEqual([]);
    expect(model.statsSummary).toBeNull();
  });

  it('直接映射後端 X-bar-S、逐點界限、違規與直方圖資料', () => {
    const model = buildSpcChartModel(statsData, { showSpecLimits: true });

    expect(model.ids).toEqual(['10', '11', '12']);
    expect(model.statsSummary).toMatchObject({
      count: 3,
      mean: '12.333',
      min: '10.000',
      max: '16.000',
    });
    expect(model.analysis?.violations.some(v => v.type === 'xbar')).toBe(true);
    expect(model.rAnalysis?.violations.some(v => v.type === 'r')).toBe(true);
    expect(model.chartType).toBe('xbar_s');
    expect(model.variationLabel).toBe('標準差 S');
    expect(model.chartData?.xBar.datasets.find(dataset => dataset.label === 'UCL')?.data)
      .toEqual([15, 12, 15]);
    expect(model.chartData?.rChart.datasets.find(dataset => dataset.label === 'LCL')?.data)
      .toEqual([0.5, 0.5, 0.5]);
    expect(model.chartData?.xBar.datasets.some(dataset => dataset.label === 'USL')).toBe(true);
    expect(model.histogramData?.bins.length).toBeGreaterThan(1);
    expect(model.cpkTrend).toHaveLength(2);
  });

  it('預設不在管制圖疊加規格界限，開啟選項才顯示', () => {
    const statsData = {
      labels: ['A', 'B', 'C', 'D', 'E'], ids: [], dates: [],
      avgs: [10, 10.1, 9.9, 10, 10.1], ranges: [0.2, 0.2, 0.2, 0.2, 0.2],
      subgroup_sizes: [], all_values: [],
      x_cl: 10, x_ucl: 10.9, x_lcl: 9.1, r_cl: 0.2, r_ucl: 0.5, r_lcl: 0,
      avg_subgroup_size: 5, tolerance: { found: true },
      process_capability: { available: true, usl: 11, lsl: 9 },
      distribution_stats: {}, cpk_trend: [],
    } as never;

    const hidden = buildSpcChartModel(statsData);
    expect(hidden.chartData!.xBar.datasets.some(d => d.label === 'USL')).toBe(false);

    const shown = buildSpcChartModel(statsData, { showSpecLimits: true });
    expect(shown.chartData!.xBar.datasets.some(d => d.label === 'USL')).toBe(true);
  });

  it('不再依前端 WECO 重算覆蓋後端判定', () => {
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
    const backendSaysStable = buildSpcChartModel({
      ...base,
      charts: {
        chart_type: 'xbar_r', subgroup_sizes: Array(9).fill(2), sigma_within: 0.1,
        location: { statistic: 'xbar', values: base.avgs, cl: Array(9).fill(10), ucl: Array(9).fill(10.9), lcl: Array(9).fill(9.1) },
        variation: { statistic: 'r', values: base.ranges, cl: Array(9).fill(0.2), ucl: Array(9).fill(0.5), lcl: Array(9).fill(0) },
      },
      stability: {
        evaluated: true, stable: true, violations: [], rules_used: ['run_9_same_side'],
        location: { evaluated: true, stable: true, violations: [], rules_used: ['run_9_same_side'], chart_kind: 'location' },
        variation: { evaluated: true, stable: true, violations: [], rules_used: ['run_9_same_side'], chart_kind: 'variation' },
      },
    } as never);
    expect(backendSaysStable.analysis!.violations).toHaveLength(0);
    expect(backendSaysStable.rAnalysis!.violations).toHaveLength(0);
  });

  it('只有後端接受常態模型時才疊加常態曲線', () => {
    const unconfirmed = buildSpcChartModel({
      ...statsData,
      distribution: {
        model: null, label: '未確認', params: [], accepted: false,
        normal_ok: false, unimodal: true, reason_code: 'UNCONFIRMED',
        candidates: [], fit_method: null, alpha: 0.05,
      },
    });
    const lognormal = buildSpcChartModel({
      ...statsData,
      distribution: {
        model: 'lognormal', label: '對數常態', params: [], accepted: true,
        normal_ok: false, unimodal: true, reason_code: null,
        candidates: [], fit_method: 'validated', alpha: 0.05,
      },
    });

    expect(unconfirmed.histogramData?.normalCurve).toEqual([]);
    expect(lognormal.histogramData?.normalCurve).toEqual([]);
  });

  it('持續監控畫面以正式研究的界限與失控判定覆蓋即時預覽', () => {
    const preview = {
      ...statsData,
      process_stream_key: 'stream-a',
      data_hash: 'same-hash',
      charts: {
        ...statsData.charts!,
        location: { ...statsData.charts!.location, ucl: [99, 99, 99] },
      },
    };
    const ongoing = {
      study_type: 'ongoing',
      process_stream_key: 'stream-a',
      data_hash: 'same-hash',
      charts: {
        ...statsData.charts!,
        location: { ...statsData.charts!.location, ucl: [11, 11, 11] },
      },
      stability: { ...statsData.stability, stable: false },
      distribution: statsData.distribution,
      time_model: statsData.time_model,
      capability: { available: false, reason: 'ongoing_monitoring' },
      applicability: statsData.applicability,
    };

    const merged = mergeOngoingStudyForDisplay(preview as never, ongoing as never);

    expect(merged?.charts?.location.ucl).toEqual([11, 11, 11]);
    expect(merged?.stability?.stable).toBe(false);
    expect(merged?.labels).toEqual(preview.labels);
  });

  it('資料雜湊改變時不把舊持續監控點值套到新預覽標籤', () => {
    const preview = {
      ...statsData,
      process_stream_key: 'stream-a',
      data_hash: 'new-hash',
    };
    const ongoing = {
      study_type: 'ongoing',
      process_stream_key: 'stream-a',
      data_hash: 'old-hash',
      charts: {
        ...statsData.charts!,
        location: { ...statsData.charts!.location, values: [99, 99, 99] },
      },
    };

    const merged = mergeOngoingStudyForDisplay(preview as never, ongoing as never);

    expect(merged).toBe(preview);
    expect(merged?.charts?.location.values).toEqual(statsData.charts?.location.values);
  });

  it('舊版空診斷 payload 不會覆蓋目前預覽的完整診斷資料', () => {
    const preview = {
      ...statsData,
      process_stream_key: 'stream-a',
      data_hash: 'same-hash',
      distribution: {
        model: 'normal', label: '常態', params: [], accepted: true,
        normal_ok: true, unimodal: true, reason_code: null,
        candidates: [], fit_method: 'validated', alpha: 0.05,
      },
      time_model: { candidate: 'A1', model: 'A1', confirmed: true, statistically_controlled: true },
    } as SpcChartData;
    const ongoing = {
      study_type: 'ongoing', process_stream_key: 'stream-a', data_hash: 'same-hash',
      charts: statsData.charts, stability: statsData.stability,
      distribution: {}, time_model: {}, capability: { available: false },
      applicability: { applicable: true },
    };

    const merged = mergeOngoingStudyForDisplay(preview, ongoing as never);

    expect(merged?.distribution).toEqual(preview.distribution);
    expect(merged?.time_model).toEqual(preview.time_model);
  });
});
