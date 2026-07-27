import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import type { MsaCriteriaProfile, MsaCriteriaVersion } from '../../types/msa';
import MsaCriteriaPage from './MsaCriteriaPage';

const authMock = vi.hoisted(() => vi.fn());
const criteriaQueryMock = vi.hoisted(() => vi.fn());
const approveMock = vi.hoisted(() => vi.fn());
const createVersionMock = vi.hoisted(() => vi.fn());

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
  useAuth: () => authMock(),
}));

vi.mock('../../hooks/useMsaCriteria', () => ({
  useMsaCriteria: (params: unknown) => criteriaQueryMock(params),
  useApproveMsaCriteriaVersion: () => ({ mutateAsync: approveMock, isPending: false }),
  useCreateMsaCriteriaVersion: () => ({ mutateAsync: createVersionMock, isPending: false }),
  useCreateMsaCriteriaProfile: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

const version = (overrides: Partial<MsaCriteriaVersion>): MsaCriteriaVersion => ({
  id: 1,
  profile_id: 10,
  version_no: 1,
  method_version: 'MSA4-1.0',
  effective_date: '2026-01-01',
  thresholds: {
    grr_accept_max: 10,
    grr_conditional_max: 30,
    ndc_min: 5,
    alpha: 0.05,
    kappa_min: 0.75,
    effectiveness_min: 90,
    false_accept_max: 5,
    false_reject_max: 5,
  },
  stability_rules: { rule_set: 'WECO', enabled_rules: [1, 2, 3, 4] },
  conditional_actions: ['加嚴抽樣', '限期改善量測系統'],
  basis: 'MSA 第四版',
  status: 'approved',
  is_current: false,
  created_by: 1,
  created_at: '2026-01-01T00:00:00+00:00',
  approved_by: 2,
  approved_at: '2026-01-02T00:00:00+00:00',
  ...overrides,
});

const profile: MsaCriteriaProfile = {
  id: 10,
  name: '一般計量型',
  customer_scope: '安泰汽車',
  product_scope: '傳動軸',
  product_family_scope: '冷鍛件',
  characteristic_scope: '外徑',
  characteristic_importance: '重要特性',
  applicable_study_types: ['crossed_anova', 'bias'],
  current_version_id: 2,
  versions: [
    version({ id: 1, version_no: 1, status: 'approved', is_current: false }),
    version({
      id: 2,
      version_no: 2,
      status: 'approved',
      is_current: true,
      thresholds: {
        grr_accept_max: 8,
        grr_conditional_max: 20,
        ndc_min: 5,
        alpha: 0.05,
        kappa_min: 0.75,
        effectiveness_min: 90,
        false_accept_max: 5,
        false_reject_max: 5,
      },
    }),
    version({
      id: 3,
      version_no: 3,
      status: 'draft',
      is_current: false,
      approved_by: null,
      approved_at: null,
    }),
  ],
};

const successQuery = {
  data: { items: [profile], page: 1, page_size: 25, total: 1 },
  isLoading: false,
  isError: false,
  refetch: vi.fn(),
};

/** 只取版本歷程的直接子項，排除條件措施等巢狀清單項目。 */
const versionEntries = (timeline: HTMLElement) => (
  within(timeline)
    .getAllByRole('listitem')
    .filter((item) => item.parentElement === timeline)
);

const allPermissions = {
  user: { username: '測試人員', role: 'admin' },
  hasPermission: () => true,
};

beforeEach(() => {
  vi.clearAllMocks();
  authMock.mockReturnValue(allPermissions);
  criteriaQueryMock.mockReturnValue(successQuery);
  approveMock.mockResolvedValue(undefined);
});

describe('MSA 判定準則頁', () => {
  it('清楚顯示目前版本、前版與方法依據', async () => {
    render(<MsaCriteriaPage />);

    expect(await screen.findByText('一般計量型')).toBeInTheDocument();
    expect(screen.getByText('目前版本 v2')).toBeInTheDocument();
    expect(screen.getAllByText('MSA 第四版').length).toBeGreaterThan(0);

    const timeline = screen.getByRole('list', { name: '一般計量型 的版本歷程' });
    const entries = versionEntries(timeline);
    expect(entries).toHaveLength(3);
    expect(within(entries[0]).getByText('草稿')).toBeInTheDocument();
    expect(within(entries[1]).getByText('目前版本')).toBeInTheDocument();
    expect(within(entries[2]).getByText('歷史版本')).toBeInTheDocument();
  });

  it('以人類可讀名稱顯示各項判定門檻', async () => {
    render(<MsaCriteriaPage />);

    const timeline = await screen.findByRole('list', { name: '一般計量型 的版本歷程' });
    const current = versionEntries(timeline)[1];

    expect(within(current).getByText('GRR 允收上限')).toBeInTheDocument();
    expect(within(current).getByText('8 %')).toBeInTheDocument();
    expect(within(current).getByText('GRR 條件接受上限')).toBeInTheDocument();
    expect(within(current).getByText('20 %')).toBeInTheDocument();
    expect(within(current).getByText('ndc 最低值')).toBeInTheDocument();
    expect(within(current).getByText('Kappa 最低值')).toBeInTheDocument();
    expect(within(current).getByText('有效性最低值')).toBeInTheDocument();
    expect(within(current).getByText('誤收率上限')).toBeInTheDocument();
    expect(within(current).getByText('誤拒率上限')).toBeInTheDocument();
  });

  it('顯示適用顧客、產品族、品質特性、研究類型與生效日', async () => {
    render(<MsaCriteriaPage />);

    expect(await screen.findByText('安泰汽車')).toBeInTheDocument();
    expect(screen.getByText('冷鍛件')).toBeInTheDocument();
    expect(screen.getByText('外徑')).toBeInTheDocument();
    expect(screen.getByText(/交叉式 ANOVA/)).toBeInTheDocument();
    expect(screen.getAllByText('2026-01-01').length).toBeGreaterThan(0);
  });

  it('核准時送出畫面看到的 expected_status 與理由', async () => {
    const user = userEvent.setup();
    render(<MsaCriteriaPage />);

    await user.click(await screen.findByRole('button', { name: '核准 v3' }));
    await user.type(screen.getByLabelText('核准理由'), '符合公司與顧客要求');
    await user.click(screen.getByRole('button', { name: '確認核准' }));

    expect(approveMock).toHaveBeenCalledWith({
      versionId: 3,
      expected_status: 'draft',
      reason: '符合公司與顧客要求',
    });
  });

  it('沒有填寫理由時不得送出核准', async () => {
    const user = userEvent.setup();
    render(<MsaCriteriaPage />);

    await user.click(await screen.findByRole('button', { name: '核准 v3' }));
    expect(screen.getByRole('button', { name: '確認核准' })).toBeDisabled();
    expect(approveMock).not.toHaveBeenCalled();
  });

  it('核准失敗時顯示錯誤並保留對話框', async () => {
    const user = userEvent.setup();
    approveMock.mockRejectedValueOnce(new Error('判定準則版本已被其他人更新'));
    render(<MsaCriteriaPage />);

    await user.click(await screen.findByRole('button', { name: '核准 v3' }));
    await user.type(screen.getByLabelText('核准理由'), '符合公司與顧客要求');
    await user.click(screen.getByRole('button', { name: '確認核准' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('判定準則版本已被其他人更新');
    expect(screen.getByRole('button', { name: '確認核准' })).toBeInTheDocument();
  });

  it('不提供編輯已核准版本的入口', async () => {
    render(<MsaCriteriaPage />);

    const timeline = await screen.findByRole('list', { name: '一般計量型 的版本歷程' });
    const approvedEntries = versionEntries(timeline).slice(1);

    approvedEntries.forEach((entry) => {
      expect(within(entry).queryByRole('button', { name: /編輯/ })).toBeNull();
      expect(within(entry).queryByRole('button', { name: /核准/ })).toBeNull();
    });
  });

  it('沒有 msa.approve 時不顯示核准按鈕', async () => {
    authMock.mockReturnValue({
      user: { username: '主管', role: 'user' },
      hasPermission: (permission: string) => permission !== 'msa.approve',
    });
    render(<MsaCriteriaPage />);

    expect(await screen.findByText('一般計量型')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '核准 v3' })).toBeNull();
  });

  it('沒有 msa.manage 時不顯示建立版本入口', async () => {
    authMock.mockReturnValue({
      user: { username: '檢驗員', role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
    });
    render(<MsaCriteriaPage />);

    expect(await screen.findByText('一般計量型')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /新增版本/ })).toBeNull();
  });

  it('載入中、錯誤與空狀態都有可讀提示', async () => {
    criteriaQueryMock.mockReturnValue({
      data: undefined, isLoading: true, isError: false, refetch: vi.fn(),
    });
    const { unmount } = render(<MsaCriteriaPage />);
    expect(screen.getByRole('status')).toHaveTextContent('正在讀取判定準則');
    unmount();

    criteriaQueryMock.mockReturnValue({
      data: undefined, isLoading: false, isError: true, refetch: vi.fn(),
    });
    const errorView = render(<MsaCriteriaPage />);
    expect(screen.getByRole('alert')).toHaveTextContent('無法載入判定準則');
    errorView.unmount();

    criteriaQueryMock.mockReturnValue({
      data: { items: [], page: 1, page_size: 25, total: 0 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(<MsaCriteriaPage />);
    expect(screen.getByText('尚未建立任何判定準則')).toBeInTheDocument();
  });
});
