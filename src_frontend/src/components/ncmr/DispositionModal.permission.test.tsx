import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DispositionModal from './DispositionModal';

const authMock = vi.fn();
const mutations = vi.hoisted(() => ({
  create: vi.fn(),
  remove: vi.fn(),
  update: vi.fn(),
  createCapa: vi.fn(),
}));

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useNCMR', () => ({
  useDispositions: () => ({ data: [{ 識別碼: 8, 處置類型: '報廢', 處置數量: 1 }] }),
  useNcmrReworks: () => ({ data: [] }),
  useCreateDisposition: () => ({ mutateAsync: mutations.create, isPending: false }),
  useDeleteDisposition: () => ({ mutateAsync: mutations.remove }),
  useUpdateNCMR: () => ({ mutateAsync: mutations.update, isPending: false }),
  useCreateCAPA: () => ({ mutateAsync: mutations.createCapa, isPending: false }),
}));

describe('DispositionModal 唯讀權限', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMock.mockReturnValue({
      hasPermission: (permission: string) => permission === 'ncmr.view',
    });
  });

  it('view-only 可閱讀明細，但新增與刪除維持停用且不呼叫 mutation', () => {
    render(
      <MemoryRouter>
        <DispositionModal
          show
          handleClose={vi.fn()}
          onSuccess={vi.fn()}
          item={{ id: 5, no: 'NCMR-5', defect_qty: 2 } as never}
        />
      </MemoryRouter>,
    );

    expect(screen.getAllByText('報廢').length).toBeGreaterThanOrEqual(1);
    const remove = screen.getByRole('button', { name: '刪除' });
    expect(remove).toBeDisabled();

    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '1' } });
    const create = screen.getByRole('button', { name: '新增此處置' });
    expect(create).toBeDisabled();
    expect(screen.getAllByText('需要 ncmr.disposition 權限')).toHaveLength(2);

    fireEvent.click(remove);
    fireEvent.click(create);
    expect(mutations.remove).not.toHaveBeenCalled();
    expect(mutations.create).not.toHaveBeenCalled();
    expect(screen.queryByText('確定刪除此處置？')).not.toBeInTheDocument();
  });
});
