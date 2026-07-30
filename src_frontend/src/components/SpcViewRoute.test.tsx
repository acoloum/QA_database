import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';

const authMock = vi.hoisted(() => vi.fn());
vi.mock('../context/useAuth', () => ({ useAuth: () => authMock() }));

import SpcViewRoute from './SpcViewRoute';

describe('SpcViewRoute', () => {
  it('沒有 spc.view 時導回首頁', () => {
    authMock.mockReturnValue({ isAuthenticated: true, isLoading: false, hasPermission: () => false });
    render(<MemoryRouter initialEntries={['/spc/advanced']}><Routes>
      <Route element={<SpcViewRoute />}><Route path="/spc/advanced" element={<div>進階頁</div>} /></Route>
      <Route path="/" element={<div>首頁</div>} />
    </Routes></MemoryRouter>);

    expect(screen.getByText('首頁')).toBeInTheDocument();
    expect(screen.queryByText('進階頁')).not.toBeInTheDocument();
  });

  it('具有 spc.view 時保留子路由', () => {
    authMock.mockReturnValue({ isAuthenticated: true, isLoading: false, hasPermission: (permission: string) => permission === 'spc.view' });
    render(<MemoryRouter initialEntries={['/spc/advanced']}><Routes>
      <Route element={<SpcViewRoute />}><Route path="/spc/advanced" element={<div>進階頁</div>} /></Route>
      <Route path="/" element={<div>首頁</div>} />
    </Routes></MemoryRouter>);

    expect(screen.getByText('進階頁')).toBeInTheDocument();
  });
});
