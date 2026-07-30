import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
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

describe('Sidebar 的機械性質選單', () => {
  it('位於 /mechanical 時顯示作用中的機械性質選單項目', () => {
    authMock.mockReturnValue({ user: { role: 'user' }, hasPermission: () => false });
    render(<MemoryRouter initialEntries={['/mechanical']}><Sidebar /></MemoryRouter>);

    const mechanicalLink = screen.getByRole('link', { name: /機械性質/ });
    expect(mechanicalLink).toHaveAttribute('href', '/mechanical');
    expect(mechanicalLink).toHaveClass('active');
  });
});

describe('Sidebar 的 MSA 選單', () => {
  it('沒有 msa.view 時不顯示 MSA 工作台', () => {
    authMock.mockReturnValue({ user: { role: 'user' }, hasPermission: () => false });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.queryByRole('link', { name: /MSA 工作台/ })).not.toBeInTheDocument();
  });

  it('具有 msa.view 時顯示 MSA 工作台', () => {
    authMock.mockReturnValue({
      user: { role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
    });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.getByRole('link', { name: /MSA 工作台/ })).toHaveAttribute('href', '/msa');
  });
});

describe('Sidebar 的獨立校正選單', () => {
  it('具有 calibration.view 時顯示量測設備與校正管理', () => {
    authMock.mockReturnValue({
      user: { role: 'user' },
      hasPermission: (permission: string) => (
        permission === 'calibration.view'
      ),
    });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.getByRole('link', { name: /量測設備/ }))
      .toHaveAttribute('href', '/measurement-equipment');
    expect(screen.getByRole('link', { name: /校正管理/ }))
      .toHaveAttribute('href', '/calibrations');
    expect(screen.getByRole('link', { name: /工作佇列/ }))
      .toHaveAttribute('href', '/calibrations');
  });

  it('只有 msa.view 時不顯示量測設備與校正管理', () => {
    authMock.mockReturnValue({
      user: { role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
    });
    render(<MemoryRouter><Sidebar /></MemoryRouter>);

    expect(screen.queryByRole('link', { name: /量測設備/ }))
      .not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /校正管理/ }))
      .not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /MSA 工作台/ }))
      .toBeInTheDocument();
  });
});
