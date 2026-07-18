import { fireEvent, render, screen } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import SpcOcapOffcanvas from './SpcOcapOffcanvas';

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

describe('SpcOcapOffcanvas', () => {
  it('提供 6M、重新量測、製程調整、產品處置、責任人與有效性欄位', () => {
    const onSave = vi.fn();
    render(<SpcOcapOffcanvas show eventId={81} onHide={vi.fn()} onSave={onSave} />);

    expect(screen.getByLabelText('6M 調查')).toBeInTheDocument();
    expect(screen.getByLabelText('重新量測')).toBeInTheDocument();
    expect(screen.getByLabelText('製程調整')).toBeInTheDocument();
    expect(screen.getByLabelText('產品處置')).toBeInTheDocument();
    expect(screen.getByLabelText('責任人 ID')).toBeInTheDocument();
    expect(screen.getByLabelText('有效性確認')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('結案'));
    expect(screen.getByRole('button', { name: '儲存 OCAP' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('有效性確認'), { target: { value: '連續三批未再發生' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      eventId: 81,
      payload: expect.objectContaining({ status: 'closed', effectiveness: '連續三批未再發生' }),
    }));
  });
});
