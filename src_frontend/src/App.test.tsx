import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('./context/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    user: { username: '測試人員', role: 'admin' },
    hasPermission: () => true,
    logout: vi.fn(),
  }),
}));

vi.mock('./pages/mechanical/MechanicalTestListPage', () => ({
  default: () => <h2>機械性質路由頁面</h2>,
}));

import App from './App';

describe('App 機械性質路由', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/mechanical');
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('已驗證使用者造訪 /mechanical 時呈現機械性質頁面', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: '機械性質路由頁面' })).toBeInTheDocument();
  });
});
