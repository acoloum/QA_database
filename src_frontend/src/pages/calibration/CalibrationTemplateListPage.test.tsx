import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CalibrationTemplateListPage from './CalibrationTemplateListPage';

const authMock = vi.hoisted(() => vi.fn());
const listMock = vi.hoisted(() => vi.fn());
const createMock = vi.hoisted(() => vi.fn());

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useCalibrationTemplates', () => ({
  useCalibrationTemplates: (params: unknown) => listMock(params),
  useCreateCalibrationTemplate: () => ({
    mutateAsync: createMock,
    isPending: false,
  }),
}));

const template = {
  id: 7,
  template_code: 'TPL-MIC-001',
  name: '外徑分厘卡內校',
  equipment_type: '分厘卡',
  description: '0–25 mm 工作用分厘卡',
  status: 'active',
  current_approved_version_id: 12,
  current_approved_version: {
    id: 12,
    version_no: 3,
    procedure_code: 'WI-MET-014',
    procedure_name: '分厘卡內校程序',
    status: 'approved',
    row_version: 4,
    approved_at: '2026-07-20T08:00:00+00:00',
  },
};

const query = (items = [template]) => ({
  data: { items, page: 1, page_size: 25, total: items.length },
  isLoading: false,
  isError: false,
  refetch: vi.fn(),
});

const renderPage = () => render(
  <MemoryRouter>
    <CalibrationTemplateListPage />
  </MemoryRouter>,
);

describe('校正模板清單', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.mockReturnValue({ hasPermission: () => true });
    listMock.mockReturnValue(query());
    createMock.mockResolvedValue(template);
  });

  it('顯示適用設備、目前核准版本與可讀狀態', () => {
    renderPage();

    expect(screen.getByRole('heading', { name: '校正模板' })).toBeInTheDocument();
    expect(screen.getAllByText('TPL-MIC-001')).toHaveLength(2);
    expect(screen.getByText('分厘卡')).toBeInTheDocument();
    expect(screen.getByText('已核准 · V3')).toBeInTheDocument();
    expect(screen.getByText(/核准時間：2026/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /管理外徑分厘卡內校/ }))
      .toHaveAttribute('href', '/calibration/templates/7');
  });

  it('篩選條件直接交給後端清單查詢', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText('搜尋模板'), '分厘卡');
    await user.selectOptions(screen.getByLabelText('模板狀態'), 'inactive');

    expect(listMock).toHaveBeenLastCalledWith(expect.objectContaining({
      search: '分厘卡',
      status: 'inactive',
      page: 1,
      page_size: 25,
    }));
  });

  it('搜尋只有空白時不送出無效 search 參數', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText('搜尋模板'), '   ');

    expect(listMock).toHaveBeenLastCalledWith(expect.objectContaining({
      search: undefined,
    }));
  });

  it('沒有 calibration.manage 時隱藏建立模板控制', () => {
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'calibration.view',
    });

    renderPage();

    expect(screen.queryByRole('button', { name: '建立模板' }))
      .not.toBeInTheDocument();
  });

  it('建立模板時保留文字欄位並透過資料 hook 送出', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole('button', { name: '建立模板' }));
    const dialog = screen.getByRole('dialog', { name: '新校正模板' });
    await user.type(within(dialog).getByLabelText('模板代碼'), 'TPL-CAL-002');
    await user.type(within(dialog).getByLabelText('模板名稱'), '游標卡尺內校');
    await user.type(within(dialog).getByLabelText('適用設備類型'), '游標卡尺');
    await user.type(within(dialog).getByLabelText('模板說明'), '0–150 mm');
    await user.click(within(dialog).getByRole('button', { name: '確認建立模板' }));

    await waitFor(() => expect(createMock).toHaveBeenCalledWith({
      template_code: 'TPL-CAL-002',
      name: '游標卡尺內校',
      equipment_type: '游標卡尺',
      description: '0–150 mm',
    }));
  });
});
