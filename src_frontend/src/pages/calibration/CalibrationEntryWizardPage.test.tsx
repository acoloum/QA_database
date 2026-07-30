import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CalibrationEntryWizardPage from './CalibrationEntryWizardPage';

const createMock = vi.hoisted(() => vi.fn());
const updateMock = vi.hoisted(() => vi.fn());
const readingsMock = vi.hoisted(() => vi.fn());
const validateMock = vi.hoisted(() => vi.fn());
const submitMock = vi.hoisted(() => vi.fn());
const uploadMock = vi.hoisted(() => vi.fn());
const pendingState = vi.hoisted(() => ({ create: false }));

const equipmentItems = [
  {
    id: 1, equipment_no: 'MIC-001', name: '外徑分厘卡',
    equipment_type: '分厘卡', status: 'active',
    calibration_status: 'valid', is_reference_standard: false,
  },
  {
    id: 9, equipment_no: 'BLOCK-001', name: '一級量塊',
    equipment_type: '量塊', status: 'active',
    calibration_status: 'valid', is_reference_standard: true,
  },
];

const templateVersion = {
  id: 12,
  version_no: 3,
  status: 'approved',
  environment_requirements: {
    temperature: {
      label: '溫度',
      required: true,
      minimum: '20',
      maximum: '26',
      unit: '°C',
      instruction: '穩定 30 分鐘後記錄',
    },
  },
  points: [{
    id: 91,
    point_code: 'P01',
    measurement_mode: '外徑',
    unit: 'mm',
    reference_input_mode: 'certified_value',
    required_repetitions: 2,
    uncertainty_required: true,
  }],
};

const templateDetail = {
  id: 7,
  template_code: 'TPL-MIC-001',
  name: '外徑分厘卡內校',
  equipment_type: '分厘卡',
  versions: [templateVersion],
};

const record = {
  id: 41,
  equipment_id: 1,
  equipment_no: 'MIC-001',
  equipment_name: '外徑分厘卡',
  calibration_type: 'internal',
  calibration_date: '2026-07-29',
  template_version_id: 12,
  row_version: 1,
  result: 'pending',
  status: 'draft',
  environment_conditions: {},
  calculation_summary: {},
  certificate_attachment_id: null,
  points: [{
    id: 31,
    point_code: 'P01',
    measurement_mode: '外徑',
    unit: 'mm',
    reference_value: '10.000',
    required_repetitions: 2,
    readings: [],
  }],
};

vi.mock('../../hooks/useMsaEquipment', () => ({
  useMsaEquipment: () => ({
    data: { items: equipmentItems, total: equipmentItems.length },
    isLoading: false,
  }),
  useMsaEquipmentDetail: (id: number | null) => ({
    data: equipmentItems.find((item) => item.id === id),
    isLoading: false,
  }),
}));
vi.mock('../../hooks/useCalibrationTemplates', () => ({
  useCalibrationTemplates: () => ({
    data: {
      items: [{
        ...templateDetail,
        current_approved_version_id: 12,
        current_approved_version: {
          id: 12, version_no: 3, status: 'approved',
        },
      }],
      total: 1,
    },
    isLoading: false,
  }),
  useCalibrationTemplate: (id: number | null) => ({
    data: id ? templateDetail : undefined,
    isLoading: false,
  }),
}));
vi.mock('../../hooks/useCalibrations', () => ({
  useCalibration: () => ({
    data: record,
    refetch: vi.fn().mockResolvedValue({ data: record }),
  }),
  useCreateCalibration: () => ({
    mutateAsync: createMock,
    isPending: pendingState.create,
  }),
  useUpdateCalibration: () => ({ mutateAsync: updateMock, isPending: false }),
  useSaveCalibrationReadings: () => ({
    mutateAsync: readingsMock, isPending: false,
  }),
  useValidateCalibration: () => ({
    mutateAsync: validateMock, isPending: false,
  }),
  useSubmitCalibration: () => ({ mutateAsync: submitMock, isPending: false }),
}));
vi.mock('../../hooks/useAttachment', () => ({
  useUploadAttachment: () => ({ mutateAsync: uploadMock, isPending: false }),
}));

const renderPage = () => render(
  <MemoryRouter><CalibrationEntryWizardPage /></MemoryRouter>,
);

const chooseBase = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.selectOptions(screen.getByLabelText('受校設備'), '1');
  await user.selectOptions(screen.getByLabelText('校正模板'), '7');
  fireEvent.change(screen.getByLabelText('校正日期'), {
    target: { value: '2026-07-29' },
  });
};

describe('四步校正詳細數據登錄精靈', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pendingState.create = false;
    createMock.mockResolvedValue(record);
    updateMock.mockImplementation(async (payload) => ({
      ...record,
      ...payload,
      row_version: record.row_version + 1,
    }));
    readingsMock.mockResolvedValue({
      ...record,
      row_version: 3,
      status: 'in_progress',
      result: 'pass',
      calculation_summary: { result: 'pass', completed_points: 1 },
    });
    validateMock.mockResolvedValue({
      result: 'pass',
      blockers: [],
      passed_scope_codes: ['OD-0-25'],
      failed_scope_codes: [],
      row_version: 4,
    });
    submitMock.mockResolvedValue({ ...record, status: 'submitted' });
    uploadMock.mockResolvedValue({ id: 88, file_name: 'certificate.pdf' });
  });

  it('內校必須選擇參考標準器', async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseBase(user);
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));

    expect(screen.getByRole('alert')).toHaveTextContent('內校必須選擇參考標準器');
    expect(createMock).not.toHaveBeenCalled();
  });

  it('建立草稿請求進行中會凍結第一步欄位', () => {
    pendingState.create = true;
    renderPage();

    expect(screen.getByLabelText('搜尋受校設備')).toBeDisabled();
    expect(screen.getByLabelText('受校設備')).toBeDisabled();
    expect(screen.getByLabelText('校正類型')).toBeDisabled();
    expect(screen.getByLabelText('校正日期')).toBeDisabled();
  });

  it('外校必須填機構及證書資訊', async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('校正類型'), 'external');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));

    expect(screen.getByRole('alert')).toHaveTextContent('外校機構與證書編號為必填');
  });

  it('依模板建立環境欄位並以 server 回傳計算進入檢閱', async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('參考標準器'), '9');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));
    expect(createMock).toHaveBeenCalledWith(expect.objectContaining({
      equipment_id: 1,
      template_version_id: 12,
      calibration_type: 'internal',
      reference_standard_equipment_id: 9,
    }));
    expect(screen.getByRole('button', { name: /設備與程序/ })).toBeDisabled();

    await user.type(screen.getByLabelText('溫度 (°C)'), '23.5');
    await user.click(screen.getByRole('button', { name: '儲存條件並繼續' }));
    expect(updateMock).toHaveBeenCalledWith(expect.objectContaining({
      calibrationId: 41,
      expected_version: 1,
      environment_conditions: {
        temperature: {
          value: '23.5',
          unit: '°C',
          instruction: '穩定 30 分鐘後記錄',
        },
      },
    }));

    await user.type(
      screen.getByLabelText('P01 試驗 1 受校件器示值'),
      '10.0010',
    );
    await user.type(
      screen.getByLabelText('P01 試驗 2 受校件器示值'),
      '10.0020',
    );
    await user.clear(screen.getByLabelText('P01 認證參考值'));
    await user.type(screen.getByLabelText('P01 認證參考值'), '10.0001');
    await user.click(screen.getByLabelText('P01 已確認認證參考值'));
    await user.type(screen.getByLabelText('P01 擴充不確定度'), '0.00050');
    await user.type(screen.getByLabelText('P01 涵蓋因子'), '2.000');
    await user.click(screen.getByRole('button', { name: '儲存原始讀值' }));
    await waitFor(() => expect(readingsMock).toHaveBeenCalled());
    expect(readingsMock.mock.calls[0][0].points[0].readings[0])
      .toEqual({ trial_no: 1, indicated_value: '10.0010' });
    expect(readingsMock.mock.calls[0][0].points[0]).toEqual(
      expect.objectContaining({
        reference_value: '10.0001',
        expanded_uncertainty: '0.00050',
        coverage_factor: '2.000',
      }),
    );

    expect(await screen.findByText('後端判定：合格')).toBeInTheDocument();
  }, 10_000);

  it('認證參考值經明確確認後清空時送出 null，不回填舊值', async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('參考標準器'), '9');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));
    await user.type(screen.getByLabelText('溫度 (°C)'), '23');
    await user.click(screen.getByRole('button', { name: '儲存條件並繼續' }));

    await user.click(screen.getByLabelText('P01 已確認認證參考值'));
    await user.clear(screen.getByLabelText('P01 認證參考值'));
    await user.click(screen.getByRole('button', { name: '儲存原始讀值' }));

    await waitFor(() => expect(readingsMock).toHaveBeenCalled());
    expect(readingsMock.mock.calls[0][0].points[0].reference_value).toBeNull();
  });

  it('外校證書以 purpose cert 上傳並綁定草稿', async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('校正類型'), 'external');
    await user.type(screen.getByLabelText('外校機構'), 'TAF 實驗室');
    await user.type(screen.getByLabelText('證書編號'), 'CERT-2026-01');
    createMock.mockResolvedValue({ ...record, calibration_type: 'external' });
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));

    const file = new File(['pdf'], 'certificate.pdf', {
      type: 'application/pdf',
    });
    await user.upload(screen.getByLabelText('證書附件'), file);
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith({
      file,
      entity_type: 'equipment_calibration',
      entity_id: 41,
      purpose: 'cert',
    }));
    expect(updateMock).toHaveBeenCalledWith(expect.objectContaining({
      calibrationId: 41,
      certificate_attachment_id: 88,
    }));
  });

  it('證書已上傳但綁定失敗時保留重試入口並阻擋無提示離頁', async () => {
    const user = userEvent.setup();
    createMock.mockResolvedValue({ ...record, calibration_type: 'external' });
    updateMock.mockRejectedValueOnce(new Error('row version conflict'));
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('校正類型'), 'external');
    await user.type(screen.getByLabelText('外校機構'), 'TAF 實驗室');
    await user.type(screen.getByLabelText('證書編號'), 'CERT-2026-RETRY');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));

    const file = new File(['pdf'], 'certificate.pdf', {
      type: 'application/pdf',
    });
    await user.upload(screen.getByLabelText('證書附件'), file);

    expect(await screen.findByRole('button', {
      name: '重新綁定已上傳附件 #88',
    })).toBeInTheDocument();
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it('外校缺少證書附件時不得宣稱驗證通過或送審', async () => {
    const user = userEvent.setup();
    createMock.mockResolvedValue({ ...record, calibration_type: 'external' });
    updateMock.mockImplementation(async (payload) => ({
      ...record,
      ...payload,
      calibration_type: 'external',
      row_version: record.row_version + 1,
    }));
    readingsMock.mockResolvedValue({
      ...record,
      calibration_type: 'external',
      row_version: 3,
      status: 'in_progress',
      result: 'pass',
      calculation_summary: { result: 'pass', completed_points: 1 },
    });
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('校正類型'), 'external');
    await user.type(screen.getByLabelText('外校機構'), 'TAF 實驗室');
    await user.type(screen.getByLabelText('證書編號'), 'CERT-2026-02');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));
    await user.type(screen.getByLabelText('溫度 (°C)'), '23');
    await user.click(screen.getByRole('button', { name: '儲存條件並繼續' }));
    await user.click(screen.getByRole('button', { name: '儲存原始讀值' }));
    await user.click(await screen.findByRole('button', { name: '執行送審前驗證' }));

    expect(await screen.findByText(
      'CALIBRATION_CERTIFICATE_REQUIRED',
    )).toBeInTheDocument();
    expect(screen.queryByText('送審前驗證通過。')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '送審校正紀錄' }))
      .toBeDisabled();
    expect(validateMock).not.toHaveBeenCalled();
  });

  it('更換外校證書會立即失效舊驗證並要求重新驗證', async () => {
    const user = userEvent.setup();
    const externalRecord = {
      ...record,
      calibration_type: 'external',
      certificate_attachment_id: null,
    };
    createMock.mockResolvedValue(externalRecord);
    updateMock.mockImplementation(async (payload) => {
      return {
        ...externalRecord,
        ...payload,
        calibration_type: 'external',
        certificate_attachment_id: payload.certificate_attachment_id ?? 88,
        row_version: payload.expected_version + 1,
      };
    });
    readingsMock.mockResolvedValue({
      ...externalRecord,
      calibration_type: 'external',
      certificate_attachment_id: 88,
      row_version: 4,
      status: 'in_progress',
      result: 'pass',
      calculation_summary: { result: 'pass', completed_points: 1 },
    });
    validateMock.mockResolvedValue({
      result: 'pass',
      blockers: [],
      passed_scope_codes: ['OD-0-25'],
      failed_scope_codes: [],
      row_version: 5,
    });
    uploadMock
      .mockResolvedValueOnce({ id: 88, file_name: 'old-certificate.pdf' })
      .mockResolvedValueOnce({ id: 89, file_name: 'new-certificate.pdf' });

    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('校正類型'), 'external');
    await user.type(screen.getByLabelText('外校機構'), 'TAF 實驗室');
    await user.type(screen.getByLabelText('證書編號'), 'CERT-OLD');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));
    await user.upload(
      screen.getByLabelText('證書附件'),
      new File(['old'], 'old.pdf', { type: 'application/pdf' }),
    );
    await user.type(screen.getByLabelText('溫度 (°C)'), '23');
    await user.click(screen.getByRole('button', { name: '儲存條件並繼續' }));
    await user.click(screen.getByRole('button', { name: '儲存原始讀值' }));
    await user.click(await screen.findByRole('button', { name: '執行送審前驗證' }));
    expect(await screen.findByText('送審前驗證通過。')).toBeInTheDocument();
    await user.type(screen.getByLabelText('送審理由'), '舊證書已驗證');

    const stepper = screen.getByRole('navigation', { name: '校正登錄步驟' });
    await user.click(within(stepper).getByRole('button', { name: /條件與證書/ }));
    await user.upload(
      screen.getByLabelText('證書附件'),
      new File(['new'], 'new.pdf', { type: 'application/pdf' }),
    );
    await user.click(within(stepper).getByRole('button', { name: /證據檢閱/ }));

    expect(screen.queryByText('送審前驗證通過。')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '送審校正紀錄' }))
      .toBeDisabled();
    expect(submitMock).not.toHaveBeenCalled();
  });

  it('驗證 blockers 可返回讀值步驟', async () => {
    const user = userEvent.setup();
    readingsMock.mockResolvedValue({
      ...record,
      row_version: 3,
      status: 'in_progress',
      result: 'pending',
      calculation_summary: {
        result: 'pending',
        blockers: ['CALIBRATION_READING_MISSING'],
        points: [{
          point_code: 'P01',
          blockers: ['CALIBRATION_READING_MISSING'],
        }],
      },
    });
    validateMock.mockResolvedValue({
      result: 'pending',
      blockers: ['CALIBRATION_READING_MISSING'],
      passed_scope_codes: [],
      failed_scope_codes: [],
      row_version: 4,
    });
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('參考標準器'), '9');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));
    await user.type(screen.getByLabelText('溫度 (°C)'), '23');
    await user.click(screen.getByRole('button', { name: '儲存條件並繼續' }));
    await user.click(screen.getByRole('button', { name: '儲存原始讀值' }));
    await user.click(await screen.findByRole('button', { name: '執行送審前驗證' }));

    expect(validateMock).toHaveBeenCalledWith({
      calibrationId: 41,
      expected_version: 3,
    });
    expect(await screen.findByText(/CALIBRATION_READING_MISSING/))
      .toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '返回 P01 讀值' }));
    expect(screen.getByRole('heading', { name: '原始讀值' })).toBeInTheDocument();
  });

  it('送審理由不視為未保存 server 內容並以最新 row version 送審', async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('參考標準器'), '9');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));
    await user.type(screen.getByLabelText('溫度 (°C)'), '23');
    await user.click(screen.getByRole('button', { name: '儲存條件並繼續' }));
    await user.click(screen.getByRole('button', { name: '儲存原始讀值' }));
    await user.click(await screen.findByRole('button', { name: '執行送審前驗證' }));
    expect(await screen.findByText('送審前驗證通過。')).toBeInTheDocument();

    await user.type(screen.getByLabelText('送審理由'), '原始讀值已完成');
    const submitButton = screen.getByRole('button', { name: '送審校正紀錄' });
    expect(submitButton).toBeEnabled();
    await user.click(submitButton);

    expect(submitMock).toHaveBeenCalledWith({
      calibrationId: 41,
      expected_version: 4,
      reason: '原始讀值已完成',
    });
    await waitFor(() => expect(screen.getByLabelText('送審理由')).toBeDisabled());
    expect(screen.getByRole('button', { name: /設備與程序/ })).toBeDisabled();
  });

  it('通過驗證後修改本地讀值會清除驗證並阻擋送審舊證據', async () => {
    const user = userEvent.setup();
    renderPage();
    await chooseBase(user);
    await user.selectOptions(screen.getByLabelText('參考標準器'), '9');
    await user.click(screen.getByRole('button', { name: '建立草稿並繼續' }));
    await user.type(screen.getByLabelText('溫度 (°C)'), '23');
    await user.click(screen.getByRole('button', { name: '儲存條件並繼續' }));
    await user.click(screen.getByRole('button', { name: '儲存原始讀值' }));
    await user.click(await screen.findByRole('button', { name: '執行送審前驗證' }));
    expect(await screen.findByText('送審前驗證通過。')).toBeInTheDocument();

    const stepper = screen.getByRole('navigation', { name: '校正登錄步驟' });
    await user.click(within(stepper).getByRole('button', { name: /原始讀值/ }));
    await user.type(
      screen.getByLabelText('P01 試驗 1 受校件器示值'),
      '10.1',
    );
    await user.click(within(stepper).getByRole('button', { name: /證據檢閱/ }));
    await user.type(screen.getByLabelText('送審理由'), '嘗試送出舊證據');

    expect(screen.queryByText('送審前驗證通過。')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '送審校正紀錄' }))
      .toBeDisabled();
    expect(submitMock).not.toHaveBeenCalled();
  });

  it('有未保存變更時註冊離開頁面提示', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.selectOptions(screen.getByLabelText('受校設備'), '1');
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });

  it('有未保存變更時攔截 Router push 型內部連結', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderPage();
    await user.selectOptions(screen.getByLabelText('受校設備'), '1');
    const link = document.createElement('a');
    link.href = '/another-module';
    link.textContent = '前往其他模組';
    document.body.appendChild(link);
    const event = new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      button: 0,
    });

    expect(link.dispatchEvent(event)).toBe(false);
    expect(event.defaultPrevented).toBe(true);
    expect(confirm).toHaveBeenCalledWith('尚有未保存變更，確定要離開嗎？');
    link.remove();
    confirm.mockRestore();
  });

  it('有未保存變更時攔截標記為登出的按鈕操作', async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const logout = vi.fn();
    renderPage();
    await user.selectOptions(screen.getByLabelText('受校設備'), '1');
    const button = document.createElement('button');
    button.dataset.navigationAction = 'logout';
    button.textContent = '登出';
    button.addEventListener('click', logout);
    document.body.appendChild(button);

    await user.click(button);

    expect(confirm).toHaveBeenCalledWith('尚有未保存變更，確定要離開嗎？');
    expect(logout).not.toHaveBeenCalled();
    button.remove();
    confirm.mockRestore();
  });
});
