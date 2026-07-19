import { fireEvent, render, screen } from '@testing-library/react';
import { beforeAll, expect, it, vi } from 'vitest';
import SpcStudyHistoryOffcanvas from './SpcStudyHistoryOffcanvas';

const historyMock = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useSpcStudies', () => ({
  useSpcStudyHistory: (studyId: number | null, page: number) =>
    historyMock(studyId, page),
}));

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

it('研究歷程可切換下一頁並使用後端分頁順序', () => {
  const version = {
    id: 2,
    version_no: 2,
    method_version: '2026.1',
    status: 'active',
    audit_incomplete: false,
    time_model: {},
    created_at: '2026-07-19T00:00:00Z',
  };
  const hybrid = Object.assign([version], {
    items: [version], total: 21, page: 1, per_page: 20, pages: 2,
  });
  historyMock.mockReturnValue({ data: hybrid, isLoading: false });

  const { rerender } = render(
    <SpcStudyHistoryOffcanvas show studyId={9} onHide={vi.fn()} />,
  );

  expect(screen.getByText('v2')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '下一頁' }));
  expect(historyMock).toHaveBeenLastCalledWith(9, 2);

  rerender(<SpcStudyHistoryOffcanvas show studyId={10} onHide={vi.fn()} />);
  expect(historyMock).toHaveBeenLastCalledWith(10, 1);
});
