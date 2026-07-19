import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { SpcStudyResult } from '../../types';
import SpcStudyPanel from './SpcStudyPanel';

const analyzeMock = vi.hoisted(() => vi.fn());
const approveResearchMock = vi.hoisted(() => vi.fn());
const approveResearchState = vi.hoisted(() => ({ isPending: false }));
const saveOcapMock = vi.hoisted(() => vi.fn());
const resetSaveOcapMock = vi.hoisted(() => vi.fn());
const saveOcapState = vi.hoisted(() => ({ isPending: false, isError: false }));
const assigneesState = vi.hoisted(() => ({
  data: [{ id: 8, username: 'qa-user', role: 'qa_supervisor', role_name: 'QA主管' }],
}));
const fetchSpcEventMock = vi.hoisted(() => vi.fn());
const refetchStudyMock = vi.hoisted(() => vi.fn());
const useSpcStudyMock = vi.hoisted(() => vi.fn((_id: number | null) => ({
  data: null,
  refetch: refetchStudyMock,
})));
const studiesState = vi.hoisted(() => ({ value: [] as Array<Record<string, unknown>> }));

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

vi.mock('../../context/useAuth', () => ({
  useAuth: () => ({ hasPermission: () => true }),
}));

vi.mock('../../hooks/useSpcStudies', () => ({
  fetchSpcEvent: (eventId: number) => fetchSpcEventMock(eventId),
  useAnalyzeSpcStudy: () => ({ mutateAsync: analyzeMock, isPending: false }),
  useSubmitSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useConfirmSpcTimeModel: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApproveSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useApproveSpcResearch: () => ({ mutateAsync: approveResearchMock, isPending: approveResearchState.isPending }),
  useRejectSpcStudy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRetireSpcLimit: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSaveSpcOcap: () => ({
    mutate: saveOcapMock,
    reset: resetSaveOcapMock,
    isPending: saveOcapState.isPending,
    isError: saveOcapState.isError,
  }),
  useSpcAssignees: () => ({
    data: assigneesState.data, isLoading: false, isError: false,
  }),
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

const createOcapEvent = (eventId: number, studyVersionId = version.id) => {
  const ocap = {
    id: eventId - 78,
    event_id: eventId,
    investigation_6m: { summary: '舊原因' },
    remeasurement: null,
    process_adjustment: '舊調整',
    product_disposition: null,
    owner_id: 8,
    effectiveness: null,
    status: 'open',
    created_by: 1,
    updated_by: 1,
    created_at: '2026-07-19T01:00:00Z',
    updated_at: '2026-07-19T01:00:00Z',
  };
  return {
    id: eventId,
    limit_version_id: 8,
    study_version_id: studyVersionId,
    sample_id: null,
    chart_kind: 'variation' as const,
    rule_code: 'beyond_limits',
    point_index: 4,
    observed_value: 0.8,
    status: 'investigating',
    created_at: '2026-07-19T00:00:00Z',
    ocap,
  };
};

const createOngoingVersion = ({
  studyId = 9,
  versionId = 32,
  stream = 'stream-a',
  eventIds = [81],
}: {
  studyId?: number;
  versionId?: number;
  stream?: string;
  eventIds?: number[];
} = {}) => {
  const events = eventIds.map(eventId => createOcapEvent(eventId, versionId));
  const limit = {
    id: 8,
    study_version_id: versionId,
    revision: 1,
    chart_type: 'xbar_s' as const,
    limits: {},
    status: 'active' as const,
    approved_by: 1,
    approved_at: '2026-07-18',
    events,
  };
  return {
    ...version,
    id: versionId,
    study_id: studyId,
    study_type: 'ongoing',
    process_stream_key: stream,
    status: 'active',
    data_hash: `${stream}-hash`,
    monitoring_limit: limit,
    limit_versions: [limit],
  } as SpcStudyResult;
};

describe('SpcStudyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    approveResearchMock.mockReset();
    approveResearchState.isPending = false;
    saveOcapMock.mockReset();
    resetSaveOcapMock.mockReset();
    fetchSpcEventMock.mockReset();
    refetchStudyMock.mockReset();
    useSpcStudyMock.mockReset();
    saveOcapState.isPending = false;
    saveOcapState.isError = false;
    studiesState.value = [];
    refetchStudyMock.mockResolvedValue({ data: null });
    fetchSpcEventMock.mockResolvedValue(createOcapEvent(81));
    useSpcStudyMock.mockImplementation(() => ({
      data: null,
      refetch: refetchStudyMock,
    }));
  });

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
    expect(screen.getByText('AIAG & VDA SPC · 2026.1')).toBeInTheDocument();
  });

  it('SpcStudyPanel 的舊版 A1 候選不可繞過唯讀限制開啟確認 modal', () => {
    const legacyCandidate = {
      ...version,
      time_model: { candidate: 'A1', confirmed: false, statistically_controlled: false },
    } as SpcStudyResult;
    render(<SpcStudyPanel source="shipping" filters={legacyCandidate.filters} preview={{ process_stream_key: 'stream-a' } as never} version={legacyCandidate} onVersionChange={vi.fn()} />);

    expect(screen.queryByRole('button', { name: '確認 A1' })).not.toBeInTheDocument();
    expect(screen.getByText('舊版方法僅供歷史送審與核准，不可重新確認時間模型。')).toBeInTheDocument();
  });

  it.each(['B', 'C3', 'D'] as const)('已確認 %s 研究可從既有面板呼叫研究核准並更新結果', async model => {
    const researchVersion = {
      ...version,
      method_version: '2026.2',
      analysis_family: 'variable',
      status: 'submitted',
      charts: null,
      time_model: {
        candidate: model, model, system_candidate: model,
        confirmed: true, statistically_controlled: false,
        confirmed_by: 2, confirmed_at: '2026-07-19T10:00:00Z',
        confirmation_reason: '已核對時間證據',
      },
    } as SpcStudyResult;
    const approvedVersion = { ...researchVersion, status: 'approved' as const };
    approveResearchMock.mockResolvedValue(approvedVersion);
    const onVersionChange = vi.fn();
    render(<SpcStudyPanel source="shipping" filters={researchVersion.filters} preview={{ process_stream_key: 'stream-a' } as never} version={researchVersion} onVersionChange={onVersionChange} />);

    expect(screen.getByText('AIAG & VDA SPC · 2026.2')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '核准研究結果' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('核准理由'), { target: { value: '已複核研究證據' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '核准研究結果' }));

    await waitFor(() => expect(approveResearchMock).toHaveBeenCalledWith({
      versionId: researchVersion.id,
      studyId: researchVersion.study_id,
      reason: '已複核研究證據',
    }));
    expect(onVersionChange).toHaveBeenCalledWith(expect.objectContaining({ status: 'approved', samples: researchVersion.samples }));
    expect(screen.queryByText(/Cp\/Cpk/)).not.toBeInTheDocument();
  });

  it('研究核准處理中時鎖定 modal，避免重複送出', () => {
    approveResearchState.isPending = true;
    const researchVersion = {
      ...version, method_version: '2026.2', analysis_family: 'variable', status: 'submitted', charts: null,
      time_model: { candidate: 'B', model: 'B', confirmed: true, statistically_controlled: false },
    } as SpcStudyResult;
    render(<SpcStudyPanel source="shipping" filters={researchVersion.filters} preview={{ process_stream_key: 'stream-a' } as never} version={researchVersion} onVersionChange={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: '核准研究結果' }));

    expect(within(screen.getByRole('dialog')).getByRole('button', { name: '處理中…' })).toBeDisabled();
  });

  it('研究核准失敗時顯示錯誤並重新取得研究，不能靜默留在過期狀態', async () => {
    const researchVersion = {
      ...version, method_version: '2026.2', analysis_family: 'variable', status: 'submitted', charts: null,
      time_model: { candidate: 'C3', model: 'C3', confirmed: true, statistically_controlled: false },
    } as SpcStudyResult;
    approveResearchMock.mockRejectedValue(new Error('研究版本已變更'));
    refetchStudyMock.mockResolvedValue({ data: null });
    const onVersionChange = vi.fn();
    render(<SpcStudyPanel source="shipping" filters={researchVersion.filters} preview={{ process_stream_key: 'stream-a' } as never} version={researchVersion} onVersionChange={onVersionChange} />);

    fireEvent.click(screen.getByRole('button', { name: '核准研究結果' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('核准理由'), { target: { value: '已複核研究證據' } });
    fireEvent.click(within(dialog).getByRole('button', { name: '核准研究結果' }));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('研究版本已變更'));
    expect(refetchStudyMock).toHaveBeenCalledTimes(1);
    expect(onVersionChange).toHaveBeenCalledWith(null);
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

  it('已顯示持續版本時 detail query 觀察該版本的研究', () => {
    const ongoing = createOngoingVersion();
    studiesState.value = [{
      id: 11,
      source: 'shipping',
      study_type: 'retrospective',
      process_stream_key: 'stream-a',
    }];

    render(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={vi.fn()}
      />,
    );

    expect(useSpcStudyMock).toHaveBeenLastCalledWith(ongoing.study_id);
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

  it('OCAP 儲存後先本地更新，再以輕量事件 API 校正伺服器狀態', async () => {
    const ongoing = createOngoingVersion();
    const oldOcap = ongoing.monitoring_limit?.events[0].ocap;
    const newOcap = {
      ...oldOcap,
      process_adjustment: '新調整',
      effectiveness: '連續三批未再發生',
      status: 'closed',
      updated_at: '2026-07-19T02:00:00Z',
    };
    const serverOcap = { ...newOcap, process_adjustment: '伺服器正規化調整' };
    const serverEvent = {
      ...ongoing.monitoring_limit?.events[0],
      status: 'closed',
      ocap: serverOcap,
    };
    fetchSpcEventMock.mockResolvedValue(serverEvent);
    const onVersionChange = vi.fn();
    saveOcapMock.mockImplementation((_input, options) => {
      void options.onSuccess(newOcap);
    });
    render(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={onVersionChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
    expect(screen.getByLabelText('製程調整')).toHaveValue('舊調整');
    fireEvent.click(screen.getByLabelText('結案'));
    fireEvent.change(screen.getByLabelText('有效性確認'), {
      target: { value: '連續三批未再發生' },
    });
    fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));

    await waitFor(() => expect(fetchSpcEventMock).toHaveBeenCalledWith(81));
    expect(refetchStudyMock).not.toHaveBeenCalled();
    await waitFor(() => expect(onVersionChange).toHaveBeenCalledTimes(2));
    const localVersion = onVersionChange.mock.calls[0][0] as SpcStudyResult;
    expect(localVersion.monitoring_limit?.events[0].status).toBe('closed');
    expect(localVersion.limit_versions?.[0].events[0].status).toBe('closed');
    expect(localVersion.monitoring_limit?.events[0].ocap?.process_adjustment).toBe('新調整');
    expect(ongoing.monitoring_limit?.events[0].status).toBe('investigating');
    const reconciledVersion = onVersionChange.mock.calls[1][0] as SpcStudyResult;
    expect(reconciledVersion.monitoring_limit?.events[0]).toEqual(serverEvent);
    expect(reconciledVersion.limit_versions?.[0].events[0]).toEqual(serverEvent);
  });

  it('輕量事件校正失敗時只保留本地 OCAP 成功結果', async () => {
    const ongoing = createOngoingVersion();
    const newOcap = {
      ...ongoing.monitoring_limit?.events[0].ocap,
      process_adjustment: '新調整',
      updated_at: '2026-07-19T02:00:00Z',
    };
    fetchSpcEventMock.mockRejectedValue(new Error('event refresh failed'));
    const onVersionChange = vi.fn();
    saveOcapMock.mockImplementation((_input, options) => {
      void options.onSuccess(newOcap);
    });
    render(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={onVersionChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
    fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));

    await waitFor(() => expect(fetchSpcEventMock).toHaveBeenCalledTimes(1));
    expect(refetchStudyMock).not.toHaveBeenCalled();
    await waitFor(() => expect(onVersionChange).toHaveBeenCalledTimes(1));
    const localVersion = onVersionChange.mock.calls[0][0] as SpcStudyResult;
    expect(localVersion.monitoring_limit?.events[0].ocap?.process_adjustment).toBe('新調整');
  });

  it('儲存 A 期間選取另一事件後，A 的延遲成功不回寫或關閉 B', async () => {
    const ongoing = createOngoingVersion({ eventIds: [81, 82] });
    const onVersionChange = vi.fn();
    let delayedSuccess: ((ocap: unknown) => unknown) | undefined;
    saveOcapMock.mockImplementation((_input, options) => {
      delayedSuccess = options.onSuccess;
    });
    const view = render(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={onVersionChange}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
    fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));
    saveOcapState.isPending = true;
    view.rerender(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={onVersionChange}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /事件 #82/ }));
    onVersionChange.mockClear();

    await act(async () => {
      await delayedSuccess?.({
        ...createOcapEvent(81).ocap,
        process_adjustment: 'A 延遲結果',
      });
    });

    expect(onVersionChange).not.toHaveBeenCalled();
    expect(screen.getByText('失控反應計畫 · 事件 #82')).toBeInTheDocument();
    expect(fetchSpcEventMock).not.toHaveBeenCalled();
  });

  it('儲存 A 期間切換研究版本後，A 的延遲成功不回寫舊版本', async () => {
    const ongoingA = createOngoingVersion();
    const ongoingB = createOngoingVersion({
      studyId: 10,
      versionId: 33,
      stream: 'stream-b',
    });
    const onVersionChange = vi.fn();
    let delayedSuccess: ((ocap: unknown) => unknown) | undefined;
    saveOcapMock.mockImplementation((_input, options) => {
      delayedSuccess = options.onSuccess;
    });
    const view = render(
      <SpcStudyPanel
        source="shipping"
        filters={ongoingA.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoingA}
        onVersionChange={onVersionChange}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
    fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));

    view.rerender(
      <SpcStudyPanel
        source="shipping"
        filters={ongoingB.filters}
        preview={{ process_stream_key: 'stream-b', data_hash: 'stream-b-hash' } as never}
        version={ongoingB}
        onVersionChange={onVersionChange}
      />,
    );
    onVersionChange.mockClear();
    await act(async () => {
      await delayedSuccess?.({
        ...createOcapEvent(81).ocap,
        process_adjustment: 'A 延遲結果',
      });
    });

    expect(onVersionChange).not.toHaveBeenCalled();
    expect(fetchSpcEventMock).not.toHaveBeenCalled();
  });

  it('關閉失敗的 OCAP 後 reset，重新開啟不顯示前一筆錯誤', () => {
    const ongoing = createOngoingVersion();
    resetSaveOcapMock.mockImplementation(() => {
      saveOcapState.isError = false;
    });
    const view = render(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
    saveOcapState.isError = true;
    view.rerender(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/OCAP 儲存失敗/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));

    expect(resetSaveOcapMock).toHaveBeenCalled();
    expect(screen.queryByText(/OCAP 儲存失敗/)).not.toBeInTheDocument();
  });

  it('選取另一事件時 reset 前一筆 mutation 狀態', () => {
    const ongoing = createOngoingVersion({ eventIds: [81, 82] });
    render(
      <SpcStudyPanel
        source="shipping"
        filters={ongoing.filters}
        preview={{ process_stream_key: 'stream-a', data_hash: 'stream-a-hash' } as never}
        version={ongoing}
        onVersionChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
    resetSaveOcapMock.mockClear();

    fireEvent.click(screen.getByRole('button', { name: /事件 #82/ }));

    expect(resetSaveOcapMock).toHaveBeenCalledTimes(1);
  });
});
