import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import CAPAPage from './CAPAPage';

vi.mock('../../hooks/useCapa', () => ({
  CAPA_SEVERITY_VARIANT: {},
  CAPA_STATUS_VARIANT: {},
  useCapaList: () => ({ data: { data: [], total: 0 }, isLoading: false }),
  useDeleteCapa: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock('../../components/capa/CAPAModal', () => ({
  default: ({ show, capaId }: { show: boolean; capaId: number | null }) =>
    show ? <div data-testid="capa-modal">CAPA {capaId}</div> : null,
}));

const renderPage = (initialEntry: string) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/capa" element={<CAPAPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe('CAPAPage', () => {
  it('opens CAPA modal from editId query param and clears the URL', async () => {
    renderPage('/capa?editId=42');

    expect(screen.getByTestId('capa-modal')).toHaveTextContent('CAPA 42');
    await waitFor(() => expect(window.location.search).toBe(''));
  });

  it('does not open modal for invalid query params', () => {
    renderPage('/capa?editId=abc');

    expect(screen.queryByTestId('capa-modal')).not.toBeInTheDocument();
  });
});
