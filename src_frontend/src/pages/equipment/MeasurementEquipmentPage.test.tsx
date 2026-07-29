import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  EquipmentCalibration,
  MeasurementEquipment,
  MeasurementEquipmentDetail,
} from '../../types/msa';
import EquipmentCalibrationForm from '../../components/msa/EquipmentCalibrationForm';
import MeasurementEquipmentPage from './MeasurementEquipmentPage';

const authMock = vi.hoisted(() => vi.fn());
const equipmentQueryMock = vi.hoisted(() => vi.fn());
const equipmentDetailMock = vi.hoisted(() => vi.fn());
const createCalibrationMock = vi.hoisted(() => vi.fn());
const approveCalibrationMock = vi.hoisted(() => vi.fn());
const statusEventMock = vi.hoisted(() => vi.fn());
const updateEquipmentMock = vi.hoisted(() => vi.fn());
const downloadCertificateMock = vi.hoisted(() => vi.fn());

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

vi.mock('../../hooks/useMsaEquipment', () => ({
  useMsaEquipment: (params: unknown) => equipmentQueryMock(params),
  useMsaEquipmentDetail: (equipmentId: number | null) => equipmentDetailMock(equipmentId),
  useCreateMsaEquipment: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateMsaEquipment: () => ({ mutateAsync: updateEquipmentMock, isPending: false }),
  useMsaStatusEvent: () => ({ mutateAsync: statusEventMock, isPending: false }),
  useDownloadMsaCertificate: () => ({
    mutateAsync: downloadCertificateMock,
    isPending: false,
  }),
  useCreateMsaCalibration: () => ({
    mutateAsync: createCalibrationMock,
    isPending: false,
  }),
  useApproveMsaCalibration: () => ({
    mutateAsync: approveCalibrationMock,
    isPending: false,
  }),
}));

const baseEquipment: MeasurementEquipment = {
  id: 1,
  equipment_no: 'EQ-001',
  name: '外徑分厘卡',
  equipment_type: '分厘卡',
  manufacturer: 'Mitutoyo',
  model: 'M-01',
  serial_no: 'SN-001',
  range_min: '0.0000000000',
  range_max: '25.0000000000',
  resolution: '0.0010000000',
  unit: 'mm',
  department: '品保部',
  location: '量測室',
  custodian: '王小明',
  status: 'active',
  calibration_type: 'external',
  calibration_exemption_reason: null,
  calibration_interval_months: 12,
  calibration_status: 'valid',
  calibration_record_id: null,
  next_calibration_date: '2027-01-20',
  calibration_block_reason: null,
  is_reference_standard: false,
  affects_product_decision: true,
  created_by: 1,
  created_at: '2026-07-01T00:00:00+00:00',
  updated_by: 1,
  updated_at: '2026-07-27T00:00:00+00:00',
};

const calibration: EquipmentCalibration = {
  id: 20,
  equipment_id: 1,
  calibration_type: 'external',
  calibration_date: '2026-07-20',
  effective_date: '2026-07-20',
  next_due_date: '2027-01-20',
  calibration_provider: '校驗實驗室',
  certificate_no: 'CERT-20',
  reference_standard_no: null,
  reference_standard_due_date: null,
  traceability_standard: 'CNS 1234',
  uncertainty_statement: 'U=0.002 mm',
  result: 'pass',
  applicable_modes: ['外徑量測'],
  restriction_conditions: null,
  approval_reason: null,
  certificate_attachment_id: 99,
  status: 'draft',
  created_by: 2,
  created_at: '2026-07-20T08:00:00+00:00',
  approved_by: null,
  approved_at: null,
  data_level: 'summary_legacy',
  correction_points: [{
    id: 30,
    measurement_mode: '外徑量測',
    nominal_value: '10.0000000000',
    indicated_value: '10.0020000000',
    error_value: '0.0020000000',
    correction_value: '-0.0020000000',
    unit: 'mm',
    range_start: '0.0000000000',
    range_end: '25.0000000000',
  }],
};

const detail: MeasurementEquipmentDetail = {
  ...baseEquipment,
  calibrations: [calibration],
  status_events: [{
    id: 31,
    equipment_id: 1,
    event_type: 'major_adjustment',
    occurred_at: '2026-07-18T08:00:00+00:00',
    reason: '更換測砧',
    created_by: 2,
    triggers_msa_restudy: true,
  }],
  links: [{
    id: 41,
    equipment_id: 1,
    source_module: 'pyrometry',
    source_entity_type: 'Recorder',
    source_entity_id: 12,
    is_current: true,
    status: 'current',
  }],
};

const queryResult = (items: MeasurementEquipment[]) => ({
  data: { items, page: 1, page_size: 25, total: items.length },
  isLoading: false,
  isError: false,
  refetch: vi.fn(),
});

const renderEquipmentPage = () => render(
  <MemoryRouter>
    <MeasurementEquipmentPage />
  </MemoryRouter>,
);

describe('量測設備頁', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    statusEventMock.mockResolvedValue({});
    updateEquipmentMock.mockResolvedValue({});
    downloadCertificateMock.mockResolvedValue(undefined);
    authMock.mockReturnValue({
      hasPermission: () => true,
    });
    equipmentQueryMock.mockReturnValue(queryResult([baseEquipment]));
    equipmentDetailMock.mockImplementation((equipmentId: number | null) => ({
      data: equipmentId === 1 ? detail : undefined,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }));
  });

  it('以風險順序顯示設備，並將狀態與校驗狀態分開篩選', async () => {
    const user = userEvent.setup();
    const items: MeasurementEquipment[] = [
      { ...baseEquipment, id: 4, equipment_no: 'EQ-FAIL', calibration_status: 'failed' },
      {
        ...baseEquipment,
        id: 3,
        equipment_no: 'EQ-EXPIRED',
        calibration_status: 'expired',
        calibration_block_reason: '校驗已於 2026-07-01 到期',
      },
      { ...baseEquipment, id: 2, equipment_no: 'EQ-DUE', calibration_status: 'due_soon' },
    ];
    equipmentQueryMock.mockReturnValue(queryResult(items));

    renderEquipmentPage();

    const queue = screen.getByLabelText('設備風險佇列');
    expect(within(queue).getAllByRole('button').map((button) => button.textContent)).toEqual([
      expect.stringContaining('校驗失敗'),
      expect.stringContaining('校驗逾期'),
      expect.stringContaining('待確認'),
      expect.stringContaining('維修'),
      expect.stringContaining('30 日內到期'),
    ]);
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell')[1]?.textContent)).toEqual([
      expect.stringContaining('EQ-FAIL'),
      expect.stringContaining('EQ-EXPIRED'),
      expect.stringContaining('EQ-DUE'),
    ]);
    expect(equipmentQueryMock).toHaveBeenCalledWith(expect.objectContaining({
      sort: 'risk',
      order: 'asc',
    }));

    await user.selectOptions(screen.getByLabelText('設備狀態'), 'active');
    await user.click(within(queue).getByRole('button', { name: /校驗逾期/ }));

    expect(screen.getByLabelText('校驗狀態')).toHaveValue('expired');
    expect(equipmentQueryMock).toHaveBeenLastCalledWith(expect.objectContaining({
      status: 'active',
      calibration_status: 'expired',
    }));
  });

  it('沒有 calibration.manage 時不顯示新增、匯入與狀態變更動作', async () => {
    const user = userEvent.setup();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.view',
    });

    renderEquipmentPage();

    expect(screen.queryByRole('button', { name: '新增設備' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '匯入設備' })).not.toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    expect(await screen.findByRole('dialog', { name: /EQ-001/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '編輯主檔' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '變更設備狀態' })).not.toBeInTheDocument();
  });

  it('設備管理者沒有 msa.manage 時可新增設備但不顯示舊匯入入口', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.manage',
    });

    renderEquipmentPage();

    expect(screen.getByRole('button', { name: '新增設備' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '匯入設備' }))
      .not.toBeInTheDocument();
  });

  it('具 calibration.manage 權限時可編輯主檔並保留未修改欄位的目前值', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    const equipmentWithEmptyRangeMin = { ...detail, range_min: null };
    equipmentDetailMock.mockImplementation((equipmentId: number | null) => ({
      data: equipmentId === 1 ? equipmentWithEmptyRangeMin : undefined,
      isLoading: false,
      isError: false,
      refetch,
    }));
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.manage',
    });

    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.click(screen.getByRole('button', { name: '編輯主檔' }));
    const name = screen.getByLabelText('設備名稱');
    await user.clear(name);
    await user.type(name, '外徑分厘卡（已校正）');
    await user.click(screen.getByRole('button', { name: '儲存主檔' }));

    await waitFor(() => expect(updateEquipmentMock).toHaveBeenCalledWith({
      equipmentId: 1,
      payload: {
        name: '外徑分厘卡（已校正）',
        equipment_type: '分厘卡',
        manufacturer: 'Mitutoyo',
        model: 'M-01',
        serial_no: 'SN-001',
        range_min: null,
        range_max: '25.0000000000',
        resolution: '0.0010000000',
        unit: 'mm',
        department: '品保部',
        location: '量測室',
        custodian: '王小明',
        calibration_type: 'external',
        calibration_interval_months: 12,
      },
    }));
    await waitFor(() => expect(refetch).toHaveBeenCalled());
  });

  it('逾期設備顯示阻擋原因，並提供表格與行動版校驗標籤卡', () => {
    equipmentQueryMock.mockReturnValue(queryResult([{
      ...baseEquipment,
      calibration_status: 'expired',
      calibration_block_reason: '校驗已於 2026-07-01 到期',
    }]));

    renderEquipmentPage();

    expect(screen.getAllByText('校驗已於 2026-07-01 到期')).toHaveLength(2);
    expect(screen.getByRole('table', { name: '量測設備與校驗風險' })).toBeInTheDocument();
    expect(screen.getByLabelText('行動版設備清單')).toBeInTheDocument();
    expect(screen.getAllByText('逾期').length).toBeGreaterThan(1);
  });

  it('設備明細可追到校驗補正點、狀態事件與 CQI-9 來源連結', async () => {
    const user = userEvent.setup();
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    expect(await screen.findByRole('dialog', { name: /EQ-001/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '主檔與量測能力' })).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: '校驗與補正點' }));
    expect(screen.getByText('舊版摘要資料')).toBeInTheDocument();
    expect(screen.queryByText('原始讀值')).not.toBeInTheDocument();
    expect(screen.getByText('CERT-20')).toBeInTheDocument();
    expect(screen.getByText('-0.0020000000')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: '狀態事件' }));
    expect(screen.getByText('更換測砧')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'CQI-9 來源' }));
    expect(screen.getByText(/Recorder #12/)).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'MSA 研究引用' }));
    expect(screen.getByText('研究引用將於研究模組啟用後呈現')).toBeInTheDocument();
  });

  it('校正主管由設備明細建立完整詳細校正，不再使用舊摘要草稿表單', async () => {
    const user = userEvent.setup();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => (
        permission === 'calibration.execute'
        || permission === 'calibration.manage'
      ),
    });
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.click(screen.getByRole('tab', { name: '校驗與補正點' }));

    expect(screen.getByRole('link', { name: '建立詳細校正' }))
      .toHaveAttribute(
        'href',
        '/measurement-equipment/1/calibrations/new',
      );
    expect(screen.queryByRole('button', { name: '儲存校驗草稿' }))
      .not.toBeInTheDocument();
  });

  it('只有 calibration.manage 而沒有 execute 時不顯示建立詳細校正', async () => {
    const user = userEvent.setup();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.manage',
    });
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.click(screen.getByRole('tab', { name: '校驗與補正點' }));

    expect(screen.queryByRole('link', { name: '建立詳細校正' }))
      .not.toBeInTheDocument();
  });

  it('只有 calibration.execute 時不顯示需要主管送審權限的完整精靈', async () => {
    const user = userEvent.setup();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.execute',
    });
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.click(screen.getByRole('tab', { name: '校驗與補正點' }));

    expect(screen.queryByRole('link', { name: '建立詳細校正' }))
      .not.toBeInTheDocument();
  });

  it.each([
    ['submitted', '已送審'],
    ['rejected', '已退回'],
    ['voided', '已作廢'],
  ] as const)('詳細校正 %s 顯示正確工作流狀態', async (status, label) => {
    const user = userEvent.setup();
    equipmentDetailMock.mockReturnValue({
      data: {
        ...detail,
        calibrations: [{
          ...calibration,
          data_level: 'detailed',
          status,
        }],
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.click(screen.getByRole('tab', { name: '校驗與補正點' }));

    expect(screen.getByText('詳細校正資料')).toBeInTheDocument();
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('狀態變更送出目前 expected_status 與明確事件類型', async () => {
    const user = userEvent.setup();
    equipmentDetailMock.mockReturnValue({
      data: { ...detail, status: 'maintenance' },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.selectOptions(screen.getByLabelText('目標狀態'), 'active');
    await user.type(screen.getByLabelText('變更原因'), '維修與複驗完成');
    await user.click(screen.getByRole('button', { name: '變更設備狀態' }));

    expect(statusEventMock).toHaveBeenCalledWith({
      equipmentId: 1,
      event_type: 'reactivated',
      expected_status: 'maintenance',
      target_status: 'active',
      reason: '維修與複驗完成',
    });
  });

  it('待確認完成送出 review_completed，且目標狀態不含目前狀態', async () => {
    const user = userEvent.setup();
    equipmentDetailMock.mockReturnValue({
      data: { ...detail, status: 'pending_review' },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    const select = screen.getByLabelText('目標狀態');
    expect(within(select).queryByRole('option', { name: '待確認' })).not.toBeInTheDocument();
    await user.selectOptions(select, 'active');
    await user.type(screen.getByLabelText('變更原因'), '審查完成');
    await user.click(screen.getByRole('button', { name: '變更設備狀態' }));

    expect(statusEventMock).toHaveBeenCalledWith({
      equipmentId: 1,
      event_type: 'review_completed',
      expected_status: 'pending_review',
      target_status: 'active',
      reason: '審查完成',
    });
  });

  it('狀態轉移遇到 409 或 422 時在抽屜顯示錯誤', async () => {
    const user = userEvent.setup();
    statusEventMock.mockRejectedValueOnce(Object.assign(
      new Error('設備狀態已變更，請重新載入'),
      { status: 409, code: 'MSA_EQUIPMENT_STATUS_CONFLICT' },
    ));
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.type(screen.getByLabelText('變更原因'), '年度保養');
    await user.click(screen.getByRole('button', { name: '變更設備狀態' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('設備狀態已變更，請重新載入');
  });

  it('證書以認證 blob 下載，CQI-9 來源連到可查詢的專頁', async () => {
    const user = userEvent.setup();
    downloadCertificateMock.mockResolvedValue(undefined);
    renderEquipmentPage();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    await user.click(screen.getByRole('tab', { name: '校驗與補正點' }));
    await user.click(screen.getByRole('button', { name: '下載證書 CERT-20' }));
    expect(downloadCertificateMock).toHaveBeenCalledWith({
      attachmentId: 99,
      filename: 'CERT-20.pdf',
    });

    await user.click(screen.getByRole('tab', { name: 'CQI-9 來源' }));
    expect(screen.getByRole('link', { name: /Recorder #12/ })).toHaveAttribute(
      'href',
      '/pyrometry/recorders',
    );
    expect(screen.getByText(/請在記錄器校正頁查詢 ID 12/)).toBeInTheDocument();
  });

  it('建立設備使用可聚焦 Modal，Escape 關閉後焦點回到觸發按鈕', async () => {
    const user = userEvent.setup();
    renderEquipmentPage();
    const trigger = screen.getByRole('button', { name: '新增設備' });

    await user.click(trigger);
    const equipmentNo = await screen.findByLabelText('設備編號');
    expect(equipmentNo).toHaveFocus();
    await user.keyboard('{Escape}');
    await waitFor(() => expect(
      screen.queryByRole('dialog', { name: '新增量測設備' }),
    ).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it('抽屜分頁具有 tab/tabpanel 關聯並支援方向鍵切換', async () => {
    const user = userEvent.setup();
    renderEquipmentPage();
    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);

    const masterTab = screen.getByRole('tab', { name: '主檔與能力' });
    expect(masterTab).toHaveAttribute('aria-controls', 'equipment-tab-master');
    expect(screen.getByRole('tabpanel')).toHaveAttribute(
      'aria-labelledby',
      'equipment-tab-master-tab',
    );
    masterTab.focus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: '校驗與補正點' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('設備明細載入與錯誤狀態可讀且可重試', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    equipmentDetailMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch,
    });
    const { rerender } = renderEquipmentPage();
    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    expect(screen.getByText('正在讀取設備明細…')).toBeInTheDocument();

    equipmentDetailMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    });
    rerender(
      <MemoryRouter>
        <MeasurementEquipmentPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('無法載入設備明細');
    await user.click(screen.getByRole('button', { name: '重試' }));
    expect(refetch).toHaveBeenCalled();
  });

  it.each([
    ['loading', { data: undefined, isLoading: true, isError: false, refetch: vi.fn() }, '正在讀取設備證據'],
    ['error', { data: undefined, isLoading: false, isError: true, refetch: vi.fn() }, '無法載入設備清單'],
    ['empty', queryResult([]), '尚無符合條件的量測設備'],
  ])('提供 %s 狀態的可讀指引', (_name, result, text) => {
    equipmentQueryMock.mockReturnValue(result);

    renderEquipmentPage();

    expect(screen.getByText(text)).toBeInTheDocument();
  });
});

describe('設備校驗表單', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'msa.approve',
    });
  });

  it('核准 draft 時送出 expected_status 與核准理由', async () => {
    const user = userEvent.setup();
    approveCalibrationMock.mockResolvedValue({ ...calibration, status: 'approved' });

    render(<EquipmentCalibrationForm equipmentId={1} calibrations={[calibration]} />);

    await user.type(screen.getByLabelText('校驗核准理由'), '證書與補正點均已核對');
    await user.click(screen.getByRole('button', { name: '核准校驗 CERT-20' }));

    expect(approveCalibrationMock).toHaveBeenCalledWith({
      calibrationId: 20,
      equipmentId: 1,
      expected_status: 'draft',
      reason: '證書與補正點均已核對',
    });
  });

  it('以補正點建立 draft，不把草稿直接當成正式證據', async () => {
    const user = userEvent.setup();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'msa.manage',
    });
    createCalibrationMock.mockResolvedValue(calibration);
    render(<EquipmentCalibrationForm equipmentId={1} calibrations={[]} />);

    await user.type(screen.getByLabelText('校驗日期'), '2026-07-27');
    await user.type(screen.getByLabelText('下次校驗日'), '2027-07-27');
    await user.type(screen.getByLabelText('證書編號'), 'CERT-NEW');
    await user.type(screen.getByLabelText('名目值'), '10');
    await user.type(screen.getByLabelText('器示值'), '10.002');
    await user.type(screen.getByLabelText('補正值'), '-0.002');
    await user.type(screen.getByLabelText('單位'), 'mm');
    await user.click(screen.getByRole('button', { name: '儲存校驗草稿' }));

    expect(createCalibrationMock).toHaveBeenCalledWith(expect.objectContaining({
      equipmentId: 1,
      calibration_type: 'external',
      calibration_date: '2026-07-27',
      next_due_date: '2027-07-27',
      certificate_no: 'CERT-NEW',
      result: 'pass',
      correction_points: [
        expect.objectContaining({
          nominal_value: '10',
          indicated_value: '10.002',
          correction_value: '-0.002',
          unit: 'mm',
        }),
      ],
    }));
  });

  it('校驗草稿可將補正點移除為零筆後再新增', async () => {
    const user = userEvent.setup();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'msa.manage',
    });
    render(<EquipmentCalibrationForm equipmentId={1} calibrations={[]} />);

    await user.click(screen.getByRole('button', { name: '移除補正點' }));
    expect(screen.queryByLabelText('名目值')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '新增補正點' }));
    expect(screen.getByLabelText('名目值')).toBeInTheDocument();
  });
});
