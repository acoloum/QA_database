import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { SpcStudyResult } from '../../types';
import SpcStudyPanel from './SpcStudyPanel';

const analyzeMock = vi.hoisted(() => vi.fn());
const useSpcStudyMock = vi.hoisted(() => vi.fn((_id: number | null) => ({ data: null })));
const studiesState = vi.hoisted(() => ({ value: [] as Array<Record<string, unknown>> }));

vi.mock('../../context/useAuth', () => ({
  useAuth: () => ({ hasPermission: () => true }),
}));

vi.mock('../../hooks/useSpcStudies', () => ({
  useAnalyzeSpcStudy: () => ({ mutateAsync: analyzeMock, isPending: false }),
  useSubmitSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useConfirmSpcTimeModel: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApproveSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRejectSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRetireSpcLimit: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSaveSpcOcap: () => ({ mutate: vi.fn(), isPending: false }),
  useSpcStudies: () => ({ data: studiesState.value }),
  useSpcStudy: (id: number | null) => useSpcStudyMock(id),
}));

const version = {
  id: 31,
  study_id: 9,
  source: 'shipping',
  study_type: 'retrospective',
  process_stream_key: 'stream-a',
  filters: { vendor: 'A廠', field: '外徑' },
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
        preview={{ process_stream_key: 'stream-a' } as never}
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

  it('切換製程流後立即清除舊版本，避免在新篩選操作舊研究', async () => {
    const onVersionChange = vi.fn();
    render(
      <SpcStudyPanel
        source="shipping"
        filters={{ vendor: 'B廠', material: '6061', field: '外徑' }}
        preview={{ process_stream_key: 'stream-b' } as never}
        version={version}
        onVersionChange={onVersionChange}
      />,
    );

    expect(screen.queryByText('研究 v2')).not.toBeInTheDocument();
    await waitFor(() => expect(onVersionChange).toHaveBeenCalledWith(null));
  });

  it('預覽尚無製程流時清除舊版本並停用舊研究操作', async () => {
    const onVersionChange = vi.fn();
    render(
      <SpcStudyPanel
        source="shipping"
        filters={{}}
        preview={null}
        version={version}
        onVersionChange={onVersionChange}
      />,
    );

    expect(screen.queryByText('研究 v2')).not.toBeInTheDocument();
    await waitFor(() => expect(onVersionChange).toHaveBeenCalledWith(null));
  });

  it('重新載入時只選取回溯研究，不讓持續監控遮蔽基準管理', () => {
    studiesState.value = [
      { id: 22, source: 'shipping', study_type: 'ongoing', process_stream_key: 'stream-a' },
      { id: 11, source: 'shipping', study_type: 'retrospective', process_stream_key: 'stream-a' },
    ];

    render(
      <SpcStudyPanel
        source="shipping"
        filters={{}}
        preview={{ process_stream_key: 'stream-a' } as never}
        version={null}
        onVersionChange={vi.fn()}
      />,
    );

    expect(useSpcStudyMock).toHaveBeenCalledWith(11);
    studiesState.value = [];
  });

  it('生效基準可直接啟動持續 SPC 並使用正式界限', async () => {
    analyzeMock.mockResolvedValue({ ...version, id: 32, study_type: 'ongoing' });
    const activeVersion = {
      ...version,
      status: 'active',
      limit_versions: [{
        id: 8, study_version_id: version.id, revision: 1,
        chart_type: 'xbar_s', limits: {}, status: 'active',
        approved_by: 1, approved_at: '2026-07-18', events: [],
      }],
    } as SpcStudyResult;
    render(
      <SpcStudyPanel
        source="shipping"
        filters={version.filters}
        preview={{ process_stream_key: 'stream-a' } as never}
        version={activeVersion}
        onVersionChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '以正式界限監控目前資料' }));

    await waitFor(() => expect(analyzeMock).toHaveBeenCalledWith({
      source: 'shipping', filters: version.filters, study_type: 'ongoing',
    }));
  });

  it('持續監控後可直接返回回溯基準流程', () => {
    const onVersionChange = vi.fn();
    const ongoingVersion = {
      ...version,
      id: 32,
      study_type: 'ongoing',
      status: 'active',
      data_hash: 'current-hash',
    } as SpcStudyResult;
    render(
      <SpcStudyPanel
        source="shipping"
        filters={version.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'current-hash' } as never}
        version={ongoingVersion}
        onVersionChange={onVersionChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '返回回溯基準' }));

    expect(onVersionChange).toHaveBeenCalledWith(null);
  });
});
