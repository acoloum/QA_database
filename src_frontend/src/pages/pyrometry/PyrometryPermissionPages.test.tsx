import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import FurnaceMasterPage from './FurnaceMasterPage';
import RecorderCalibrationPage from './RecorderCalibrationPage';
import ThermocoupleCalibrationPage from './ThermocoupleCalibrationPage';

const authMock = vi.fn();
const hooks = vi.hoisted(() => ({
  saveFurnace: vi.fn(),
  deleteFurnace: vi.fn(),
  recorderDetail: vi.fn(),
  saveRecorder: vi.fn(),
  deleteRecorder: vi.fn(),
  thermocoupleDetail: vi.fn(),
  saveThermocouple: vi.fn(),
  deleteThermocouple: vi.fn(),
}));

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/usePyrometry', () => ({
  useFurnaces: () => ({ data: [{
    識別碼: 1, 爐號: 'F-1', 名稱: '一號爐', 製程類型: 'T6時效',
    TUS點數: 12, SAT點數: 2, TUS允許公差: 5, SAT允許誤差: 2,
    啟用狀態: true,
  }], isLoading: false }),
  useFurnaceTusTrend: () => ({ data: [] }),
  useSaveFurnace: () => ({ mutate: hooks.saveFurnace, isPending: false }),
  useDeleteFurnace: () => ({ mutateAsync: hooks.deleteFurnace }),
  useRecorders: () => ({ data: [{
    識別碼: 2, 編號: 'R-1', 校正日期: '2026-01-01', 到期日: '2027-01-01',
    啟用狀態: true,
  }], isLoading: false }),
  useRecorderDetail: () => ({ mutateAsync: hooks.recorderDetail }),
  useSaveRecorder: () => ({ mutate: hooks.saveRecorder, isPending: false }),
  useDeleteRecorder: () => ({ mutateAsync: hooks.deleteRecorder }),
  useThermocouples: () => ({ data: [{
    識別碼: 3, 編號: 'TC-1', 型式: 'TYPE K', 校正日期: '2026-01-01',
    到期日: '2027-01-01', 啟用狀態: true, 校正點: [],
  }], isLoading: false }),
  useThermocoupleDetail: () => ({ mutateAsync: hooks.thermocoupleDetail }),
  useSaveThermocouple: () => ({ mutate: hooks.saveThermocouple, isPending: false }),
  useDeleteThermocouple: () => ({ mutateAsync: hooks.deleteThermocouple }),
}));

type PageCase = {
  name: string;
  Page: () => React.JSX.Element;
  detailHandler: ReturnType<typeof vi.fn> | null;
};

const pages: PageCase[] = [
  { name: '爐子設備', Page: FurnaceMasterPage, detailHandler: null },
  { name: '記錄器', Page: RecorderCalibrationPage, detailHandler: hooks.recorderDetail },
  { name: '熱電偶', Page: ThermocoupleCalibrationPage, detailHandler: hooks.thermocoupleDetail },
];

describe('爐溫主檔操作權限', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    hooks.recorderDetail.mockResolvedValue({
      編號: 'R-1', 校正日期: '', 到期日: '', 啟用狀態: true, 備註: '', 校正點: [],
    });
    hooks.thermocoupleDetail.mockResolvedValue({
      編號: 'TC-1', 型式: 'TYPE K', 校正日期: '', 到期日: '',
      啟用狀態: true, 備註: '', 校正點: [],
    });
  });

  it.each(pages)('$name 缺權限時新增、編輯、刪除皆停用且不執行 handler', ({ Page, detailHandler }) => {
    authMock.mockReturnValue({ hasPermission: () => false });
    render(<Page />);

    const create = screen.getByRole('button', { name: /新增$/ });
    const edit = screen.getByRole('button', { name: '編輯' });
    const remove = screen.getByRole('button', { name: '刪除' });
    expect(create).toBeDisabled();
    expect(edit).toBeDisabled();
    expect(remove).toBeDisabled();
    expect(screen.getAllByText('需要 pyrometry.edit 權限').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('需要 pyrometry.delete 權限')).toBeInTheDocument();

    fireEvent.click(create);
    fireEvent.click(edit);
    fireEvent.click(remove);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    if (detailHandler) expect(detailHandler).not.toHaveBeenCalled();
  });

  it.each(pages)('$name 權限撤銷後既有 modal 的儲存入口停用且不送出', ({ Page }) => {
    authMock.mockReturnValue({ hasPermission: () => true });
    const { rerender } = render(<Page />);
    const create = screen.getByRole('button', { name: /新增$/ });
    expect(create).toBeEnabled();
    expect(screen.getByRole('button', { name: '編輯' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '刪除' })).toBeEnabled();
    fireEvent.click(create);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    authMock.mockReturnValue({ hasPermission: () => false });
    rerender(<Page />);
    const save = screen.getByRole('button', { name: '儲存' });
    expect(save).toBeDisabled();
    fireEvent.click(save);
    expect(hooks.saveFurnace).not.toHaveBeenCalled();
    expect(hooks.saveRecorder).not.toHaveBeenCalled();
    expect(hooks.saveThermocouple).not.toHaveBeenCalled();
  });
});
