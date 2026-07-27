import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
  useMsaStatusEvent: () => ({ mutateAsync: statusEventMock, isPending: false }),
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

describe('量測設備頁', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
      { ...baseEquipment, id: 2, equipment_no: 'EQ-DUE', calibration_status: 'due_soon' },
      {
        ...baseEquipment,
        id: 3,
        equipment_no: 'EQ-EXPIRED',
        calibration_status: 'expired',
        calibration_block_reason: '校驗已於 2026-07-01 到期',
      },
      { ...baseEquipment, id: 4, equipment_no: 'EQ-FAIL', calibration_status: 'failed' },
    ];
    equipmentQueryMock.mockReturnValue(queryResult(items));

    render(<MeasurementEquipmentPage />);

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

    await user.selectOptions(screen.getByLabelText('設備狀態'), 'active');
    await user.click(within(queue).getByRole('button', { name: /校驗逾期/ }));

    expect(screen.getByLabelText('校驗狀態')).toHaveValue('expired');
    expect(equipmentQueryMock).toHaveBeenLastCalledWith(expect.objectContaining({
      status: 'active',
      calibration_status: 'expired',
    }));
  });

  it('沒有 msa.manage 時不顯示新增、匯入與狀態變更動作', async () => {
    const user = userEvent.setup();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'msa.view',
    });

    render(<MeasurementEquipmentPage />);

    expect(screen.queryByRole('button', { name: '新增設備' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '匯入設備' })).not.toBeInTheDocument();

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    expect(await screen.findByRole('dialog', { name: /EQ-001/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '變更設備狀態' })).not.toBeInTheDocument();
  });

  it('逾期設備顯示阻擋原因，並提供表格與行動版校驗標籤卡', () => {
    equipmentQueryMock.mockReturnValue(queryResult([{
      ...baseEquipment,
      calibration_status: 'expired',
      calibration_block_reason: '校驗已於 2026-07-01 到期',
    }]));

    render(<MeasurementEquipmentPage />);

    expect(screen.getAllByText('校驗已於 2026-07-01 到期')).toHaveLength(2);
    expect(screen.getByRole('table', { name: '量測設備與校驗風險' })).toBeInTheDocument();
    expect(screen.getByLabelText('行動版設備清單')).toBeInTheDocument();
    expect(screen.getAllByText('逾期').length).toBeGreaterThan(1);
  });

  it('設備明細可追到校驗補正點、狀態事件與 CQI-9 來源連結', async () => {
    const user = userEvent.setup();
    render(<MeasurementEquipmentPage />);

    await user.click(screen.getAllByRole('button', { name: /查看 EQ-001/ })[0]);
    expect(await screen.findByRole('dialog', { name: /EQ-001/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '主檔與量測能力' })).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: '校驗與補正點' }));
    expect(screen.getByText('CERT-20')).toBeInTheDocument();
    expect(screen.getByText('-0.0020000000')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: '狀態事件' }));
    expect(screen.getByText('更換測砧')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'CQI-9 來源' }));
    expect(screen.getByText(/Recorder #12/)).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'MSA 研究引用' }));
    expect(screen.getByText('研究引用將於研究模組啟用後呈現')).toBeInTheDocument();
  });

  it('狀態變更送出目前 expected_status 與明確事件類型', async () => {
    const user = userEvent.setup();
    equipmentDetailMock.mockReturnValue({
      data: { ...detail, status: 'maintenance' },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    render(<MeasurementEquipmentPage />);

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

  it.each([
    ['loading', { data: undefined, isLoading: true, isError: false, refetch: vi.fn() }, '正在讀取設備證據'],
    ['error', { data: undefined, isLoading: false, isError: true, refetch: vi.fn() }, '無法載入設備清單'],
    ['empty', queryResult([]), '尚無符合條件的量測設備'],
  ])('提供 %s 狀態的可讀指引', (_name, result, text) => {
    equipmentQueryMock.mockReturnValue(result);

    render(<MeasurementEquipmentPage />);

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
