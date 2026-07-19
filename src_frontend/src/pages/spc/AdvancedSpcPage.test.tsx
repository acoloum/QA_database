import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authMock = vi.hoisted(() => vi.fn());
const analyzeMock = vi.hoisted(() => vi.fn());
const approveResearchMock = vi.hoisted(() => vi.fn());
const submitMock = vi.hoisted(() => vi.fn());
const confirmTimeMock = vi.hoisted(() => vi.fn());
const confirmTransformationMock = vi.hoisted(() => vi.fn());

const savedAttributeVersion = {
  id: 51, study_id: 9, source: 'shipping', study_type: 'retrospective', analysis_family: 'attribute',
  process_stream_key: 'attribute-stream', filters: { vendor: '保存廠商', material: '6061', spec: '10x1', field: '外徑' },
  options: { interval: 'day', chart_type: 'p' }, version_no: 1, method_version: '2026.2', code_version: null,
  data_hash: 'a'.repeat(64), specification: { found: true }, charts: null, stability: { evaluated: false, stable: null, violations: [], rules_used: [] },
  distribution: { model: null, label: '不適用', params: [], accepted: false, normal_ok: false, unimodal: false, reason_code: 'attribute_chart', candidates: [], fit_method: null, alpha: 0.05 },
  time_model: { candidate: null, confirmed: false, statistically_controlled: false }, capability: { available: false },
  applicability: { applicable: false, message: '測試' }, status: 'draft', audit_incomplete: false, created_by: 1, created_at: '2026-07-19',
};

const transformationCandidate = {
  model: 'johnson_su', label: 'Johnson SU', params: { a: 1, b: 2, loc: 3, scale: 4 }, epsilon: 2.22e-16,
  fit_method: 'johnson_su_mle', ad_statistic: 0.2, ad_p_value: 0.4, tail_quantiles: [1, 2, 3],
  monotonic: true, roundtrip_relative_error: 1e-12, accepted: true, reason_code: null, rank: 1,
};
const savedVariableVersion = {
  ...savedAttributeVersion, id: 61, study_id: 10, analysis_family: 'variable', process_stream_key: 'variable-stream',
  charts: { chart_type: 'xbar_s', location: { statistic: 'xbar', values: [1], cl: [1], ucl: [2], lcl: [0] }, variation: { statistic: 's', values: [0.1], cl: [0.1], ucl: [0.2], lcl: [0] }, subgroup_sizes: [3], sigma_within: 0.1 },
  distribution: { model: null, label: '分布模型未確認', params: [], accepted: false, normal_ok: false, unimodal: true, reason_code: 'DISTRIBUTION_UNCONFIRMED', candidates: [], fit_method: null, alpha: 0.05, scale: 'original', transformation_candidates: [transformationCandidate], transformation_recommendation: transformationCandidate },
  time_model: { candidate: 'C3', candidate_options: ['A1', 'A2', 'B', 'C1', 'C2', 'C3', 'C4', 'D'], confirmed: false, statistically_controlled: false, diagnostic_version: '2026.2', evidence: { subgroup_count: 30 } },
};

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useSpcStudies', () => ({
  useAnalyzeSpcStudy: () => ({ mutateAsync: analyzeMock, isPending: false, isError: false }),
  useSubmitSpcStudy: () => ({ mutateAsync: submitMock, isPending: false }), useApproveSpcStudy: () => ({ isPending: false }),
  useApproveSpcResearch: () => ({ mutateAsync: approveResearchMock, isPending: false }),
  useConfirmSpcTimeModel: () => ({ mutateAsync: confirmTimeMock, isPending: false }),
  useConfirmSpcTransformation: () => ({ mutateAsync: confirmTransformationMock, isPending: false }),
  useRejectSpcStudy: () => ({ isPending: false }), useRetireSpcLimit: () => ({ isPending: false }),
}));
vi.mock('../../components/spc/SpcStudyWorkflowBar', () => ({
  default: (props: { onAction: (action: 'submit' | 'approve-research') => void; onAnalyze: () => void }) => <><button onClick={() => props.onAction('submit')}>開啟送審</button><button onClick={() => props.onAction('approve-research')}>開啟研究核准</button><button onClick={props.onAnalyze}>重建候選</button></>,
}));
vi.mock('../../components/spc/SpcBaselineApprovalModal', () => ({
  default: (props: { filters: Record<string, unknown>; onConfirm: (reason: string) => void }) => <div>核准快照廠商：{String(props.filters.vendor)}<button onClick={() => props.onConfirm('已完成研究複核')}>確認流程</button></div>,
}));
vi.mock('../../components/spc/SpcStudyHistoryOffcanvas', () => ({ default: () => null }));

import AdvancedSpcPage from './AdvancedSpcPage';

const renderPage = (entry: string) => render(
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={[entry]}><AdvancedSpcPage /></MemoryRouter>
  </QueryClientProvider>,
);

describe('AdvancedSpcPage', () => {
  beforeEach(() => {
    analyzeMock.mockReset();
    submitMock.mockReset();
    authMock.mockReset();
    confirmTimeMock.mockReset();
    confirmTransformationMock.mockReset();
  });

  it('從 query 載入出貨屬性研究條件', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    renderPage('/spc/advanced?family=attribute&source=shipping&vendor=甲&start_date=2026-07-01&end_date=2026-07-02');

    expect(screen.getByRole('heading', { name: '進階 SPC 分析' })).toBeInTheDocument();
    expect(screen.getByLabelText('資料來源')).toHaveValue('shipping');
    expect(screen.getByLabelText('廠商')).toHaveValue('甲');
    expect(screen.getByLabelText('開始日期')).toHaveValue('2026-07-01');
    expect(screen.getByLabelText('結束日期')).toHaveValue('2026-07-02');
    expect(screen.getByLabelText('分析族別')).toHaveValue('attribute');
  });

  it('machine query 強制巡檢來源並忽略不正確的篩選型別', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    renderPage('/spc/advanced?family=machine&source=unknown&interval=year&chart_type=xbar_r&vendor=1&m_id=oops');

    expect(screen.getByLabelText('分析族別')).toHaveValue('machine');
    expect(screen.queryByLabelText('資料來源')).not.toBeInTheDocument();
    expect(screen.getByLabelText('機台 ID')).toHaveValue('');
    expect(screen.getByText(/資料來源固定為現場巡檢/)).toBeInTheDocument();
  });

  it('分析成功後即使改變表單，送審仍使用保存版本的篩選快照', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue(savedAttributeVersion);
    renderPage('/spc/advanced?source=shipping&vendor=分析前廠商');

    fireEvent.click(screen.getByRole('button', { name: '建立屬性研究' }));
    await screen.findByRole('button', { name: '開啟送審' });
    fireEvent.change(screen.getByLabelText('廠商'), { target: { value: '分析後變更廠商' } });
    fireEvent.click(screen.getByRole('button', { name: '開啟送審' }));

    expect(screen.getByText('核准快照廠商：保存廠商')).toBeInTheDocument();
  });

  it('出貨研究只送出出貨白名單篩選與日期', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue(savedAttributeVersion);
    renderPage('/spc/advanced?source=shipping&vendor=甲&material=6061&spec=10x1&item=外徑&start_date=2026-07-01&end_date=2026-07-31&m_id=99');
    fireEvent.click(screen.getByRole('button', { name: '建立屬性研究' }));

    await screen.findByRole('button', { name: '開啟送審' });
    expect(analyzeMock).toHaveBeenCalledWith(expect.objectContaining({
      source: 'shipping',
      filters: { vendor: '甲', material: '6061', spec: '10x1', field: '外徑', start_date: '2026-07-01', end_date: '2026-07-31' },
    }));
  });

  it('巡檢研究只送出巡檢白名單篩選與機台操作員日期', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue({ ...savedAttributeVersion, source: 'patrol' });
    renderPage('/spc/advanced?source=patrol&customer=3&material=6063&spec=8x1&item=厚度&position=A&m_id=7&op_id=9&s_date=2026-07-01&e_date=2026-07-31&vendor=不送出');
    fireEvent.click(screen.getByRole('button', { name: '建立屬性研究' }));

    await screen.findByRole('button', { name: '開啟送審' });
    expect(analyzeMock).toHaveBeenCalledWith(expect.objectContaining({
      source: 'patrol',
      filters: { cust_id: '3', mat: '6063', spec: '8x1', item: '厚度', pos: 'A', s_date: '2026-07-01', e_date: '2026-07-31', m_id: '7', op_id: '9' },
    }));
  });

  it('瀏覽器返回或前進改變 searchParams 時同步表單，不保留舊 state', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    window.history.replaceState({}, '', '/spc/advanced?source=shipping&vendor=甲');
    render(<QueryClientProvider client={new QueryClient()}><BrowserRouter><AdvancedSpcPage /></BrowserRouter></QueryClientProvider>);
    expect(screen.getByLabelText('廠商')).toHaveValue('甲');

    act(() => {
      window.history.pushState({}, '', '/spc/advanced?source=patrol&m_id=7&op_id=9&s_date=2026-07-01&e_date=2026-07-31');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    expect(screen.getByLabelText('資料來源')).toHaveValue('patrol');
    expect(screen.getByLabelText('機台 ID')).toHaveValue('7');
    expect(screen.getByLabelText('操作員 ID')).toHaveValue('9');
    expect(screen.getByLabelText('開始日期')).toHaveValue('2026-07-01');
    window.history.replaceState({}, '', '/');
  });

  it('machine 工作區只送出 Task5 固定巡檢流與嚴格 options', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue({ ...savedAttributeVersion, source: 'patrol', analysis_family: 'machine', filters: { m_id: 7, mat: '6061', spec: '10x1', item: '外徑', pos: 'A' }, options: { conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態' } });
    renderPage('/spc/advanced?family=machine&source=shipping&m_id=7&material=6061&spec=10x1&item=外徑&position=A&conditions_confirmed=true&condition_reason=不得保留在網址&vendor=不得送出');

    expect(screen.queryByLabelText('資料來源')).not.toBeInTheDocument();
    expect(screen.getByLabelText('研究條件確認理由')).toHaveValue('');
    fireEvent.change(screen.getByLabelText('研究條件確認理由'), { target: { value: '已確認機台設定與治具狀態' } });
    fireEvent.click(screen.getByRole('button', { name: '分析機器績效' }));

    await screen.findByRole('button', { name: '開啟送審' });
    expect(analyzeMock).toHaveBeenCalledWith({
      source: 'patrol', analysis_family: 'machine',
      filters: { m_id: 7, mat: '6061', spec: '10x1', item: '外徑', pos: 'A' },
      options: { conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態' },
    });
  });

  it('切換工作區會清除前一族別 query，避免將屬性條件送入機器研究', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    renderPage('/spc/advanced?family=attribute&source=shipping&vendor=甲&material=6061');

    fireEvent.click(screen.getByRole('tab', { name: '機器績效' }));

    expect(screen.getByLabelText('機台 ID')).toHaveValue('');
    expect(screen.getByLabelText('材質')).toHaveValue('');
  });

  it('只有 SPC 管理權限可分析機器研究，屬性研究仍保留檢視權限入口', () => {
    authMock.mockReturnValue({ hasPermission: (permission: string) => permission === 'spc.view' });
    renderPage('/spc/advanced?family=machine&m_id=7&material=6061&spec=10x1&item=外徑&position=A&conditions_confirmed=true');

    fireEvent.change(screen.getByLabelText('研究條件確認理由'), { target: { value: '已確認機台設定與治具狀態' } });
    expect(screen.getByRole('button', { name: '分析機器績效' })).toBeDisabled();
    expect(screen.getByText('機器研究需要 SPC 管理權限。')).toBeInTheDocument();
  });

  it('機器條件失效時重建候選不會送出空白或 0 機台 request', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue({ ...savedAttributeVersion, source: 'patrol', analysis_family: 'machine', filters: { m_id: 7 }, options: {} });
    renderPage('/spc/advanced?family=machine&m_id=7&material=6061&spec=10x1&item=外徑&position=A&conditions_confirmed=true');
    fireEvent.change(screen.getByLabelText('研究條件確認理由'), { target: { value: '已確認機台設定與治具狀態' } });
    fireEvent.click(screen.getByRole('button', { name: '分析機器績效' }));
    await screen.findByRole('button', { name: '重建候選' });
    fireEvent.change(screen.getByLabelText('機台 ID'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: '重建候選' }));

    expect(analyzeMock).toHaveBeenCalledTimes(1);
  });

  it.each([
    [403, 'SPC_APPROVE_FORBIDDEN', '權限不足：'],
    [409, 'INVALID_STUDY_STATE', '研究狀態已變更：'],
  ])('流程操作遇到 %s 時保留 modal 並以可即時讀取的錯誤提示', async (status, code, heading) => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue(savedAttributeVersion);
    submitMock.mockRejectedValue({ response: { status, data: { code, message: '請重新整理後再操作' } } });
    renderPage('/spc/advanced?source=shipping&vendor=甲');
    fireEvent.click(screen.getByRole('button', { name: '建立屬性研究' }));
    await screen.findByRole('button', { name: '開啟送審' });
    fireEvent.click(screen.getByRole('button', { name: '開啟送審' }));
    fireEvent.click(screen.getByRole('button', { name: '確認流程' }));

    await waitFor(() => expect(screen.getAllByRole('alert').some(item => item.textContent?.includes(code))).toBe(true));
    const alert = screen.getAllByRole('alert').find(item => item.textContent?.includes(code));
    if (!alert) throw new Error('未找到流程錯誤提示');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(alert).toHaveTextContent(heading);
    expect(alert).toHaveTextContent(code);
    expect(screen.queryByText('核准快照廠商：保存廠商')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '開啟送審' })).not.toBeInTheDocument();
    expect(screen.getByText('請重新分析或開啟版本歷程後再操作。')).toBeInTheDocument();
  });

  it('雙向切換工作區會清空未保存的機器條件理由', () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    renderPage('/spc/advanced?family=machine&m_id=7&material=6061&spec=10x1&item=外徑&position=A&conditions_confirmed=true');
    fireEvent.change(screen.getByLabelText('研究條件確認理由'), { target: { value: '本次瀏覽器暫存理由' } });

    fireEvent.click(screen.getByRole('tab', { name: '屬性管制圖' }));
    fireEvent.click(screen.getByRole('tab', { name: '機器績效' }));

    expect(screen.getByLabelText('研究條件確認理由')).toHaveValue('');
  });

  it('從出貨 deep link 建立變數研究並顯示診斷與轉換工作區', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue(savedVariableVersion);
    renderPage('/spc/advanced?family=variable&source=shipping&vendor=甲&material=6061&spec=10x1&field=外徑&start_date=2026-07-01&end_date=2026-07-31');

    expect(screen.getByRole('tab', { name: '變數診斷與轉換' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('檢驗特性')).toHaveValue('外徑');
    fireEvent.click(screen.getByRole('button', { name: '建立變數研究' }));
    await screen.findByText('系統候選：C3');
    expect(screen.getByText('分布轉換候選')).toBeInTheDocument();
    expect(analyzeMock).toHaveBeenCalledWith({
      source: 'shipping', analysis_family: 'variable',
      filters: { vendor: '甲', material: '6061', spec: '10x1', field: '外徑', start_date: '2026-07-01', end_date: '2026-07-31' },
    });
  });

  it('巡檢 deep link 別名會轉成後端 variable filters', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue({ ...savedVariableVersion, source: 'patrol' });
    renderPage('/spc/advanced?family=variable&source=patrol&m_id=7&op_id=9&cust_id=3&mat=6061&spec=10x1&item=厚度&pos=前段&s=2026-07-01&e=2026-07-31');
    fireEvent.click(screen.getByRole('button', { name: '建立變數研究' }));
    await screen.findByText('系統候選：C3');
    expect(analyzeMock).toHaveBeenCalledWith({
      source: 'patrol', analysis_family: 'variable',
      filters: { cust_id: '3', mat: '6061', spec: '10x1', item: '厚度', pos: '前段', s_date: '2026-07-01', e_date: '2026-07-31', m_id: '7', op_id: '9' },
    });
  });

  it('時間模型確認後改用不可變後繼版本並清除舊表單', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue(savedVariableVersion);
    confirmTimeMock.mockResolvedValue({
      ...savedVariableVersion, id: 62, version_no: 2,
      time_model: { ...savedVariableVersion.time_model, model: 'C4', system_candidate: 'C3', overridden: true, confirmed: true, confirmed_by: 7, confirmed_at: '2026-07-19T09:00:00Z', confirmation_reason: '已核對批次切換紀錄' },
    });
    renderPage('/spc/advanced?family=variable&source=shipping&field=外徑');
    fireEvent.click(screen.getByRole('button', { name: '建立變數研究' }));
    await screen.findByLabelText('確認模型');
    fireEvent.change(screen.getByLabelText('確認模型'), { target: { value: 'C4' } });
    fireEvent.change(screen.getByLabelText('確認理由'), { target: { value: '已核對批次切換紀錄' } });
    fireEvent.click(screen.getByRole('button', { name: '確認模型' }));

    await screen.findByText(/確認模型：C4/);
    expect(confirmTimeMock).toHaveBeenCalledWith({ versionId: 61, studyId: 10, model: 'C4', reason: '已核對批次切換紀錄' });
    expect(screen.queryByLabelText('確認理由')).not.toBeInTheDocument();
  });

  it('轉換確認遇到 409 時清除過期版本並進入安全模式', async () => {
    authMock.mockReturnValue({ hasPermission: () => true });
    analyzeMock.mockResolvedValue(savedVariableVersion);
    confirmTransformationMock.mockRejectedValue({ response: { status: 409, data: { code: 'SPC_TRANSFORMATION_CONFIRM_CONFLICT', message: '版本已變更' } } });
    renderPage('/spc/advanced?family=variable&source=shipping&field=外徑');
    fireEvent.click(screen.getByRole('button', { name: '建立變數研究' }));
    await screen.findByLabelText('轉換確認理由');
    fireEvent.change(screen.getByLabelText('轉換確認理由'), { target: { value: '已複核配適證據' } });
    fireEvent.click(screen.getByRole('button', { name: '確認轉換' }));

    await screen.findByText(/SPC_TRANSFORMATION_CONFIRM_CONFLICT/);
    expect(screen.queryByText('系統候選：C3')).not.toBeInTheDocument();
    expect(screen.getByText('請重新分析或開啟版本歷程後再操作。')).toBeInTheDocument();
  });
});
