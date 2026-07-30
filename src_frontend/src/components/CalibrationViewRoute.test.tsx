import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CalibrationViewRoute from './CalibrationViewRoute';

const authMock = vi.hoisted(() => vi.fn());

vi.mock('../context/useAuth', () => ({
  useAuth: () => authMock(),
}));

const renderRoute = () => render(
  <MemoryRouter initialEntries={['/calibrations']}>
    <Routes>
      <Route path="/" element={<h1>首頁</h1>} />
      <Route path="/login" element={<h1>登入</h1>} />
      <Route element={<CalibrationViewRoute />}>
        <Route path="/calibrations" element={<h1>校正工作佇列</h1>} />
      </Route>
    </Routes>
  </MemoryRouter>,
);

describe('校正檢視路由防線', () => {
  beforeEach(() => vi.clearAllMocks());

  it('驗證載入中提供可辨識狀態', () => {
    authMock.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      hasPermission: vi.fn(),
    });
    renderRoute();
    expect(screen.getByRole('status')).toHaveTextContent('載入中');
  });

  it('未登入時導向登入頁', () => {
    authMock.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      hasPermission: vi.fn(),
    });
    renderRoute();
    expect(screen.getByRole('heading', { name: '登入' })).toBeInTheDocument();
  });

  it('沒有 calibration.view 時導向首頁', () => {
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      hasPermission: () => false,
    });
    renderRoute();
    expect(screen.getByRole('heading', { name: '首頁' })).toBeInTheDocument();
  });

  it.each([
    ['一般授權使用者', { role: 'user' }],
    ['由既有 hasPermission 放行的管理員', { role: 'admin' }],
  ])('%s 可以開啟完整校正子路由', (_label, user) => {
    authMock.mockReturnValue({
      user,
      isAuthenticated: true,
      isLoading: false,
      hasPermission: (permission: string) => permission === 'calibration.view',
    });
    renderRoute();
    expect(screen.getByRole('heading', { name: '校正工作佇列' }))
      .toBeInTheDocument();
  });
});
