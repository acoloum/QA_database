import { describe, expect, it } from 'vitest';

import {
  percentile,
  probabilityPlotPoints,
  reportModelFromStats,
  reportModelFromVersion,
} from './spcReportModel';
import type { SpcChartData, SpcChartSet, SpcStudyResult, ProcessCapability } from '../../../types';

const chartSet: SpcChartSet = {
  chart_type: 'i_mr',
  location: { statistic: 'individual', values: [10, 12, 11, 13], cl: [11.5, 11.5, 11.5, 11.5], ucl: [15, 15, 15, 15], lcl: [8, 8, 8, 8] },
  variation: { statistic: 'mr', values: [null, 2, 1, 2], cl: [1.6, 1.6, 1.6, 1.6], ucl: [5, 5, 5, 5], lcl: [0, 0, 0, 0] },
  subgroup_sizes: [1, 1, 1, 1],
  sigma_within: 1.5,
};

const capability: ProcessCapability = {
  available: true, lsl: 8, one_sided: 'lower', ppk: 0.9, ppl: 0.9,
  applicable: 'performance', method: 'G',
  ppm: { upper: null, lower: 5000, total: 5000 },
  targets: { pk_target: 1.0 } as ProcessCapability['targets'],
  achieved: false,
};

const stats: SpcChartData = {
  labels: ['a', 'b', 'c', 'd'], ids: ['1', '2', '3', '4'],
  dates: ['2026-06-01', '2026-06-03', '2026-06-02', ''],
  avgs: [10, 12, 11, 13], ranges: [null, 2, 1, 2], subgroup_sizes: [1, 1, 1, 1],
  all_values: [10, 12, 11, 13],
  x_cl: null, x_ucl: null, x_lcl: null, r_cl: null, r_ucl: null, r_lcl: null,
  avg_subgroup_size: 1,
  tolerance: { found: true, LSL: 8 },
  process_capability: capability,
  distribution_stats: {},
  cpk_trend: [],
  charts: chartSet,
  capability,
  distribution: { model: 'normal', label: '常態分布', params: [], accepted: true, normal_ok: true, unimodal: true, reason_code: null, candidates: [], fit_method: null, alpha: 0.05 },
};

describe('spcReportModel', () => {
  it('percentile 以線性內插計算', () => {
    expect(percentile([1, 2, 3, 4], 50)).toBe(2.5);
    expect(percentile([5], 99)).toBe(5);
    expect(percentile([], 50)).toBeNull();
  });

  it('機率圖點依觀測值排序且理論分位數遞增', () => {
    const pts = probabilityPlotPoints([13, 10, 12, 11]);
    expect(pts.map((p) => p.y)).toEqual([10, 11, 12, 13]);
    for (let i = 1; i < pts.length; i += 1) {
      expect(pts[i].x).toBeGreaterThan(pts[i - 1].x);
    }
  });

  it('reportModelFromStats 對機械性質映射識別、規格、能力與位置估計', () => {
    const model = reportModelFromStats('mechanical', {
      vendor_id: '2', material: '6061-T651', product_size: '66.7*59', item: '抗拉強度', position: '爐門',
    }, stats);

    expect(model.identity.find((f) => f.label === '材質')?.value).toBe('6061-T651');
    expect(model.identity.find((f) => f.label === '特性 / 位置')?.value).toBe('抗拉強度（爐門）');
    expect(model.specLimits.lsl).toBe(8);
    expect(model.specLimits.oneSided).toBe('lower');
    // 不穩定 → 績效指標 Pp/Ppk
    expect(model.applicableLabel).toContain('績效');
    expect(model.locationEstimate).toBe(11.5); // median of 10,11,12,13
    expect(model.sampleInfo.n).toBe(4);
    expect(model.conclusion).toContain('未達標');
    expect(model.chartModel.chartData).not.toBeNull();
  });

  it('能力未計算但規格快照存在時，規格界限仍由 tolerance 顯示', () => {
    const gatedStats: SpcChartData = {
      ...stats,
      capability: { available: false } as ProcessCapability,
      process_capability: { available: false } as ProcessCapability,
      tolerance: { found: true, LSL: 350, one_sided: 'lower' } as SpcChartData['tolerance'],
    };
    const model = reportModelFromStats('mechanical', { item: '抗拉強度', position: '爐門' }, gatedStats);
    expect(model.specLimits.lsl).toBe(350);
    expect(model.specLimits.oneSided).toBe('lower');
  });

  it('reportModelFromVersion 由 samples 還原原始值並映射', () => {
    const version = {
      source: 'mechanical', study_type: 'retrospective', created_at: '2026-07-01T00:00:00Z',
      filters: { material: '6061-T651', product_size: '66.7*59', item: '抗拉強度', position: '爐門' },
      charts: chartSet, capability, specification: { found: true, LSL: 8 },
      stability: { stable: false }, distribution: { model: 'normal', label: '常態分布', accepted: true },
      applicability: { applicable: false },
      samples: [
        { id: 1, key: 'a', order: 0, timestamp: '2026-06-01', values: [10], distribution_values: [10], record_ids: [1], measurement_ids: [], exclusion_snapshot: [] },
        { id: 2, key: 'b', order: 1, timestamp: '2026-06-02', values: [12], distribution_values: [12], record_ids: [2], measurement_ids: [], exclusion_snapshot: [] },
      ],
    } as unknown as SpcStudyResult;

    const model = reportModelFromVersion(version);
    expect(model.sampleInfo.n).toBe(2);
    expect(model.runChart).toEqual([10, 12]);
    expect(model.remarks).toContain('回溯研究');
    expect(model.studyDate).toBe('2026-07-01');
  });
});
