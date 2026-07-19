import { act, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authMock = vi.hoisted(() => vi.fn());
const analyzeMock = vi.hoisted(() => vi.fn());
const approveResearchMock = vi.hoisted(() => vi.fn());

const savedAttributeVersion = {
  id: 51, study_id: 9, source: 'shipping', study_type: 'retrospective', analysis_family: 'attribute',
  process_stream_key: 'attribute-stream', filters: { vendor: '保存廠商', material: '6061', spec: '10x1', field: '外徑' },
  options: { interval: 'day', chart_type: 'p' }, version_no: 1, method_version: '2026.2', code_version: null,
  data_hash: 'a'.repeat(64), specification: { found: true }, charts: null, stability: { evaluated: false, stable: null, violations: [], rules_used: [] },
  distribution: { model: null, label: '不適用', params: [], accepted: false, normal_ok: false, unimodal: false, reason_code: 'attribute_chart', candidates: [], fit_method: null, alpha: 0.05 },
  time_model: { candidate: null, confirmed: false, statistically_controlled: false }, capability: { available: false },
  applicability: { applicable: false, message: '測試' }, status: 'draft', audit_incomplete: false, created_by: 1, created_at: '2026-07-19',
};

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useSpcStudies', () => ({
  useAnalyzeSpcStudy: () => ({ mutateAsync: analyzeMock, isPending: false, isError: false }),
  useSubmitSpcStudy: () => ({ isPending: false }), useApproveSpcStudy: () => ({ isPending: false }),
  useApproveSpcResearch: () => ({ mutateAsync: approveResearchMock, isPending: false }),
  useRejectSpcStudy: () => ({ isPending: false }), useRetireSpcLimit: () => ({ isPending: false }),
}));
vi.mock('../../components/spc/SpcStudyWorkflowBar', () => ({
  default: (props: { onAction: (action: 'submit' | 'approve-research') => void }) => <><button onClick={() => props.onAction('submit')}>開啟送審</button><button onClick={() => props.onAction('approve-research')}>開啟研究核准</button></>,
}));
vi.mock('../../components/spc/SpcBaselineApprovalModal', () => ({
  default: (props: { filters: Record<string, unknown> }) => <div>核准快照廠商：{String(props.filters.vendor)}</div>,
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
    authMock.mockReset();
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
    renderPage('/spc/advanced?family=machine&source=shipping&m_id=7&material=6061&spec=10x1&item=外徑&position=A&conditions_confirmed=true&condition_reason=已確認機台設定與治具狀態&vendor=不得送出');

    expect(screen.queryByLabelText('資料來源')).not.toBeInTheDocument();
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
});
