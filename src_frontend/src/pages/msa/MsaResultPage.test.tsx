import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { MsaResultVersion } from '../../types/msa';
import MsaResultPage from './MsaResultPage';

const authMock = vi.hoisted(() => vi.fn());
const studyMock = vi.hoisted(() => vi.fn());
const submitMock = vi.hoisted(() => vi.fn());
const approveMock = vi.hoisted(() => vi.fn());
const rejectMock = vi.hoisted(() => vi.fn());
const voidMock = vi.hoisted(() => vi.fn());
const downloadMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useMsaStudies', () => ({
  useMsaStudy: () => studyMock(),
  useSubmitMsaResult: () => ({ mutateAsync: submitMock, isPending: false }),
  useApproveMsaResult: () => ({ mutateAsync: approveMock, isPending: false }),
  useRejectMsaResult: () => ({ mutateAsync: rejectMock, isPending: false }),
  useVoidMsaResult: () => ({ mutateAsync: voidMock, isPending: false }),
  useDownloadMsaReport: () => ({ mutateAsync: downloadMock, isPending: false }),
}));

const result = (overrides: Partial<MsaResultVersion> = {}) => ({
  id: 12, study_id: 3, plan_version_id: 9, result_version_no: 1,
  method_code: 'MSA4_GRR_ANOVA_1_0', method_version: '1.0',
  code_version: 'msa-engine-1.0.0', data_hash: 'a'.repeat(64),
  applicability_result: { applicable: true, parts: 10 },
  statistics: {
    grr: 0.0287, ndc: 5,
    percent_study_variation: { ev: 15.3, av: 19.4, grr: 24.7, pv: 96.9 },
  },
  chart_data: {
    xbar_chart: { center: 10, ucl: 10.1, lcl: 9.9, points: {}, out_of_control_points: [] },
    range_chart: { center: 0.02, ucl: 0.06, lcl: 0, points: {} },
  },
  criteria_snapshot: { grr_accept_max: 10, percent_basis: 'study_variation' },
  conclusion: {
    statistical_result: { percent_grr: 24.7 },
    system_disposition: 'conditionally_acceptable',
    engineering_judgment: null,
    reasons: ['%GRR 落在條件接受區間'],
    percent_basis: 'study_variation',
  },
  warnings: [{ code: 'MSA_ANOVA_INTERACTION_POOLED', message: '交互作用併入誤差' }],
  blockers: [],
  status: 'analyzed',
  created_by_id: 7, created_at: '2026-07-28T01:00:00+00:00',
  ...overrides,
}) as unknown as MsaResultVersion;

const renderPage = (
  props: Partial<{ result: MsaResultVersion; isParticipant: boolean }> = {},
) => render(
  <MemoryRouter>
    <MsaResultPage result={props.result ?? result()} isParticipant={props.isParticipant} />
  </MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  authMock.mockReturnValue({ hasPermission: () => true });
  studyMock.mockReturnValue({
    data: { id: 3, study_no: 'MSA-2026-0003', characteristic: '外徑' },
    isLoading: false, isError: false,
  });
  submitMock.mockResolvedValue({});
  approveMock.mockResolvedValue({});
});

describe('MSA 結果頁：結論區', () => {
  it('系統處置以圖示與文字呈現並標示無障礙名稱', () => {
    renderPage();

    const hero = screen.getByLabelText('判定結果：條件接受');
    expect(hero).toHaveAttribute('data-tone', 'warning');
    expect(within(hero).getByText('條件接受')).toBeInTheDocument();
  });

  it('人工工程判斷與系統處置分開呈現', () => {
    renderPage();

    const hero = screen.getByLabelText('判定結果：條件接受');
    expect(within(hero).getByText('系統處置')).toBeInTheDocument();
    expect(within(hero).getByText('人工工程判斷')).toBeInTheDocument();
    expect(within(hero).getByText('未附加')).toBeInTheDocument();
  });

  it('列出判定理由與分析警告', () => {
    renderPage();

    expect(screen.getByText('%GRR 落在條件接受區間')).toBeInTheDocument();
    expect(screen.getByText('交互作用併入誤差')).toBeInTheDocument();
  });

  it('阻擋條件以警示樣式呈現', () => {
    renderPage({
      result: result({
        blockers: [{ code: 'MSA_X', message: '選定口徑無可用百分比' }],
      }),
    });

    expect(screen.getByRole('alert')).toHaveTextContent('選定口徑無可用百分比');
  });
});

describe('MSA 結果頁：證據分層', () => {
  it('分層標題說明每一層回答什麼問題', () => {
    renderPage();

    expect(screen.getByText('這個量測系統的表現長什麼樣子？')).toBeInTheDocument();
    expect(screen.getByText('這個結論是用什麼方法、什麼數字算出來的？')).toBeInTheDocument();
    expect(screen.getByText('當時是用哪一版準則判定的？')).toBeInTheDocument();
    expect(screen.getByText('這份結果能不能被追溯與驗證？')).toBeInTheDocument();
  });

  it('預設只展開第一層，其餘可自行展開', async () => {
    const user = userEvent.setup();
    renderPage();

    const auditToggle = screen.getByRole('button', { name: /稽核指紋/ });
    expect(auditToggle).toHaveAttribute('aria-expanded', 'false');

    await user.click(auditToggle);
    expect(auditToggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('a'.repeat(64))).toBeInTheDocument();
  });

  it('方法層帶出方法版本與程式版本', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: /方法與統計證據/ }));
    expect(
      screen.getByText(/方法 MSA4_GRR_ANOVA_1_0（版本 1.0）/),
    ).toBeInTheDocument();
    expect(screen.getByText(/程式版本 msa-engine-1.0.0/)).toBeInTheDocument();
  });
});

describe('MSA 結果頁：工作流', () => {
  it('已分析的結果只提供送審', () => {
    renderPage();

    expect(screen.getByRole('button', { name: '送審' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: '核准' })).toBeNull();
  });

  it('送審中的結果提供核准與退回', () => {
    renderPage({ result: result({ status: 'submitted' }) });

    expect(screen.getByRole('button', { name: '核准' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退回' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '送審' })).toBeNull();
  });

  it('參與過本研究的人不能核准且說明原因', () => {
    renderPage({
      result: result({ status: 'submitted' }), isParticipant: true,
    });

    expect(screen.getByRole('button', { name: '核准' })).toBeDisabled();
    expect(
      screen.getByText(/你參與過本研究，依職責分離不得核准/),
    ).toBeInTheDocument();
  });

  it('沒有核准權限時按鈕停用並說明權限不足', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission !== 'msa.approve',
    });
    renderPage({ result: result({ status: 'submitted' }) });

    expect(screen.getByRole('button', { name: '核准' })).toBeDisabled();
    expect(screen.getAllByText('權限不足').length).toBeGreaterThan(0);
  });

  it('條件接受送審必須填寫措施與期限', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: '送審' }));
    await user.type(screen.getByLabelText('理由'), '條件接受，已排定改善');
    await user.click(screen.getByRole('button', { name: '確認' }));

    expect(screen.getByRole('alert')).toHaveTextContent('必須列出具體處置措施');
    expect(submitMock).not.toHaveBeenCalled();
  });

  it('填齊條件接受資訊後送出 expected_status 與措施', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: '送審' }));
    await user.type(screen.getByLabelText('理由'), '條件接受');
    await user.type(screen.getByLabelText('處置措施（每行一項）'), '加嚴抽樣');
    await user.type(screen.getByLabelText('處置期限'), '2026-10-31');
    await user.click(screen.getByRole('button', { name: '確認' }));

    expect(submitMock).toHaveBeenCalledWith({
      resultId: 12,
      expected_status: 'analyzed',
      reason: '條件接受',
      actions: ['加嚴抽樣'],
      due_date: '2026-10-31',
    });
  });

  it('可接受的結果送審不要求處置措施', async () => {
    const user = userEvent.setup();
    renderPage({
      result: result({
        conclusion: {
          statistical_result: {}, system_disposition: 'acceptable',
          engineering_judgment: null, reasons: [], percent_basis: 'tolerance',
        },
      } as never),
    });

    await user.click(screen.getByRole('button', { name: '送審' }));
    await user.type(screen.getByLabelText('理由'), '統計合格');
    await user.click(screen.getByRole('button', { name: '確認' }));

    expect(submitMock).toHaveBeenCalledWith({
      resultId: 12, expected_status: 'analyzed', reason: '統計合格',
    });
  });

  it('後端衝突時保留對話框並顯示錯誤', async () => {
    submitMock.mockRejectedValue(new Error('結果版本狀態已變更'));
    const user = userEvent.setup();
    renderPage({
      result: result({
        conclusion: {
          statistical_result: {}, system_disposition: 'acceptable',
          engineering_judgment: null, reasons: [], percent_basis: 'tolerance',
        },
      } as never),
    });

    await user.click(screen.getByRole('button', { name: '送審' }));
    await user.type(screen.getByLabelText('理由'), '送審');
    await user.click(screen.getByRole('button', { name: '確認' }));

    expect(await screen.findByText('結果版本狀態已變更')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('未核准時提醒報告會帶未核准標示', () => {
    renderPage();

    expect(
      screen.getByText('尚未核准，報告會帶「未核准」標示'),
    ).toBeInTheDocument();
  });

  it('下載報告帶出研究編號', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: '下載 PDF 報告' }));

    expect(downloadMock).toHaveBeenCalledWith({
      resultId: 12, format: 'pdf', studyNo: 'MSA-2026-0003',
    });
  });
});
