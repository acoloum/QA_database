import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { SpcChartSet, SpcStudyResult } from '../../types';
import SpcBaselineApprovalModal from './SpcBaselineApprovalModal';

const xbarCharts: SpcChartSet = {
  chart_type: 'xbar_r',
  subgroup_sizes: [2, 2],
  sigma_within: 0.2,
  location: { statistic: 'xbar', values: [10, 10.1], cl: [10, 10], ucl: [10.5, 10.5], lcl: [9.5, 9.5] },
  variation: { statistic: 'r', values: [0.2, 0.1], cl: [0.2, 0.2], ucl: [0.5, 0.5], lcl: [0, 0] },
};

const version: SpcStudyResult = {
  id: 12,
  study_id: 5,
  source: 'shipping',
  study_type: 'retrospective',
  process_stream_key: 'stream-a',
  filters: { vendor: 'A廠', material: '6061', field: '外徑' },
  version_no: 3,
  data_hash: '1234567890abcdef'.repeat(4),
  method_version: '2026.1',
  code_version: 'build-77',
  charts: xbarCharts,
  samples: [
    { id: 1, key: 'A', order: 0, timestamp: '2026-07-01', values: [9.9, 10.1], distribution_values: [9.9, 10.1], record_ids: [101], measurement_ids: [1001, 1002], exclusion_snapshot: [] },
    { id: 2, key: 'B', order: 1, timestamp: '2026-07-02', values: [10, 10.2], distribution_values: [10, 10.2], record_ids: [102], measurement_ids: [1003, 1004], exclusion_snapshot: [] },
  ],
  specification: { found: true, USL: 11, LSL: 9 },
  stability: { evaluated: true, stable: true, rules_used: [], violations: [] },
  distribution: { model: 'normal', label: '常態分布', params: [], accepted: true, normal_ok: true, unimodal: true, reason_code: null, candidates: [], fit_method: 'AD', alpha: 0.05 },
  time_model: { candidate: 'A1', model: 'A1', confirmed: true, statistically_controlled: true },
  capability: { available: true, cp: 1.5, cpk: 1.4 },
  applicability: { applicable: true },
  status: 'submitted', audit_incomplete: false, created_by: 1, created_at: '2026-07-18',
};

describe('SpcBaselineApprovalModal', () => {
  it('核准前揭露篩選、來源、雜湊、時間範圍、子組與界限，且理由必填', () => {
    const onConfirm = vi.fn();
    render(
      <SpcBaselineApprovalModal
        show
        action="approve"
        source="shipping"
        filters={{ vendor: 'A廠', material: '6061', field: '外徑' }}
        version={version}
        onHide={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByText('A廠')).toBeInTheDocument();
    expect(screen.getByText('101、102')).toBeInTheDocument();
    expect(screen.getByText(version.data_hash)).toBeInTheDocument();
    expect(screen.getByText('2026-07-01 ～ 2026-07-02')).toBeInTheDocument();
    expect(screen.getByText('2 組／4 筆量測')).toBeInTheDocument();
    expect(screen.getByText(/10\.500/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '核准並生效' })).toBeDisabled();

    fireEvent.change(screen.getByLabelText('核准理由'), { target: { value: '基準資料與製程條件已複核' } });
    fireEvent.click(screen.getByRole('button', { name: '核准並生效' }));
    expect(onConfirm).toHaveBeenCalledWith('基準資料與製程條件已複核');
  });

  it('不等子組時逐一揭露每個 n 對應的核准界限', () => {
    const unequal = {
      ...version,
      charts: {
        ...xbarCharts,
        subgroup_sizes: [3, 5],
        location: { ...xbarCharts.location, ucl: [10.7, 10.5], cl: [10, 10], lcl: [9.3, 9.5] },
        variation: { ...xbarCharts.variation, ucl: [0.8, 0.6], cl: [0.3, 0.25], lcl: [0.02, 0.05] },
      },
    } as SpcStudyResult;

    render(
      <SpcBaselineApprovalModal
        show
        action="approve"
        source="shipping"
        filters={unequal.filters}
        version={unequal}
        onHide={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByText('n=3')).toBeInTheDocument();
    expect(screen.getByText('n=5')).toBeInTheDocument();
    expect(screen.getByText(/10\.700/)).toBeInTheDocument();
    expect(screen.getByText(/10\.500/)).toBeInTheDocument();
  });

  it('機器研究核准時揭露保存的固定條件與確認理由，且不顯示生效界限', () => {
    const machineVersion: SpcStudyResult = {
      ...version,
      source: 'patrol', analysis_family: 'machine', charts: null,
      filters: { m_id: 7, mat: '6061', spec: '10x1', item: '外徑', pos: 'A' },
      options: { conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態' },
      capability: {
        available: true, approvable: true, preliminary: false, index_family: 'machine', method: 'G', n: 60, reason_code: null,
        distribution: { model: 'normal', label: '常態分布', accepted: true, reason_code: null },
        quantiles: { q_0_135: 9.7, q_50: 10, q_99_865: 10.3 }, usl: 11, lsl: 9,
        pm: 3.33, pmu: 3.33, pml: 3.33, pmk: 3.33, targets: { class: '關鍵', pm: 2.33, pmk: 2 },
        evidence: { source_semantics: 'patrol_min_max_observations', operators: [8], record_ids: [101], detail_ids: [1001], date_span: { start: '2026-07-01', end: '2026-07-02' }, conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態' },
      },
      status: 'submitted',
    };
    render(<SpcBaselineApprovalModal show action="approve-research" source="patrol" filters={machineVersion.filters} version={machineVersion} onHide={vi.fn()} onConfirm={vi.fn()} />);

    expect(screen.getByText('核准機器研究結果')).toBeInTheDocument();
    expect(screen.getByText('已確認機台設定與治具狀態')).toBeInTheDocument();
    expect(screen.getByText('patrol_min_max_observations')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '核准研究結果' })).toBeInTheDocument();
    expect(screen.queryByText('位置 UCL')).not.toBeInTheDocument();
  });
});
