import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import WelcomeMessage from './WelcomeMessage';

const authMock = vi.fn();

vi.mock('../../context/useAuth', () => ({ useAuth: () => authMock() }));
vi.mock('../../hooks/useDashboard', () => ({ useDashboardStats: () => ({ stats: null }) }));

describe('WelcomeMessage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('有對應品管人員時以名字（去姓）問候', () => {
    authMock.mockReturnValue({ user: { username: 'A033', display_name: '管隆偉' } });
    render(<WelcomeMessage />);
    expect(screen.getByRole('heading', { level: 2 }).textContent).toMatch(/，隆偉！$/);
  });

  it('兩字姓名直接顯示全名', () => {
    authMock.mockReturnValue({ user: { username: 'A099', display_name: '林木' } });
    render(<WelcomeMessage />);
    expect(screen.getByRole('heading', { level: 2 }).textContent).toMatch(/，林木！$/);
  });

  it('未對應品管人員時退回顯示帳號', () => {
    authMock.mockReturnValue({ user: { username: 'admin', display_name: null } });
    render(<WelcomeMessage />);
    expect(screen.getByRole('heading', { level: 2 }).textContent).toMatch(/，admin！$/);
  });
});
