import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../context/useAuth', () => ({
  useAuth: () => ({ hasPermission: () => false }),
}));

import AdvancedSpcPage from './AdvancedSpcPage';

describe('AdvancedSpcPage', () => {
  const renderPage = (entry: string) => render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[entry]}><AdvancedSpcPage /></MemoryRouter>
    </QueryClientProvider>,
  );

  it('從 query 載入出貨屬性研究條件', () => {
    renderPage('/spc/advanced?family=attribute&source=shipping&vendor=甲');

    expect(screen.getByRole('heading', { name: '進階 SPC 分析' })).toBeInTheDocument();
    expect(screen.getByLabelText('資料來源')).toHaveValue('shipping');
    expect(screen.getByLabelText('廠商')).toHaveValue('甲');
    expect(screen.getByLabelText('分析族別')).toHaveValue('attribute');
  });

  it('忽略不在白名單或型別不正確的 query 值', () => {
    renderPage('/spc/advanced?family=machine&source=unknown&interval=year&chart_type=xbar_r&vendor=1');

    expect(screen.getByLabelText('資料來源')).toHaveValue('shipping');
    expect(screen.getByLabelText('分析族別')).toHaveValue('attribute');
    expect(screen.getByLabelText('子組區間')).toHaveValue('day');
    expect(screen.getByLabelText('圖表類型')).toHaveValue('p');
  });
});
