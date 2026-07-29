import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../services/apiError';
import CalibrationDetailPage from './CalibrationDetailPage';

const authMock = vi.hoisted(() => vi.fn());
const detailMock = vi.hoisted(() => vi.fn());
const approveMock = vi.hoisted(() => vi.fn());
const rejectMock = vi.hoisted(() => vi.fn());
const voidMock = vi.hoisted(() => vi.fn());
const downloadMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useCalibrations', () => ({
  useCalibration: (id: number) => detailMock(id),
  useApproveCalibration: () => ({ mutateAsync: approveMock, isPending: false }),
  useRejectCalibration: () => ({ mutateAsync: rejectMock, isPending: false }),
  useVoidCalibration: () => ({ mutateAsync: voidMock, isPending: false }),
  useDownloadCalibrationCertificate: () => ({ mutateAsync: downloadMock }),
}));

const calibration = {
  id: 41,
  equipment_id: 14,
  equipment_no: 'MIC-014',
  equipment_name: '外徑分厘卡',
  calibration_type: 'internal',
  calibration_date: '2026-07-23',
  effective_date: '2026-07-23',
  next_due_date: '2027-07-22',
  calibration_provider: null,
  certificate_no: 'CERT-2026-014',
  traceability_standard: 'CNS 12681',
  uncertainty_statement: 'k=2',
  result: 'pass',
  applicable_modes: ['量測'],
  restriction_conditions: null,
  approval_reason: null,
  reference_standard_no: 'STD-002',
  reference_standard_due_date: '2027-02-01',
  template_version_id: 8,
  data_level: 'detailed',
  row_version: 7,
  template_snapshot: { template_code: 'TPL-MIC-001', version_no: 3 },
  environment_conditions: { temperature_c: '23.1' },
  calculation_summary: { calculation_version: '2.1.0', result: 'pass' },
  calculation_version: '2.1.0',
  data_hash: 'sha256:abc123',
  procedure_code: 'WI-CAL-014',
  procedure_name: '外徑分厘卡內校',
  calibration_location: '量測室',
  started_at: '2026-07-23T08:00:00+08:00',
  completed_at: '2026-07-23T08:30:00+08:00',
  reference_standard_equipment_id: 2,
  submitted_by: 9,
  submitted_at: '2026-07-23T09:00:00+08:00',
  rejection_reason: null,
  void_reason: null,
  successor_id: null,
  predecessor_id: null,
  certificate_attachment_id: 88,
  status: 'submitted',
  created_by: 6,
  created_at: '2026-07-23T08:00:00+08:00',
  approved_by: null,
  approved_at: null,
  points: [{
    id: 81,
    template_point_id: 18,
    point_order: 1,
    point_code: 'P01',
    measurement_mode: 'direct',
    nominal_value: '10.000',
    unit: 'mm',
    reference_value: '10.000',
    error_lower_limit: '-0.004',
    error_upper_limit: '0.004',
    evaluation_basis: 'error',
    repeatability_rule: 'range',
    repeatability_limit: '0.002',
    qualification_scope_code: '0-25mm',
    qualification_range_start: '0',
    qualification_range_end: '25',
    uncertainty_required: true,
    required: true,
    required_repetitions: 2,
    average_value: '10.001',
    error_value: '0.001',
    repeatability_value: '0.001',
    mean_error: '0.001',
    mean_correction: '-0.001',
    minimum_error: '0.000',
    maximum_error: '0.001',
    error_range: '0.001',
    sample_stddev: '0.0007',
    expanded_uncertainty: '0.0014',
    coverage_factor: '2',
    completed_reading_count: 2,
    result: 'pass',
    remarks: null,
    readings: [{
      id: 801,
      trial_no: 1,
      standard_reading: '10.000',
      indicated_value: '10.001',
      effective_reference: '10.000',
      error_value: '0.001',
      correction_value: '-0.001',
      result: 'pass',
      entered_by: 6,
      entered_at: '2026-07-23T08:05:00+08:00',
      last_modified_by: 6,
      last_modified_at: '2026-07-23T08:05:00+08:00',
      revision_reason: null,
    }],
  }],
  reference_snapshots: [{
    id: 31,
    reference_standard_equipment_id: 2,
    equipment_no: 'STD-002',
    name: '標準量塊',
    model: 'GB-10',
    serial_no: 'SN-2002',
    range_min: '0',
    range_max: '25',
    resolution: '0.001',
    unit: 'mm',
    calibration_date: '2026-02-01',
    certificate_no: 'STD-CERT-2',
    calibration_due_date: '2027-02-01',
    result: 'pass',
    data_hash: 'sha256:std',
    traceability_standard: 'TAF',
    snapshot_data: { qualified: true },
    created_at: '2026-07-23T08:00:00+08:00',
  }],
};

const renderPage = () => render(
  <MemoryRouter initialEntries={['/calibrations/41']}>
    <Routes><Route path="/calibrations/:calibrationId" element={<CalibrationDetailPage />} /></Routes>
  </MemoryRouter>,
);

describe('校正分層證據詳情', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => (
        permission === 'calibration.view' || permission === 'calibration.approve'
      ),
    });
    detailMock.mockReturnValue({ data: calibration, isLoading: false, isError: false, refetch: vi.fn() });
    approveMock.mockResolvedValue(calibration);
    rejectMock.mockResolvedValue(calibration);
    voidMock.mockResolvedValue(calibration);
  });

  it('核准前必須確認五層證據並填寫理由', async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByRole('heading', { name: '校正紀錄 CAL-2026-0041' });
    await user.type(screen.getByLabelText('核准理由'), '計算與追溯證據均已核對');
    expect(screen.getByRole('button', { name: '核准校正' })).toBeDisabled();

    for (const label of [
      '已核對原始讀值', '已核對計算結果', '已核對標準器資格',
      '已核對證書附件', '已核對模板版本',
    ]) {
      await user.click(screen.getByLabelText(label));
    }

    expect(screen.getByRole('button', { name: '核准校正' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: '核准校正' }));
    await waitFor(() => expect(approveMock).toHaveBeenCalledWith({
      calibrationId: 41,
      expected_version: 7,
      reason: '計算與追溯證據均已核對',
      confirmations: {
        raw_readings: true,
        calculations: true,
        reference_standard: true,
        attachments: true,
        template_version: true,
      },
    }));
  });

  it('依判定、摘要、讀值、快照、附件、簽核、版本順序呈現證據', () => {
    renderPage();
    const text = screen.getByRole('main').textContent ?? '';

    for (const label of ['判定摘要', '校正點摘要', '原始讀值', '標準器快照', '證書附件', '簽核紀錄', '模板版本快照']) {
      expect(text.indexOf(label)).toBeGreaterThanOrEqual(0);
    }
    expect(text.indexOf('判定摘要')).toBeLessThan(text.indexOf('校正點摘要'));
    expect(text.indexOf('校正點摘要')).toBeLessThan(text.indexOf('原始讀值'));
    expect(text.indexOf('原始讀值')).toBeLessThan(text.indexOf('標準器快照'));
    expect(text.indexOf('標準器快照')).toBeLessThan(text.indexOf('證書附件'));
    expect(text.indexOf('證書附件')).toBeLessThan(text.indexOf('簽核紀錄'));
    expect(text.indexOf('簽核紀錄')).toBeLessThan(text.indexOf('模板版本快照'));
    expect(screen.getByTestId('mobile-reading-P01-1')).toHaveTextContent('10.001');
    expect(screen.getByRole('region', { name: '原始讀值' }))
      .toHaveAttribute('data-responsive-layout', 'single-column-cards');
  });

  it('legacy 紀錄只顯示摘要層與資料限制', () => {
    detailMock.mockReturnValue({
      data: { ...calibration, data_level: 'summary_legacy', points: [], reference_snapshots: [] },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    renderPage();

    expect(screen.getByRole('alert')).toHaveTextContent('舊版摘要資料未保存逐點原始讀值');
    for (const heading of [
      '校正點摘要', '原始讀值', '標準器快照', '證書附件',
      '簽核紀錄', '模板版本快照',
    ]) {
      expect(screen.queryByRole('heading', { name: heading })).not.toBeInTheDocument();
    }
  });

  it.each([
    [403, 'CALIBRATION_SELF_APPROVAL_FORBIDDEN', '建立、輸入或送審人員不得核准自己的校正紀錄'],
    [409, 'CALIBRATION_VERSION_CONFLICT', '校正紀錄已被其他人更新，請重新載入'],
    [422, 'CALIBRATION_FIELD_INVALID', '核准確認項目必須完整勾選'],
  ])('保留 %i 的結構化錯誤、中文訊息與 details', async (status, code, message) => {
    const user = userEvent.setup();
    approveMock.mockRejectedValue(new ApiError({
      message,
      status,
      code,
      details: { field: 'confirmations', calibration_id: 41 },
    }));
    renderPage();
    await user.type(screen.getByLabelText('核准理由'), '已完成核對');
    for (const label of ['已核對原始讀值', '已核對計算結果', '已核對標準器資格', '已核對證書附件', '已核對模板版本']) {
      await user.click(screen.getByLabelText(label));
    }
    await user.click(screen.getByRole('button', { name: '核准校正' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveAttribute('data-error-status', String(status));
    expect(alert).toHaveAttribute('data-error-code', code);
    expect(alert).toHaveTextContent(code);
    expect(alert).toHaveTextContent(message);
    expect(alert).toHaveTextContent('field: confirmations');
    expect(alert).toHaveTextContent('calibration_id: 41');
  });

  it('依權限與狀態顯示核准、退回與作廢操作', () => {
    renderPage();
    expect(screen.getByRole('button', { name: '核准校正' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退回校正' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '作廢校正' })).not.toBeInTheDocument();
  });

  it('具有管理權且進行中的紀錄可作廢，但不顯示核准控制', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.manage',
    });
    detailMock.mockReturnValue({
      data: { ...calibration, status: 'in_progress' },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    renderPage();

    expect(screen.getByRole('button', { name: '作廢校正' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '核准校正' })).not.toBeInTheDocument();
    expect(within(screen.getByRole('main')).getByText('進行中')).toBeInTheDocument();
  });

  it.each([
    ['無權限', 'submitted', () => false, false, false, false],
    ['核准者送審', 'submitted', (permission: string) => permission === 'calibration.approve', true, true, false],
    ['管理者草稿', 'draft', (permission: string) => permission === 'calibration.manage', false, false, true],
    ['管理者登錄中', 'in_progress', (permission: string) => permission === 'calibration.manage', false, false, true],
    ['管理者待送審', 'ready_for_submission', (permission: string) => permission === 'calibration.manage', false, false, true],
    ['管理者已核准', 'approved', (permission: string) => permission === 'calibration.manage', false, false, false],
    ['管理者已退回', 'rejected', (permission: string) => permission === 'calibration.manage', false, false, false],
    ['管理者已作廢', 'voided', (permission: string) => permission === 'calibration.manage', false, false, false],
    ['管理者已取代', 'superseded', (permission: string) => permission === 'calibration.manage', false, false, false],
  ])('%s 的狀態與權限操作矩陣正確', (
    _caseName,
    status,
    hasPermission,
    canApprove,
    canReject,
    canVoid,
  ) => {
    authMock.mockReturnValue({ hasPermission });
    detailMock.mockReturnValue({
      data: { ...calibration, status },
      isLoading: false, isError: false, refetch: vi.fn(),
    });
    renderPage();

    expect(Boolean(screen.queryByRole('button', { name: '核准校正' }))).toBe(canApprove);
    expect(Boolean(screen.queryByRole('button', { name: '退回校正' }))).toBe(canReject);
    expect(Boolean(screen.queryByRole('button', { name: '作廢校正' }))).toBe(canVoid);
  });
});
