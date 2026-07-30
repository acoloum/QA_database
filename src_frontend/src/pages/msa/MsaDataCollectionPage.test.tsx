import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MsaObservationMatrix from '../../components/msa/MsaObservationMatrix';
import MsaDataCollectionPage from './MsaDataCollectionPage';

const authMock = vi.hoisted(() => vi.fn());
const studyMock = vi.hoisted(() => vi.fn());
const tasksMock = vi.hoisted(() => vi.fn());
const observationsMock = vi.hoisted(() => vi.fn());
const recordMock = vi.hoisted(() => vi.fn());
const correctMock = vi.hoisted(() => vi.fn());
const validateMock = vi.hoisted(() => vi.fn());
const previewMock = vi.hoisted(() => vi.fn());
const confirmMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useMsaStudies', () => ({
  useMsaStudy: () => studyMock(),
  useMsaPlanTasks: () => tasksMock(),
  useMsaPlanObservations: () => observationsMock(),
  useRecordMsaObservation: () => ({
    mutateAsync: recordMock, isPending: false,
  }),
  useCorrectMsaObservation: () => ({
    mutateAsync: correctMock, isPending: false,
  }),
  useValidateMsaPlan: () => ({ mutateAsync: validateMock, isPending: false }),
  usePreviewMsaObservationImport: () => ({
    mutateAsync: previewMock, isPending: false,
  }),
  useConfirmMsaObservationImport: () => ({
    mutateAsync: confirmMock, isPending: false,
  }),
}));

const task = (overrides = {}) => ({
  requested_order: 1, part_blind_code: 'P-07', appraiser_blind_code: 'A-01',
  trial_no: 1, recorded: false, ...overrides,
});

const renderPage = () => render(
  <MemoryRouter initialEntries={['/msa/studies/3/collect']}>
    <Routes>
      <Route
        path="/msa/studies/:studyId/collect"
        element={<MsaDataCollectionPage />}
      />
    </Routes>
  </MemoryRouter>,
);

beforeEach(() => {
  vi.clearAllMocks();
  authMock.mockReturnValue({ hasPermission: () => true });
  studyMock.mockReturnValue({
    data: {
      id: 3, study_no: 'MSA-2026-0003', characteristic: '外徑', unit: 'mm',
      current_plan_version_id: 9,
    },
    isLoading: false, isError: false,
  });
  tasksMock.mockReturnValue({
    data: { items: [task(), task({ requested_order: 2 })] },
    isLoading: false, isError: false, refetch: vi.fn(),
  });
  observationsMock.mockReturnValue({
    data: { items: [] }, isLoading: false, isError: false, refetch: vi.fn(),
  });
  recordMock.mockResolvedValue({ id: 1 });
});

describe('MSA 盲測收集', () => {
  it('評價人只看到盲碼與目前量測欄位', async () => {
    renderPage();

    expect(await screen.findByText('盲碼 P-07')).toBeInTheDocument();
    expect(screen.queryByText(/真實零件/)).toBeNull();
    expect(screen.queryByText(/參考值/)).toBeNull();
    expect(screen.queryByText(/前次讀值/)).toBeNull();
  });

  it('進度顯示完成與總數，而不是只給百分比', async () => {
    tasksMock.mockReturnValue({
      data: {
        items: [task({ recorded: true }), task({ requested_order: 2 })],
      },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    renderPage();

    expect(await screen.findByText('進度 1 / 2 件')).toBeInTheDocument();
    expect(screen.getByText(/已完成 1 \/ 2 件/)).toBeInTheDocument();
  });

  it('送出讀值後帶著任務順序呼叫後端', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText(/量測讀值/), '10.004');
    await user.click(screen.getByRole('button', { name: '儲存並前往下一件' }));

    expect(recordMock).toHaveBeenCalledWith({
      planId: 9, task_order: 1, numeric_value: '10.004',
    });
  });

  it('未輸入讀值時不能送出', async () => {
    renderPage();

    expect(
      await screen.findByRole('button', { name: '儲存並前往下一件' }),
    ).toBeDisabled();
  });

  it('後端衝突時顯示訊息並重新取得任務狀態', async () => {
    const refetch = vi.fn();
    tasksMock.mockReturnValue({
      data: { items: [task()] },
      isLoading: false, isError: false, refetch,
    });
    recordMock.mockRejectedValue(new Error('這個盲測任務已有有效讀值'));
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText(/量測讀值/), '10.0');
    await user.click(screen.getByRole('button', { name: '儲存並前往下一件' }));

    expect(
      await screen.findByText('這個盲測任務已有有效讀值'),
    ).toBeInTheDocument();
    await waitFor(() => expect(refetch).toHaveBeenCalled());
  });

  it('全部完成後提供完整性驗證入口', async () => {
    tasksMock.mockReturnValue({
      data: { items: [task({ recorded: true })] },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText('所有盲測任務都已完成')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '驗證資料完整性' }));
    expect(validateMock).toHaveBeenCalledWith({ planId: 9 });
  });

  it('沒有 msa.manage 時不顯示矩陣與匯入分頁', async () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission !== 'msa.manage',
    });
    renderPage();

    expect(await screen.findByRole('button', { name: '逐筆盲測' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '觀測矩陣' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Excel 匯入' })).toBeNull();
  });
});

describe('MSA 觀測矩陣', () => {
  const cells = [{
    observationId: 55,
    requestedOrder: 1, partBlindCode: 'P-07', appraiserBlindCode: 'A-01',
    trialNo: 1, value: '10.001', source: 'page_single',
    enteredBy: '王小明', enteredAt: '2026-07-27T09:30:00+08:00',
    history: [
      {
        value: '10.000', enteredBy: '王小明',
        enteredAt: '2026-07-27T09:00:00+08:00', reason: null,
      },
      {
        value: '10.001', enteredBy: '李主管',
        enteredAt: '2026-07-27T09:30:00+08:00', reason: '小數點輸入錯誤',
      },
    ],
  }];

  it('修正讀值必須填寫理由才能送出', async () => {
    const onCorrect = vi.fn();
    const user = userEvent.setup();
    render(<MsaObservationMatrix cells={cells} onCorrect={onCorrect} />);

    await user.click(
      await screen.findByRole('button', { name: '修正 P-07 第 1 次' }),
    );
    await user.clear(screen.getByLabelText('新讀值'));
    await user.type(screen.getByLabelText('新讀值'), '10.002');
    await user.click(screen.getByRole('button', { name: '確認修正' }));

    expect(screen.getByRole('alert')).toHaveTextContent('請填寫修正理由');
    expect(onCorrect).not.toHaveBeenCalled();
  });

  it('填寫理由後送出修正', async () => {
    const onCorrect = vi.fn();
    const user = userEvent.setup();
    render(<MsaObservationMatrix cells={cells} onCorrect={onCorrect} />);

    await user.click(
      await screen.findByRole('button', { name: '修正 P-07 第 1 次' }),
    );
    await user.clear(screen.getByLabelText('新讀值'));
    await user.type(screen.getByLabelText('新讀值'), '10.002');
    await user.type(screen.getByLabelText('修正理由'), '重新量測確認');
    await user.click(screen.getByRole('button', { name: '確認修正' }));

    expect(onCorrect).toHaveBeenCalledWith({
      observationId: 55, requestedOrder: 1,
      value: '10.002', reason: '重新量測確認',
    });
  });

  it('已修正的格子可展開原始與後繼紀錄', async () => {
    const user = userEvent.setup();
    render(<MsaObservationMatrix cells={cells} onCorrect={vi.fn()} />);

    await user.click(screen.getByRole('button', {
      name: '查看 P-07 第 1 次修正歷程',
    }));

    const history = screen.getByRole('region', { name: '修正歷程' });
    expect(within(history).getByText('10.000')).toBeInTheDocument();
    expect(within(history).getByText('原始輸入')).toBeInTheDocument();
    expect(within(history).getByText('小數點輸入錯誤')).toBeInTheDocument();
  });

  it('尚未輸入的格子不提供修正入口', () => {
    render(
      <MsaObservationMatrix
        cells={[{
          ...cells[0], observationId: null, value: null, history: [],
        }]}
        onCorrect={vi.fn()}
      />,
    );

    expect(screen.getByText('未輸入')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /修正/ })).toBeNull();
  });
});
