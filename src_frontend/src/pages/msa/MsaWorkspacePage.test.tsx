import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MsaWorkspacePage from './MsaWorkspacePage';

const authMock = vi.hoisted(() => vi.fn());
const studiesMock = vi.hoisted(() => vi.fn());
const equipmentMock = vi.hoisted(() => vi.fn());
const restudyMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useMsaStudies', () => ({
  useMsaStudies: () => studiesMock(),
  useMsaRestudyRequests: () => restudyMock(),
}));
vi.mock('../../hooks/useMsaEquipment', () => ({
  useMsaEquipment: () => equipmentMock(),
  msaKeys: { all: ['msa'] },
}));

const renderPage = () => render(
  <MemoryRouter><MsaWorkspacePage /></MemoryRouter>,
);

const query = (items: unknown[]) => ({
  data: { items, page: 1, page_size: 100, total: items.length },
  isLoading: false,
  isError: false,
  refetch: vi.fn(),
});

const equipmentRow = (overrides = {}) => ({
  id: 1, equipment_no: 'EQ-001', name: '分厘卡',
  calibration_status: 'failed', next_calibration_date: '2026-06-01',
  custodian: '王小明', status: 'active', ...overrides,
});

const studyRow = (overrides = {}) => ({
  id: 10, study_no: 'MSA-2026-0010', characteristic: '外徑',
  status: 'submitted', next_due_date: null, ...overrides,
});

const restudyRow = (overrides = {}) => ({
  id: 20, source_study_id: 3, trigger_type: 'equipment_maintenance',
  status: 'open', due_date: '2020-01-01', ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  authMock.mockReturnValue({ hasPermission: () => true });
  studiesMock.mockReturnValue(query([studyRow()]));
  equipmentMock.mockReturnValue(query([equipmentRow()]));
  restudyMock.mockReturnValue(query([restudyRow()]));
});

describe('MSA 工作台', () => {
  it('依阻擋風險優先呈現工作，而不是只顯示總數', async () => {
    renderPage();

    const queues = await screen.findAllByTestId('msa-work-item');
    expect(queues[0]).toHaveTextContent('校驗失敗');
    expect(queues[1]).toHaveTextContent('待核准');
    expect(queues[2]).toHaveTextContent('再研究逾期');
  });

  it('狀態同時提供圖示與文字，且以無障礙名稱標示嚴重度', async () => {
    renderPage();

    const [critical] = await screen.findAllByTestId('msa-work-item');
    expect(critical).toHaveAttribute('data-severity', 'critical');
    expect(critical).toHaveAccessibleName(/重大風險/);
    expect(within(critical).getByText('校驗失敗')).toBeInTheDocument();
  });

  it('每筆工作都說明原因、對象、期限與下一步', async () => {
    renderPage();

    const [critical] = await screen.findAllByTestId('msa-work-item');
    expect(within(critical).getByText('EQ-001｜分厘卡')).toBeInTheDocument();
    expect(within(critical).getByText('負責人：王小明')).toBeInTheDocument();
    expect(within(critical).getByText('期限 2026-06-01')).toBeInTheDocument();
    expect(
      within(critical).getByText(/下一步：完成校驗並核准後才可用於正式研究/),
    ).toBeInTheDocument();
  });

  it('風險卡片以圖示與文字說明嚴重度', async () => {
    renderPage();

    const blocked = await screen.findByLabelText('重大風險：設備阻擋 1 件');
    expect(blocked).toHaveAttribute('data-severity', 'critical');
    const approval = screen.getByLabelText('需注意：待核准 1 件');
    expect(approval).toHaveAttribute('data-severity', 'warning');
  });

  it('沒有風險時卡片顯示為正常而非隱藏', async () => {
    studiesMock.mockReturnValue(query([]));
    equipmentMock.mockReturnValue(query([]));
    restudyMock.mockReturnValue(query([]));
    renderPage();

    expect(
      await screen.findByLabelText('正常：設備阻擋 0 件'),
    ).toHaveAttribute('data-severity', 'normal');
    expect(screen.getByText('目前沒有待處理的 MSA 工作。')).toBeInTheDocument();
  });

  it('沒有 msa.manage 時隱藏建立研究捷徑', async () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission !== 'msa.manage',
    });
    renderPage();

    expect(await screen.findByText('研究清單')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /建立研究/ })).toBeNull();
  });

  it('具 msa.manage 時提供建立研究捷徑', async () => {
    renderPage();

    const links = await screen.findAllByRole('link', { name: /建立研究/ });
    expect(links[0]).toHaveAttribute('href', '/msa/studies/new');
  });

  it('所有捷徑都可用鍵盤逐一到達', async () => {
    const user = userEvent.setup();
    renderPage();

    const nav = await screen.findByRole('navigation', { name: 'MSA 捷徑' });
    const links = within(nav).getAllByRole('link');
    for (const link of links) {
      await user.tab();
      if (document.activeElement === link) {
        expect(link).toHaveFocus();
      }
    }
    expect(links.length).toBeGreaterThanOrEqual(4);
  });

  it('載入中顯示可讀狀態', () => {
    studiesMock.mockReturnValue({
      data: undefined, isLoading: true, isError: false, refetch: vi.fn(),
    });
    renderPage();

    expect(screen.getByRole('status')).toHaveTextContent('正在讀取 MSA 工作');
  });

  it('載入失敗時提供重試', async () => {
    const refetch = vi.fn();
    studiesMock.mockReturnValue({
      data: undefined, isLoading: false, isError: true, refetch,
    });
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByRole('alert')).toHaveTextContent('無法載入 MSA 工作台');
    await user.click(screen.getByRole('button', { name: '重試' }));
    expect(refetch).toHaveBeenCalled();
  });

  it('尚未逾期的再研究要求不會被標成重大風險', async () => {
    restudyMock.mockReturnValue(query([restudyRow({ due_date: '2099-12-31' })]));
    renderPage();

    const items = await screen.findAllByTestId('msa-work-item');
    const restudy = items.find(
      (item) => item.textContent?.includes('再研究要求'),
    );
    expect(restudy).toHaveAttribute('data-severity', 'info');
  });
});
