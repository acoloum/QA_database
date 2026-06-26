import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PaginationBar from './PaginationBar';

describe('PaginationBar', () => {
  it('renders compact page links with ellipses for large page counts', () => {
    render(<PaginationBar page={10} perPage={10} total={200} onPageChange={vi.fn()} />);

    expect(screen.getByText('共 200 筆，第 10 / 20 頁')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '9' })).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '11' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '20' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument();
  });

  it('supports first, previous, next and last navigation', () => {
    const onPageChange = vi.fn();
    render(<PaginationBar page={3} perPage={10} total={50} onPageChange={onPageChange} />);

    fireEvent.click(screen.getByLabelText('第一頁'));
    fireEvent.click(screen.getByLabelText('上一頁'));
    fireEvent.click(screen.getByLabelText('下一頁'));
    fireEvent.click(screen.getByLabelText('最後一頁'));

    expect(onPageChange).toHaveBeenNthCalledWith(1, 1);
    expect(onPageChange).toHaveBeenNthCalledWith(2, 2);
    expect(onPageChange).toHaveBeenNthCalledWith(3, 4);
    expect(onPageChange).toHaveBeenNthCalledWith(4, 5);
  });
});
