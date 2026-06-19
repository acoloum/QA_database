import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PatrolImportModal from './PatrolImportModal';

const mutateAsync = vi.fn();

vi.mock('../../hooks/usePatrol', () => ({
  useImportPatrol: () => ({
    mutateAsync,
    isPending: false,
    isError: false,
  }),
}));

describe('PatrolImportModal', () => {
  beforeEach(() => {
    mutateAsync.mockReset();
  });

  it('使用巡檢匯入 mutation 上傳檔案', async () => {
    const handleClose = vi.fn();
    const onSuccess = vi.fn();

    mutateAsync.mockResolvedValueOnce({ message: '匯入成功' });

    render(<PatrolImportModal show handleClose={handleClose} onSuccess={onSuccess} />);

    const file = new File(['巡檢資料'], 'patrol.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });

    fireEvent.change(screen.getByLabelText('選擇檔案'), {
      target: { files: [file] },
    });
    fireEvent.click(screen.getByRole('button', { name: '開始匯入' }));

    await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith(file));
    expect(onSuccess).toHaveBeenCalled();
    expect(handleClose).toHaveBeenCalled();
  });
});
