import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PermissionRoute from './PermissionRoute';

const authMock = vi.fn();

vi.mock('../context/useAuth', () => ({ useAuth: () => authMock() }));

const renderRoute = () => render(
  <MemoryRouter initialEntries={['/受控頁面']}>
    <Routes>
      <Route path="/login" element={<h1>登入頁</h1>} />
      <Route path="/" element={<h1>儀表板</h1>} />
      <Route
        path="/受控頁面"
        element={(
          <PermissionRoute permission="ncmr.view">
            <h1>受控內容</h1>
          </PermissionRoute>
        )}
      />
    </Routes>
  </MemoryRouter>,
);

describe('PermissionRoute', () => {
  beforeEach(() => vi.clearAllMocks());

  it('驗證狀態載入中時只顯示可辨識的載入狀態', () => {
    authMock.mockReturnValue({ isLoading: true, isAuthenticated: false, hasPermission: vi.fn() });
    renderRoute();
    expect(screen.getByRole('status')).toHaveTextContent('載入中');
    expect(screen.queryByText('受控內容')).not.toBeInTheDocument();
  });

  it('未登入時導向登入頁', async () => {
    authMock.mockReturnValue({ isLoading: false, isAuthenticated: false, hasPermission: vi.fn() });
    renderRoute();
    expect(await screen.findByRole('heading', { name: '登入頁' })).toBeInTheDocument();
  });

  it('缺少權限時導回儀表板且不呈現受控內容', async () => {
    authMock.mockReturnValue({ isLoading: false, isAuthenticated: true, hasPermission: () => false });
    renderRoute();
    expect(await screen.findByRole('heading', { name: '儀表板' })).toBeInTheDocument();
    expect(screen.queryByText('受控內容')).not.toBeInTheDocument();
  });

  it('具有權限時呈現受控內容', () => {
    authMock.mockReturnValue({ isLoading: false, isAuthenticated: true, hasPermission: (permission: string) => permission === 'ncmr.view' });
    renderRoute();
    expect(screen.getByRole('heading', { name: '受控內容' })).toBeInTheDocument();
  });
});
