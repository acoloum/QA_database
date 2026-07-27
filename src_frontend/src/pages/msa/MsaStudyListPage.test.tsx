import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MsaStudyListPage from './MsaStudyListPage';

const authMock = vi.hoisted(() => vi.fn());
const studiesMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useMsaStudies', () => ({
  useMsaStudies: (params: unknown) => studiesMock(params),
}));

const study = (overrides = {}) => ({
  id: 1, study_no: 'MSA-2026-0001', study_type: 'grr_anova',
  characteristic: '外徑', status: 'approved',
  next_due_date: null, updated_at: '2026-07-01T00:00:00+00:00',
  ...overrides,
});

const query = (items: unknown[]) => ({
  data: { items, page: 1, page_size: 100, total: items.length },
  isLoading: false, isError: false, refetch: vi.fn(),
});

const renderPage = () => render(
  <MemoryRouter><MsaStudyListPage /></MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  authMock.mockReturnValue({ hasPermission: () => true });
});

describe('MSA 研究清單', () => {
  it('待核准排在最前面，逾期次之，其餘依階段排列', async () => {
    studiesMock.mockReturnValue(query([
      study({ id: 1, study_no: 'A-已核准', status: 'approved' }),
      study({
        id: 2, study_no: 'B-逾期', status: 'collecting',
        next_due_date: '2020-01-01',
      }),
      study({ id: 3, study_no: 'C-待核准', status: 'submitted' }),
      study({ id: 4, study_no: 'D-草稿', status: 'draft' }),
    ]));
    renderPage();

    const rows = await screen.findAllByRole('row');
    // 第 0 列是表頭
    expect(rows[1]).toHaveTextContent('C-待核准');
    expect(rows[2]).toHaveTextContent('B-逾期');
    expect(rows[3]).toHaveTextContent('D-草稿');
    expect(rows[4]).toHaveTextContent('A-已核准');
  });

  it('逾期研究明確標示而不是只靠日期', async () => {
    studiesMock.mockReturnValue(query([
      study({ status: 'approved', next_due_date: '2020-01-01' }),
    ]));
    renderPage();

    const row = (await screen.findAllByRole('row'))[1];
    expect(row).toHaveAttribute('data-overdue', 'true');
    expect(within(row).getByText('（已逾期）')).toBeInTheDocument();
  });

  it('狀態與方法以中文顯示', async () => {
    studiesMock.mockReturnValue(query([study({ status: 'ready_for_analysis' })]));
    renderPage();

    // 篩選下拉也含相同文字，因此限縮在表格內比對
    const table = await screen.findByRole('table', { name: 'MSA 研究' });
    expect(within(table).getByText('可進行分析')).toBeInTheDocument();
    expect(within(table).getByText('交叉型 ANOVA')).toBeInTheDocument();
  });

  it('狀態篩選會帶入 API 查詢參數', async () => {
    studiesMock.mockReturnValue(query([study()]));
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByLabelText('狀態'), 'submitted');

    expect(studiesMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'submitted' }),
    );
  });

  it('方法與關鍵字在前端過濾既有結果', async () => {
    studiesMock.mockReturnValue(query([
      study({ id: 1, study_no: 'MSA-A', study_type: 'grr_anova' }),
      study({ id: 2, study_no: 'MSA-B', study_type: 'bias' }),
    ]));
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByLabelText('方法'), 'bias');
    expect(screen.queryByText('MSA-A')).toBeNull();
    expect(screen.getByText('MSA-B')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('方法'), '');
    await user.type(screen.getByLabelText('搜尋'), 'MSA-A');
    expect(screen.getByText('MSA-A')).toBeInTheDocument();
    expect(screen.queryByText('MSA-B')).toBeNull();
  });

  it('清除篩選會回到全部結果', async () => {
    studiesMock.mockReturnValue(query([study({ study_type: 'bias' })]));
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText('搜尋'), '不存在');
    expect(screen.getByText('沒有符合條件的 MSA 研究')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '清除篩選' }));
    expect(screen.getByText('MSA-2026-0001')).toBeInTheDocument();
  });

  it('沒有 msa.manage 時不顯示建立研究', async () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission !== 'msa.manage',
    });
    studiesMock.mockReturnValue(query([study()]));
    renderPage();

    expect(screen.queryByRole('link', { name: '建立研究' })).toBeNull();
  });

  it('載入中、錯誤與空狀態都有可讀提示', async () => {
    studiesMock.mockReturnValue({
      data: undefined, isLoading: true, isError: false, refetch: vi.fn(),
    });
    const { unmount } = renderPage();
    expect(screen.getByRole('status')).toHaveTextContent('正在讀取研究清單');
    unmount();

    const refetch = vi.fn();
    studiesMock.mockReturnValue({
      data: undefined, isLoading: false, isError: true, refetch,
    });
    const errorView = renderPage();
    expect(screen.getByRole('alert')).toHaveTextContent('無法載入研究清單');
    errorView.unmount();

    studiesMock.mockReturnValue(query([]));
    renderPage();
    expect(screen.getByText('沒有符合條件的 MSA 研究')).toBeInTheDocument();
  });

  it('研究編號可連到明細', async () => {
    studiesMock.mockReturnValue(query([study({ id: 42 })]));
    renderPage();

    expect(
      await screen.findByRole('link', { name: 'MSA-2026-0001' }),
    ).toHaveAttribute('href', '/msa/studies/42');
  });
});
