import { render, screen, waitFor } from '@testing-library/react';
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

vi.mock('./pages/DashboardPage', () => ({
  default: () => <h2>儀表板路由頁面</h2>,
}));

vi.mock('./pages/msa/MsaWorkspacePage', () => ({
  default: () => <h2>MSA 工作台路由頁面</h2>,
}));

vi.mock('./pages/equipment/MeasurementEquipmentPage', () => ({
  default: () => <h2>量測設備路由頁面</h2>,
}));

vi.mock('./pages/calibration/CalibrationTemplateListPage', () => ({
  default: () => <h2>校正模板路由頁面</h2>,
}));

vi.mock('./pages/calibration/CalibrationTemplateEditorPage', () => ({
  default: () => <h2>校正模板版本路由頁面</h2>,
}));

vi.mock('./pages/calibration/CalibrationEntryWizardPage', () => ({
  default: () => <h2>校正詳細數據登錄路由頁面</h2>,
}));

vi.mock('./pages/msa/MsaImportHistoryPage', () => ({
  default: () => <h2>設備匯入路由頁面</h2>,
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

describe('App MSA 路由', () => {
  let originalPathname: string;
  let originalSearch: string;
  let originalHash: string;

  beforeEach(() => {
    originalPathname = window.location.pathname;
    originalSearch = window.location.search;
    originalHash = window.location.hash;
    window.history.replaceState({}, '', '/msa');
  });

  afterEach(() => {
    window.history.replaceState({}, '', `${originalPathname}${originalSearch}${originalHash}`);
  });

  it('已驗證且具有 msa.view 的使用者造訪 /msa 時呈現 MSA 工作台', async () => {
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '測試人員', role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
      logout: vi.fn(),
    });
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'MSA 工作台路由頁面' })).toBeInTheDocument();
  });

  it('已驗證但沒有 msa.view 的使用者造訪 /msa 時不呈現 MSA 工作台', async () => {
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '測試人員', role: 'user' },
      hasPermission: () => false,
      logout: vi.fn(),
    });
    render(<App />);

    expect(await screen.findByRole('heading', { name: '儀表板路由頁面' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'MSA 工作台路由頁面' })).not.toBeInTheDocument();
  });

  it.each([
    ['/msa/imports', '設備匯入路由頁面'],
  ])('具有 msa.view 才能開啟 %s 子路由', async (path, heading) => {
    window.history.replaceState({}, '', path);
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '測試人員', role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
      logout: vi.fn(),
    });

    const { unmount } = render(<App />);
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
    unmount();

    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '測試人員', role: 'user' },
      hasPermission: () => false,
      logout: vi.fn(),
    });
    render(<App />);
    expect(await screen.findByRole('heading', { name: '儀表板路由頁面' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: heading })).not.toBeInTheDocument();
  });
});

describe('App 獨立量測設備路由', () => {
  let originalPathname: string;
  let originalSearch: string;
  let originalHash: string;

  beforeEach(() => {
    originalPathname = window.location.pathname;
    originalSearch = window.location.search;
    originalHash = window.location.hash;
  });

  afterEach(() => {
    window.history.replaceState(
      {},
      '',
      `${originalPathname}${originalSearch}${originalHash}`,
    );
  });

  it('具有 calibration.view 時可開啟獨立設備模組', async () => {
    window.history.replaceState({}, '', '/measurement-equipment');
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '校正人員', role: 'user' },
      hasPermission: (permission: string) => permission === 'calibration.view',
      logout: vi.fn(),
    });

    render(<App />);

    expect(await screen.findByRole(
      'heading',
      { name: '量測設備路由頁面' },
    )).toBeInTheDocument();
  });

  it('舊 MSA 設備入口導向獨立設備模組', async () => {
    window.history.replaceState({}, '', '/msa/equipment');
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '校正人員', role: 'user' },
      hasPermission: (permission: string) => permission === 'calibration.view',
      logout: vi.fn(),
    });

    render(<App />);

    expect(await screen.findByRole(
      'heading',
      { name: '量測設備路由頁面' },
    )).toBeInTheDocument();
    expect(window.location.pathname).toBe('/measurement-equipment');
  });

  it('只有 msa.view 時不可開啟獨立設備模組', async () => {
    window.history.replaceState({}, '', '/measurement-equipment');
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: 'MSA 人員', role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
      logout: vi.fn(),
    });

    render(<App />);

    expect(await screen.findByRole(
      'heading',
      { name: '儀表板路由頁面' },
    )).toBeInTheDocument();
    expect(screen.queryByRole(
      'heading',
      { name: '量測設備路由頁面' },
    )).not.toBeInTheDocument();
  });
});

describe('App 校正模板路由', () => {
  const originalPathname = window.location.pathname;

  afterEach(() => {
    window.history.replaceState({}, '', originalPathname);
  });

  it.each([
    ['/calibration/templates', '校正模板路由頁面'],
    ['/calibration/templates/7', '校正模板版本路由頁面'],
  ])('具有 calibration.view 時可開啟 %s', async (path, heading) => {
    window.history.replaceState({}, '', path);
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '校正人員', role: 'user' },
      hasPermission: (permission: string) => permission === 'calibration.view',
      logout: vi.fn(),
    });

    render(<App />);

    expect(await screen.findByRole('heading', { name: heading }))
      .toBeInTheDocument();
  });

  it.each([
    '/calibration/new',
    '/measurement-equipment/1/calibrations/new',
  ])('具有 calibration.execute 與 manage 時可開啟 %s', async (path) => {
    window.history.replaceState({}, '', path);
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '校正執行者', role: 'user' },
      hasPermission: (permission: string) => (
        permission === 'calibration.view'
        || permission === 'calibration.execute'
        || permission === 'calibration.manage'
      ),
      logout: vi.fn(),
    });

    render(<App />);

    expect(await screen.findByRole(
      'heading',
      { name: '校正詳細數據登錄路由頁面' },
    )).toBeInTheDocument();
  });

  it('只有 calibration.view 與 execute 時不可開啟完整送審精靈', async () => {
    window.history.replaceState({}, '', '/calibration/new');
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: '檢視者', role: 'user' },
      hasPermission: (permission: string) => (
        permission === 'calibration.view'
        || permission === 'calibration.execute'
      ),
      logout: vi.fn(),
    });

    render(<App />);

    await waitFor(() => expect(window.location.pathname)
      .toBe('/measurement-equipment'));
    expect(screen.queryByRole(
      'heading',
      { name: '校正詳細數據登錄路由頁面' },
    )).not.toBeInTheDocument();
  });

  it('沒有 calibration.view 時不可開啟模板頁', async () => {
    window.history.replaceState({}, '', '/calibration/templates');
    authMock.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { username: 'MSA 人員', role: 'user' },
      hasPermission: (permission: string) => permission === 'msa.view',
      logout: vi.fn(),
    });

    render(<App />);

    expect(await screen.findByRole('heading', { name: '儀表板路由頁面' }))
      .toBeInTheDocument();
  });
});
