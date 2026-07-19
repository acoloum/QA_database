import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

const authMock = vi.hoisted(() => vi.fn());
vi.mock('../context/useAuth', () => ({ useAuth: () => authMock() }));

import Sidebar from './Sidebar';

describe('Sidebar 的進階 SPC 權限', () => {
  it('沒有 spc.view 時不顯示進階 SPC', () => {
    authMock.mockReturnValue({ user: { role: 'user' }, hasPermission: () => false });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.queryByRole('link', { name: /進階 SPC/ })).not.toBeInTheDocument();
  });

  it('具有 spc.view 時顯示進階 SPC', () => {
    authMock.mockReturnValue({ user: { role: 'user' }, hasPermission: (permission: string) => permission === 'spc.view' });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.getByRole('link', { name: /進階 SPC/ })).toHaveAttribute('href', '/spc/advanced');
  });
});
