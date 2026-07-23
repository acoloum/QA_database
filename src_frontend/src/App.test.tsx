import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const authMock = vi.hoisted(() => vi.fn());

vi.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('./context/useAuth', () => ({
  useAuth: () => authMock(),
}));

vi.mock('./pages/mechanical/MechanicalTestListPage', () => ({
  default: () => <h2>機械性質路由頁面</h2>,
}));

import App from './App';

describe('App 機械性質路由', () => {
  let originalPathname: string;
  let originalSearch: string;
  let originalHash: string;

  beforeEach(() => {
    originalPathname = window.location.pathname;
    originalSearch = window.location.search;
    originalHash = window.location.hash;
    window.history.replaceState({}, '', '/mechanical');
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '測試人員', role: 'admin' },
      hasPermission: () => true,
      logout: vi.fn(),
    });
  });

  afterEach(() => {
    window.history.replaceState({}, '', `${originalPathname}${originalSearch}${originalHash}`);
  });

  it('已驗證使用者造訪 /mechanical 時呈現機械性質頁面', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: '機械性質路由頁面' })).toBeInTheDocument();
    expect(screen.getByRole('complementary')).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('未登入使用者造訪 /mechanical 時導向登入頁', async () => {
    authMock.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      hasPermission: () => false,
      login: vi.fn(),
      logout: vi.fn(),
    });
    render(<App />);

    expect(await screen.findByRole('heading', { name: '品保管理系統' })).toBeInTheDocument();
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
  });
});
