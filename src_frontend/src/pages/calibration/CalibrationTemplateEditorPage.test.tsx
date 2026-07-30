import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../services/apiError';
import CalibrationTemplateEditorPage from './CalibrationTemplateEditorPage';

const authMock = vi.hoisted(() => vi.fn());
const detailMock = vi.hoisted(() => vi.fn());
const createVersionMock = vi.hoisted(() => vi.fn());
const updateVersionMock = vi.hoisted(() => vi.fn());
const submitMock = vi.hoisted(() => vi.fn());
const submitPendingMock = vi.hoisted(() => vi.fn());
const approveMock = vi.hoisted(() => vi.fn());
const rejectMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useCalibrationTemplates', () => ({
  useCalibrationTemplate: (id: number | null) => detailMock(id),
  useCreateCalibrationTemplateVersion: () => ({
    mutateAsync: createVersionMock, isPending: false,
  }),
  useUpdateCalibrationTemplateVersion: () => ({
    mutateAsync: updateVersionMock, isPending: false,
  }),
  useSubmitCalibrationTemplateVersion: () => ({
    mutateAsync: submitMock, isPending: submitPendingMock(),
  }),
  useApproveCalibrationTemplateVersion: () => ({
    mutateAsync: approveMock, isPending: false,
  }),
  useRejectCalibrationTemplateVersion: () => ({
    mutateAsync: rejectMock, isPending: false,
  }),
}));

const point = {
  id: 91,
  template_version_id: 12,
  point_order: 1,
  point_code: 'P01',
  measurement_mode: '外徑',
  nominal_value: '10.000',
  unit: 'mm',
  reference_input_mode: 'certified_value',
  required_repetitions: 3,
  error_lower_limit: '-0.003',
  error_upper_limit: '0.003',
  evaluation_basis: 'all_readings',
  repeatability_rule: 'range',
  repeatability_limit: '0.002',
  qualification_scope_code: 'OD-0-25',
  qualification_range_start: '0',
  qualification_range_end: '25',
  uncertainty_required: true,
  required: true,
};

const version = (overrides = {}) => ({
  id: 12,
  template_id: 7,
  version_no: 3,
  procedure_code: 'WI-MET-014',
  procedure_name: '分厘卡內校程序',
  procedure_description: '依標準塊逐點校正',
  default_repetitions: 3,
  environment_requirements: {},
  allow_limited_use: false,
  status: 'draft',
  row_version: 4,
  revision_reason: '新增 25 mm 校正點',
  created_by: 5,
  created_at: '2026-07-18T08:00:00+00:00',
  submitted_by: null,
  submitted_at: null,
  approved_by: null,
  approved_at: null,
  approval_reason: null,
  rejection_reason: null,
  successor_version_id: null,
  points: [point],
  ...overrides,
});

const template = (versions = [version()]) => ({
  id: 7,
  template_code: 'TPL-MIC-001',
  name: '外徑分厘卡內校',
  equipment_type: '分厘卡',
  description: '0–25 mm',
  status: 'active',
  current_approved_version_id: null,
  current_approved_version: null,
  versions,
});

const renderPage = () => render(
  <MemoryRouter initialEntries={['/calibration/templates/7']}>
    <Routes>
      <Route
        path="/calibration/templates/:templateId"
        element={<CalibrationTemplateEditorPage />}
      />
    </Routes>
  </MemoryRouter>,
);

describe('校正模板受控版本編輯器', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    submitPendingMock.mockReturnValue(false);
    authMock.mockReturnValue({ hasPermission: () => true });
    detailMock.mockReturnValue({
      data: template(),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    updateVersionMock.mockResolvedValue(version({ row_version: 5 }));
    createVersionMock.mockResolvedValue(version({ id: 13, version_no: 4 }));
    submitMock.mockResolvedValue(version({ status: 'submitted' }));
    approveMock.mockResolvedValue(version({ status: 'approved' }));
    rejectMock.mockResolvedValue(version({ status: 'rejected' }));
  });

  it('建立校正點時要求完整允差與重複性規則', async () => {
    const user = userEvent.setup();
    detailMock.mockReturnValue({
      data: template([version({ points: [] })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();

    await user.click(await screen.findByRole('button', { name: '新增校正點' }));
    await user.type(screen.getByLabelText('校正點代碼'), 'P01');
    await user.type(screen.getByLabelText('量測模式'), '外徑');
    await user.type(screen.getByLabelText('單位'), 'mm');
    await user.selectOptions(screen.getByLabelText('重複性規則'), 'range');
    await user.click(screen.getByRole('button', { name: '儲存草稿' }));

    expect(screen.getByRole('alert')).toHaveTextContent('極差上限為必填');
    expect(updateVersionMock).not.toHaveBeenCalled();
  });

  it('沒有版本時可建立第一個受控草稿版本', async () => {
    const user = userEvent.setup();
    detailMock.mockReturnValue({
      data: template([]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();

    await user.type(screen.getByLabelText('程序代碼'), 'WI-CAL-001');
    await user.type(screen.getByLabelText('程序名稱'), '分厘卡內校程序');
    await user.type(screen.getByLabelText('修訂理由'), '初版建立');
    await user.clear(screen.getByLabelText('環境條件 JSON'));
    fireEvent.change(screen.getByLabelText('環境條件 JSON'), {
      target: {
        value: '{"temperature":{"required":true,"minimum":"20","maximum":"26","unit":"°C"}}',
      },
    });
    await user.click(screen.getByRole('button', { name: '新增校正點' }));
    await user.type(screen.getByLabelText('校正點代碼'), 'P01');
    await user.type(screen.getByLabelText('量測模式'), '外徑');
    await user.type(screen.getByLabelText('名目值'), '10');
    await user.type(screen.getByLabelText('單位'), 'mm');
    await user.type(screen.getByLabelText('誤差下限'), '-0.01');
    await user.click(screen.getByRole('button', { name: '建立第一版草稿' }));

    await waitFor(() => expect(createVersionMock).toHaveBeenCalledWith({
      templateId: 7,
      procedure_code: 'WI-CAL-001',
      procedure_name: '分厘卡內校程序',
      procedure_description: null,
      default_repetitions: 3,
      environment_requirements: {
        temperature: {
          required: true,
          minimum: '20',
          maximum: '26',
          unit: '°C',
        },
      },
      allow_limited_use: false,
      revision_reason: '初版建立',
      points: [expect.objectContaining({
        point_code: 'P01',
        nominal_value: '10',
        error_lower_limit: '-0.01',
      })],
    }));
  });

  it('草稿以表格 caption、欄位 label 與鍵盤可到達操作呈現', async () => {
    const user = userEvent.setup();
    renderPage();

    const table = screen.getByRole('table', { name: 'V3 校正點規則' });
    expect(within(table).getByDisplayValue('P01')).toHaveAccessibleName('校正點代碼');

    await user.tab();
    const addButton = screen.getByRole('button', { name: '新增校正點' });
    while (document.activeElement !== addButton) await user.tab();
    expect(addButton).toHaveFocus();
  });

  it('草稿有未儲存變更時阻擋送審舊 server state', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.clear(screen.getByLabelText('程序名稱'));
    await user.type(screen.getByLabelText('程序名稱'), '尚未儲存的新名稱');

    expect(screen.getByRole('button', { name: '送審版本' })).toBeDisabled();
    expect(screen.getByText('有未儲存變更，請先儲存草稿。'))
      .toBeInTheDocument();
  });

  it('送審等待期間凍結編輯，並可檢視完整 server 版本快照', async () => {
    const user = userEvent.setup();
    submitPendingMock.mockReturnValue(true);
    detailMock.mockReturnValue({
      data: template([version({
        environment_requirements: {
          temperature: { minimum: '20', maximum: '26', unit: '°C' },
        },
      })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();

    expect(screen.getByLabelText('程序名稱')).toBeDisabled();
    expect(screen.getByLabelText('校正點代碼')).toBeDisabled();
    expect(screen.getByLabelText('送審理由')).toBeDisabled();
    expect(screen.getByRole('button', { name: '新增校正點' })).toBeDisabled();
    await user.click(screen.getByText('檢視完整已儲存版本'));

    const preview = screen.getByRole('region', { name: '完整已儲存版本' });
    expect(within(preview).getByText('WI-MET-014')).toBeInTheDocument();
    expect(within(preview).getByText('20–26 °C')).toBeInTheDocument();
    expect(within(preview).getByText('新增 25 mm 校正點')).toBeInTheDocument();
    expect(within(preview).getByText('-0.003 ～ 0.003 mm')).toBeInTheDocument();
    expect(within(preview).getByText('極差 ≤ 0.002 mm')).toBeInTheDocument();
    expect(within(preview).getByText('認證值 · 每筆讀值')).toBeInTheDocument();
    expect(within(preview).getByText('必要點 · 需不確定度')).toBeInTheDocument();
  });

  it('V1 的 point 422 會聚焦並標示對應欄位', async () => {
    const user = userEvent.setup();
    detailMock.mockReturnValue({
      data: template([]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    createVersionMock.mockRejectedValue(new ApiError({
      message: '誤差下限格式錯誤',
      status: 422,
      details: { index: 0, field: 'error_lower_limit' },
    }));
    renderPage();

    await user.type(screen.getByLabelText('程序代碼'), 'WI-CAL-001');
    await user.type(screen.getByLabelText('程序名稱'), '分厘卡內校程序');
    await user.type(screen.getByLabelText('修訂理由'), '初版建立');
    await user.click(screen.getByRole('button', { name: '新增校正點' }));
    await user.type(screen.getByLabelText('校正點代碼'), 'P01');
    await user.type(screen.getByLabelText('量測模式'), '外徑');
    await user.type(screen.getByLabelText('名目值'), '10');
    await user.type(screen.getByLabelText('單位'), 'mm');
    await user.type(screen.getByLabelText('誤差下限'), '-0.01');
    await user.click(screen.getByRole('button', { name: '建立第一版草稿' }));

    const lowerLimit = await screen.findByLabelText('誤差下限');
    await waitFor(() => expect(lowerLimit).toHaveFocus());
    expect(lowerLimit).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert'))
      .toHaveTextContent('欄位：points[0].error_lower_limit');
  });

  it('核准版本唯讀且建立新版必須填修訂理由', async () => {
    const user = userEvent.setup();
    detailMock.mockReturnValue({
      data: template([version({
        status: 'approved',
        approved_by: 9,
        approved_at: '2026-07-20T08:00:00+00:00',
      })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();

    expect(screen.queryByRole('button', { name: '儲存草稿' }))
      .not.toBeInTheDocument();
    expect(screen.getByDisplayValue('P01')).toBeDisabled();

    await user.click(screen.getByRole('button', { name: '建立新版' }));
    await user.click(screen.getByRole('button', { name: '建立草稿版本' }));
    expect(screen.getByRole('alert')).toHaveTextContent('修訂理由為必填');
    expect(createVersionMock).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText('新版修訂理由'), '調整允差依據');
    await user.click(screen.getByRole('button', { name: '建立草稿版本' }));
    await waitFor(() => expect(createVersionMock).toHaveBeenCalledWith(
      expect.objectContaining({
        templateId: 7,
        revision_reason: '調整允差依據',
        points: [expect.objectContaining({ point_code: 'P01' })],
      }),
    ));
  });

  it('退回版本可複製為後繼草稿', async () => {
    const user = userEvent.setup();
    detailMock.mockReturnValue({
      data: template([version({
        status: 'rejected',
        rejection_reason: '允差依據不足',
      })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();

    await user.click(screen.getByRole('button', { name: '建立新版' }));
    await user.type(screen.getByLabelText('新版修訂理由'), '補充允差依據');
    await user.click(screen.getByRole('button', { name: '建立草稿版本' }));

    expect(createVersionMock).toHaveBeenCalledWith(expect.objectContaining({
      templateId: 7,
      revision_reason: '補充允差依據',
    }));
  });

  it('沒有 calibration.manage 時隱藏編輯、建立新版與送審', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.view',
    });
    renderPage();

    expect(screen.queryByRole('button', { name: '儲存草稿' }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '送審版本' }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '建立新版' }))
      .not.toBeInTheDocument();
  });

  it('submitted 版本只有 calibration.approve 可核准或退回，且理由必填', async () => {
    const user = userEvent.setup();
    detailMock.mockReturnValue({
      data: template([version({ status: 'submitted', submitted_by: 5 })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    authMock.mockReturnValue({
      hasPermission: (permission: string) => (
        permission === 'calibration.view' || permission === 'calibration.approve'
      ),
    });
    renderPage();

    await user.click(screen.getByRole('button', { name: '核准版本' }));
    expect(screen.getByRole('alert')).toHaveTextContent('決策理由為必填');
    expect(approveMock).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText('核准或退回理由'), '已核對程序與允差');
    await user.click(screen.getByRole('button', { name: '核准版本' }));
    expect(approveMock).toHaveBeenCalledWith({
      templateId: 7,
      versionId: 12,
      expected_version: 4,
      reason: '已核對程序與允差',
    });
  });

  it('沒有 calibration.approve 時不顯示核准與退回', () => {
    detailMock.mockReturnValue({
      data: template([version({ status: 'submitted' })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission !== 'calibration.approve',
    });
    renderPage();

    expect(screen.queryByRole('button', { name: '核准版本' }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '退回版本' }))
      .not.toBeInTheDocument();
  });

  it('保留自我核准後端錯誤訊息與欄位細節', async () => {
    const user = userEvent.setup();
    detailMock.mockReturnValue({
      data: template([version({ status: 'submitted' })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    approveMock.mockRejectedValue(new ApiError({
      message: '建立者或送審者不得核准同一版本',
      status: 403,
      code: 'CALIBRATION_DUTY_SEPARATION_REQUIRED',
      details: { field: 'approved_by' },
    }));
    renderPage();

    await user.type(screen.getByLabelText('核准或退回理由'), '確認核准');
    await user.click(screen.getByRole('button', { name: '核准版本' }));

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('建立者或送審者不得核准同一版本');
    expect(screen.getByRole('alert')).toHaveTextContent('欄位：approved_by');
  });

  it('版本衝突顯示目前與送出 row version 並提供重新載入', async () => {
    const user = userEvent.setup();
    const refetch = vi.fn();
    detailMock.mockReturnValue({
      data: template(),
      isLoading: false,
      isError: false,
      refetch,
    });
    updateVersionMock.mockRejectedValue(new ApiError({
      message: '模板版本已被其他人更新，請重新載入',
      status: 409,
      code: 'CALIBRATION_VERSION_CONFLICT',
      details: { current_version: 6, expected_version: 4 },
    }));
    renderPage();

    await user.clear(screen.getByLabelText('程序名稱'));
    await user.type(screen.getByLabelText('程序名稱'), '新版程序名稱');
    await user.click(screen.getByRole('button', { name: '儲存草稿' }));

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('目前版本 r6；送出版本 r4');
    await user.click(screen.getByRole('button', { name: '重新載入最新版本' }));
    expect(refetch).toHaveBeenCalled();
  });

  it('版本時間軸顯示修訂、送審與核准證據', () => {
    detailMock.mockReturnValue({
      data: template([version({
        status: 'approved',
        submitted_by: 5,
        submitted_at: '2026-07-19T08:00:00+00:00',
        approved_by: 9,
        approved_at: '2026-07-20T08:00:00+00:00',
        approval_reason: '程序與允差已核對',
      })]),
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
    renderPage();

    const timeline = screen.getByRole('navigation', { name: '模板版本時間軸' });
    expect(within(timeline).getByText('新增 25 mm 校正點')).toBeInTheDocument();
    expect(within(timeline).getByText(/送審 #5/)).toBeInTheDocument();
    expect(within(timeline).getByText(/核准 #9/)).toBeInTheDocument();
    expect(within(timeline).getByText('程序與允差已核對')).toBeInTheDocument();
  });
});
