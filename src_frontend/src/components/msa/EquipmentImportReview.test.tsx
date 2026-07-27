import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { EquipmentImportBatch } from '../../types/msa';
import MsaImportHistoryPage from '../../pages/msa/MsaImportHistoryPage';
import EquipmentImportReview from './EquipmentImportReview';

const authMock = vi.hoisted(() => vi.fn());
const previewMock = vi.hoisted(() => vi.fn());
const confirmMock = vi.hoisted(() => vi.fn());
const historyMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({
  useAuth: () => authMock(),
}));

vi.mock('../../hooks/useMsaImports', () => ({
  usePreviewMsaEquipmentImport: () => ({
    mutateAsync: previewMock,
    isPending: false,
    error: null,
  }),
  useConfirmMsaEquipmentImport: () => ({
    mutateAsync: confirmMock,
    isPending: false,
    error: null,
  }),
  useMsaImportHistory: () => historyMock(),
  useMsaImportBatch: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
}));

const batch: EquipmentImportBatch = {
  id: 41,
  original_filename: 'measurements.csv',
  file_sha256: 'abc123',
  file_size: 300,
  status: 'previewed',
  total_rows: 2,
  success_rows: 0,
  pending_rows: 1,
  rejected_rows: 0,
  parser_version: 'msa-equipment-csv-1',
  uploaded_by: 7,
  uploaded_at: '2026-07-27T08:00:00+00:00',
  rows: [
    {
      id: 71,
      source_row_no: 2,
      raw: { 設備編號: 'EQ-071', 校驗類別: '遊校' },
      normalized: {
        equipment_no: 'EQ-071',
        calibration_type: null,
        calibration_reminder: '<span class="danger">校驗即將到期</span>',
      },
      issue_codes: ['MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE'],
      issue_description: '「遊校」必須由人員明確映射',
      equipment_id: null,
      confirmed_by: null,
      confirmed_at: null,
    },
    {
      id: 72,
      source_row_no: 3,
      raw: { 設備編號: 'EQ-072' },
      normalized: { equipment_no: 'EQ-072', name: '高度規' },
      issue_codes: [],
      issue_description: null,
      equipment_id: null,
      confirmed_by: null,
      confirmed_at: null,
    },
  ],
};

describe('設備匯入檢閱', () => {
  beforeEach(() => vi.clearAllMocks());

  it('不以 HTML 呈現來源提醒文字', () => {
    render(<EquipmentImportReview batch={batch} />);

    expect(screen.getByText(/校驗即將到期/)).toBeInTheDocument();
    expect(document.querySelector('span.danger')).toBeNull();
  });

  it('逐列解決遊校映射後才能確認，且不提供全部忽略', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<EquipmentImportReview batch={batch} onConfirm={onConfirm} />);

    expect(screen.getByText('待人工確認 1 筆')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: /全部忽略/ })).not.toBeInTheDocument();

    const issueRow = screen.getByRole('row', { name: /原始列 2/ });
    await user.selectOptions(within(issueRow).getByLabelText('列 2 處置'), 'accept');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();

    await user.selectOptions(within(issueRow).getByLabelText('列 2 校驗類別映射'), 'external');
    await user.click(screen.getByRole('button', { name: '確認匯入' }));

    expect(onConfirm).toHaveBeenCalledWith({
      71: { action: 'accept', calibration_type: 'external' },
    });
  });

  it('以三階段 stepper 與逐列原始/正規化/問題碼建立證據軌', () => {
    render(<EquipmentImportReview batch={batch} />);

    const stepper = screen.getByLabelText('設備匯入階段');
    expect(within(stepper).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      expect.stringContaining('上傳與解析'),
      expect.stringContaining('差異與問題處置'),
      expect.stringContaining('確認與稽核結果'),
    ]);
    expect(screen.getByRole('columnheader', { name: '原始值' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: '正規化值' })).toBeInTheDocument();
    expect(screen.getByText('MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE')).toBeInTheDocument();
  });
});

describe('設備匯入紀錄頁', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.mockReturnValue({ hasPermission: () => true });
    historyMock.mockReturnValue({
      data: { items: [], page: 1, page_size: 20, total: 0 },
      isLoading: false,
      isError: false,
    });
  });

  it('先預覽差異，未確認前不建立正式設備', async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue(batch);
    const csvFile = new File(
      ['設備編號,名稱\nEQ-071,卡尺'],
      'measurements.csv',
      { type: 'text/csv' },
    );

    render(<MsaImportHistoryPage />);

    await user.upload(screen.getByLabelText('設備清單檔案'), csvFile);
    await user.click(screen.getByRole('button', { name: '預覽匯入' }));

    expect(await screen.findByText('待人工確認 1 筆')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();
    expect(previewMock).toHaveBeenCalledWith({ file: csvFile });
    expect(confirmMock).not.toHaveBeenCalled();
  });

  it('沒有 msa.manage 時不顯示上傳與確認控制，但仍可讀歷史', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'msa.view',
    });

    render(<MsaImportHistoryPage />);

    expect(screen.queryByLabelText('設備清單檔案')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '預覽匯入' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '匯入稽核歷程' })).toBeInTheDocument();
  });
});
