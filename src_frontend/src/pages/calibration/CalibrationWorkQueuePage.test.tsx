import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CalibrationWorkQueuePage from './CalibrationWorkQueuePage';

const listMock = vi.hoisted(() => vi.fn());

vi.mock('../../hooks/useCalibrations', () => ({
  useCalibrations: (params: unknown) => listMock(params),
}));

const records = [
  {
    id: 41,
    equipment_no: 'MIC-014',
    equipment_name: '外徑分厘卡',
    calibration_date: '2026-07-23',
    status: 'submitted',
    result: 'fail',
    data_level: 'detailed',
    row_version: 4,
  },
  {
    id: 42,
    equipment_no: 'CAL-008',
    equipment_name: '游標卡尺',
    calibration_date: '2026-07-22',
    status: 'draft',
    result: 'pending',
    data_level: 'detailed',
    row_version: 2,
  },
];

describe('校正工作佇列', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listMock.mockReturnValue({
      data: { items: records, page: 1, page_size: 25, total: 2 },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });
  });

  it('以後端風險排序的回傳順序顯示高風險紀錄在前', () => {
    render(<MemoryRouter><CalibrationWorkQueuePage /></MemoryRouter>);

    const queue = screen.getByRole('list', { name: '校正風險工作佇列' });
    expect(queue.children[0]).toHaveTextContent('MIC-014');
    expect(queue.children[0]).toHaveTextContent('待核准');
    expect(queue.children[1]).toHaveTextContent('CAL-008');
  });

  it('把篩選條件與風險排序參數直接交給後端', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><CalibrationWorkQueuePage /></MemoryRouter>);

    await user.selectOptions(screen.getByLabelText('工作狀態'), 'submitted');
    await user.type(screen.getByLabelText('搜尋校正紀錄'), 'MIC-014');

    expect(listMock).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 25,
      status: 'submitted',
      search: 'MIC-014',
      sort: 'risk',
      order: 'asc',
    });
  });
});
