import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { EquipmentImportBatch, EquipmentImportResolution } from '../../types/msa';
import type { IssueMap, ResolutionMap } from './EquipmentImportReview';
import MsaImportHistoryPage from '../../pages/msa/MsaImportHistoryPage';
import EquipmentImportReview from './EquipmentImportReview';

const authMock = vi.hoisted(() => vi.fn());
const previewMock = vi.hoisted(() => vi.fn());
const confirmMock = vi.hoisted(() => vi.fn());
const historyMock = vi.hoisted(() => vi.fn());
const batchDetailMock = vi.hoisted(() => vi.fn());

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
  useMsaImportBatch: (batchId: number | null, params: unknown) => (
    batchDetailMock(batchId, params)
  ),
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
  rows_total: 2,
  row_page: 1,
  row_page_size: 100,
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

const StatefulReview = ({
  initialBatch,
  onConfirm,
  onRowPageChange,
}: {
  initialBatch: EquipmentImportBatch;
  onConfirm?: (resolutions: ResolutionMap) => void | Promise<void>;
  onRowPageChange?: (page: number) => void;
}) => {
  const [resolutions, setResolutions] = useState<ResolutionMap>({});
  const [resolutionIssues, setResolutionIssues] = useState<IssueMap>({});

  const handleResolutionChange = (
    rowId: number,
    issueCodes: string[],
    patch: Partial<EquipmentImportResolution>,
  ) => {
    setResolutionIssues((c) => ({ ...c, [rowId]: issueCodes }));
    setResolutions((c) => ({ ...c, [rowId]: { ...c[rowId], ...patch } }));
  };

  return (
    <EquipmentImportReview
      batch={initialBatch}
      resolutions={resolutions}
      resolutionIssues={resolutionIssues}
      onResolutionChange={handleResolutionChange}
      onConfirm={onConfirm}
      onRowPageChange={onRowPageChange}
    />
  );
};

describe('設備匯入檢閱', () => {
  beforeEach(() => vi.clearAllMocks());

  it('不以 HTML 呈現來源提醒文字', () => {
    render(<StatefulReview initialBatch={batch} />);

    expect(screen.getByText(/校驗即將到期/)).toBeInTheDocument();
    expect(document.querySelector('span.danger')).toBeNull();
  });

  it('逐列解決遊校映射後才能確認，且不提供全部忽略', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<StatefulReview initialBatch={batch} onConfirm={onConfirm} />);

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
    render(<StatefulReview initialBatch={batch} />);

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

  it('免校理由缺漏可直接填理由，不依賴校驗類別問題碼', async () => {
    const user = userEvent.setup();
    const exemptBatch: EquipmentImportBatch = {
      ...batch,
      total_rows: 1,
      pending_rows: 1,
      rows_total: 1,
      rows: [{
        ...batch.rows[0],
        normalized: { equipment_no: 'EQ-071', calibration_type: 'exempt' },
        issue_codes: ['MSA_IMPORT_EXEMPTION_REASON_MISSING'],
      }],
    };
    render(<StatefulReview initialBatch={exemptBatch} onConfirm={vi.fn()} />);

    const row = screen.getByRole('row', { name: /原始列 2/ });
    await user.selectOptions(within(row).getByLabelText('列 2 處置'), 'accept');
    expect(within(row).getByLabelText('列 2 免校理由')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();
    await user.type(within(row).getByLabelText('列 2 免校理由'), '僅供目視參考');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeEnabled();
  });

  it('序號問題必須填寫序號或拒絕，未知 blocking issue 只能拒絕', async () => {
    const user = userEvent.setup();
    const serialBatch: EquipmentImportBatch = {
      ...batch,
      total_rows: 2,
      pending_rows: 2,
      rows_total: 2,
      rows: [
        {
          ...batch.rows[0],
          issue_codes: ['MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX'],
        },
        {
          ...batch.rows[1],
          issue_codes: ['MSA_IMPORT_FUTURE_BLOCKING_CODE'],
        },
      ],
    };
    render(<StatefulReview initialBatch={serialBatch} onConfirm={vi.fn()} />);

    const serialRow = screen.getByRole('row', { name: /原始列 2/ });
    await user.selectOptions(within(serialRow).getByLabelText('列 2 處置'), 'accept');
    expect(within(serialRow).getByLabelText('列 2 序號')).toBeInTheDocument();

    const unknownRow = screen.getByRole('row', { name: /原始列 3/ });
    expect(
      within(unknownRow).getByLabelText('列 3 處置').querySelectorAll('option'),
    ).toHaveLength(2);
    await user.selectOptions(within(unknownRow).getByLabelText('列 3 處置'), 'reject');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();
    await user.type(within(serialRow).getByLabelText('列 2 序號'), 'SN-071');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeEnabled();
  });

  it('多個可修復問題必須全部填妥才視為完成', async () => {
    const user = userEvent.setup();
    const combinedBatch: EquipmentImportBatch = {
      ...batch,
      total_rows: 1,
      pending_rows: 1,
      rows_total: 1,
      rows: [{
        ...batch.rows[0],
        issue_codes: [
          'MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE',
          'MSA_IMPORT_RESOLUTION_MISSING',
          'MSA_IMPORT_MODEL_MISSING',
        ],
      }],
    };
    render(<StatefulReview initialBatch={combinedBatch} onConfirm={vi.fn()} />);
    const row = screen.getByRole('row', { name: /原始列 2/ });

    await user.selectOptions(within(row).getByLabelText('列 2 處置'), 'accept');
    await user.selectOptions(within(row).getByLabelText('列 2 校驗類別映射'), 'external');
    await user.type(within(row).getByLabelText('列 2 解析度'), '0.01');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();
    await user.type(within(row).getByLabelText('列 2 型號'), 'M-01');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeEnabled();
  });

  it('逐列處置跨分頁保留，直到全部 pending rows 完成才可確認', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    const firstPage: EquipmentImportBatch = {
      ...batch,
      total_rows: 2,
      pending_rows: 2,
      rows_total: 2,
      row_page_size: 1,
      rows: [{
        ...batch.rows[0],
        issue_codes: ['MSA_IMPORT_MODEL_MISSING'],
      }],
    };

    const StatefulWrapper = ({ currentPageBatch }: { currentPageBatch: EquipmentImportBatch }) => {
      const [resolutions, setResolutions] = useState<ResolutionMap>({});
      const [resolutionIssues, setResolutionIssues] = useState<IssueMap>({});

      const handleResolutionChange = (
        rowId: number,
        issueCodes: string[],
        patch: Partial<EquipmentImportResolution>,
      ) => {
        setResolutionIssues((c) => ({ ...c, [rowId]: issueCodes }));
        setResolutions((c) => ({ ...c, [rowId]: { ...c[rowId], ...patch } }));
      };

      return (
        <EquipmentImportReview
          batch={currentPageBatch}
          resolutions={resolutions}
          resolutionIssues={resolutionIssues}
          onResolutionChange={handleResolutionChange}
          onConfirm={vi.fn()}
          onRowPageChange={onPageChange}
        />
      );
    };

    const { rerender } = render(<StatefulWrapper currentPageBatch={firstPage} />);
    let row = screen.getByRole('row', { name: /原始列 2/ });
    await user.selectOptions(within(row).getByLabelText('列 2 處置'), 'accept');
    await user.type(within(row).getByLabelText('列 2 型號'), 'M-01');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: '下一頁逐列證據' }));
    expect(onPageChange).toHaveBeenCalledWith(2);

    const secondPageBatch: EquipmentImportBatch = {
      ...firstPage,
      row_page: 2,
      rows: [{
        ...batch.rows[1],
        issue_codes: ['MSA_IMPORT_CUSTODIAN_MISSING'],
      }],
    };
    rerender(<StatefulWrapper currentPageBatch={secondPageBatch} />);
    row = screen.getByRole('row', { name: /原始列 3/ });
    await user.selectOptions(within(row).getByLabelText('列 3 處置'), 'pending_review');
    await user.type(within(row).getByLabelText('列 3 保管人'), '王小明');
    expect(screen.getByRole('button', { name: '確認匯入' })).toBeEnabled();
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
    batchDetailMock.mockReturnValue({
      data: undefined,
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

  it('沒有 calibration.view 時返回 MSA 工作台而不是不可達設備頁', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'msa.view',
    });

    render(<MsaImportHistoryPage />);

    expect(screen.getByRole('link', { name: '返回 MSA 工作台' }))
      .toHaveAttribute('href', '/msa');
    expect(screen.queryByRole('link', { name: '返回設備清單' }))
      .not.toBeInTheDocument();
  });

  it('大型批次從歷程載入時以 row_page 分頁查詢', async () => {
    const user = userEvent.setup();
    historyMock.mockReturnValue({
      data: {
        items: [{
          id: batch.id,
          original_filename: batch.original_filename,
          file_sha256: batch.file_sha256,
          file_size: batch.file_size,
          status: batch.status,
          total_rows: batch.total_rows,
          success_rows: batch.success_rows,
          pending_rows: batch.pending_rows,
          rejected_rows: batch.rejected_rows,
          parser_version: batch.parser_version,
          uploaded_by: batch.uploaded_by,
          uploaded_at: batch.uploaded_at,
        }],
        page: 1,
        page_size: 20,
        total: 1,
      },
      isLoading: false,
      isError: false,
    });
    batchDetailMock.mockImplementation((
      batchId: number | null,
      requestedParams?: { row_page: number; row_page_size: number },
    ) => {
      const params = requestedParams ?? { row_page: 1, row_page_size: 100 };
      return {
      data: batchId == null ? undefined : {
        ...batch,
        rows_total: 2,
        row_page: params.row_page,
        row_page_size: 1,
        rows: [batch.rows[params.row_page - 1]],
      },
      isLoading: false,
      isError: false,
      };
    });

    render(<MsaImportHistoryPage />);
    await user.click(screen.getByRole('button', { name: '檢視逐列證據' }));
    expect(batchDetailMock).toHaveBeenLastCalledWith(41, {
      row_page: 1,
      row_page_size: 100,
    });
    await user.click(screen.getByRole('button', { name: '下一頁逐列證據' }));
    expect(batchDetailMock).toHaveBeenLastCalledWith(41, {
      row_page: 2,
      row_page_size: 100,
    });
  });
});
