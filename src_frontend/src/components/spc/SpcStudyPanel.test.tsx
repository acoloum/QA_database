import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { SpcStudyResult } from '../../types';
import SpcStudyPanel from './SpcStudyPanel';

vi.mock('../../context/useAuth', () => ({
  useAuth: () => ({ hasPermission: () => true }),
}));

vi.mock('../../hooks/useSpcStudies', () => ({
  useAnalyzeSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useConfirmSpcTimeModel: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApproveSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRejectSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRetireSpcLimit: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSaveSpcOcap: () => ({ mutate: vi.fn(), isPending: false }),
  useSpcStudies: () => ({ data: [] }),
  useSpcStudy: () => ({ data: null }),
}));

const version = {
  id: 31,
  study_id: 9,
  version_no: 2,
  method_version: '2026.1',
  code_version: 'abc123',
  data_hash: 'a'.repeat(64),
  specification: { found: true, USL: 11, LSL: 9 },
  charts: { chart_type: 'xbar_s' },
  stability: {
    evaluated: true,
    stable: false,
    rules_used: ['beyond_limits'],
    violations: [],
    location: { evaluated: true, stable: true, rules_used: [], violations: [], chart_kind: 'location' },
    variation: { evaluated: true, stable: false, rules_used: ['beyond_limits'], violations: [], chart_kind: 'variation' },
  },
  distribution: {
    model: null,
    label: '尚未確認',
    params: [],
    accepted: false,
    normal_ok: false,
    unimodal: true,
    reason_code: 'DISTRIBUTION_UNCONFIRMED',
    candidates: [],
    fit_method: null,
    alpha: 0.05,
  },
  time_model: {
    candidate: 'B',
    confirmed: false,
    statistically_controlled: false,
  },
  capability: { available: false, reason: 'process_unstable' },
  applicability: { applicable: true, chart_type: 'xbar_s' },
  status: 'draft',
  audit_incomplete: false,
  created_by: 1,
  created_at: '2026-07-18T08:00:00Z',
  samples: [],
} as unknown as SpcStudyResult;

describe('SpcStudyPanel', () => {
  it('顯示回溯模式、時間模型候選、分布原因及兩張圖的個別穩定性', () => {
    render(
      <SpcStudyPanel
        source="shipping"
        filters={{ vendor: 'A廠', material: '6061', field: '外徑' }}
        version={version}
        onVersionChange={vi.fn()}
      />,
    );

    expect(screen.getByText('回溯研究')).toBeInTheDocument();
    expect(screen.getByText('時間模型 B')).toBeInTheDocument();
    expect(screen.getByText('分布尚未確認')).toBeInTheDocument();
    expect(screen.getByText('位置圖穩定')).toBeInTheDocument();
    expect(screen.getByText('變異圖失控')).toBeInTheDocument();
    expect(screen.queryByText(/Cp\/Cpk/)).not.toBeInTheDocument();
  });
});
