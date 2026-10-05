import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ComplaintCapaModal from './ComplaintCapaModal';
import type { CustomerComplaint } from '../../types';

const authMock = vi.fn();
const capaListMock = vi.fn();

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useCapa', () => ({ useCapaList: (params: unknown) => capaListMock(params) }));

const complaint = { id: 7, complaint_no: 'CC-007' } as CustomerComplaint;

describe('ComplaintCapaModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.mockReturnValue({ hasPermission: () => true });
    capaListMock.mockReturnValue({
      data: { data: [{ id: 3, no: 'CAPA-003', vendor: '甲客戶', ncmr_description: '表面刮傷' }] },
      isLoading: false,
    });
  });

  it('預設開立新 CAPA', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    const onHide = vi.fn();
    render(<ComplaintCapaModal complaint={complaint} onHide={onHide} onCreate={onCreate} onLink={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: '開立' }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(7));
    expect(onHide).toHaveBeenCalled();
  });

  it('選擇關聯既有 CAPA 時只列出進行中的 CAPA 並送出所選 CAPA', async () => {
    const onLink = vi.fn().mockResolvedValue(undefined);
    render(<ComplaintCapaModal complaint={complaint} onHide={vi.fn()} onCreate={vi.fn()} onLink={onLink} />);

    fireEvent.click(screen.getByLabelText('關聯既有 CAPA（共用同一份 8D）'));
    const confirm = screen.getByRole('button', { name: '關聯' });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '3' } });
    fireEvent.click(confirm);

    expect(capaListMock).toHaveBeenCalledWith({ status: '進行中', per_page: 100 });
    await waitFor(() => expect(onLink).toHaveBeenCalledWith(7, 3));
  });

  it('缺少 capa.edit 權限時不可選擇關聯既有 CAPA', () => {
    authMock.mockReturnValue({ hasPermission: (perm: string) => perm !== 'capa.edit' });
    render(<ComplaintCapaModal complaint={complaint} onHide={vi.fn()} onCreate={vi.fn()} onLink={vi.fn()} />);

    expect(screen.getByLabelText('關聯既有 CAPA（共用同一份 8D）')).toBeDisabled();
  });
});
