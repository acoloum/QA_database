import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ChartRangeControls from './ChartRangeControls';

describe('ChartRangeControls', () => {
  it('updates range indices and triggers apply action', async () => {
    const user = userEvent.setup();
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();
    const onApply = vi.fn();

    render(
      <ChartRangeControls
        label="測試恆溫穩定期"
        start={0}
        end={2}
        timeLabels={['09:00', '09:10', '09:20']}
        applyLabel="套用測試"
        startAriaLabel="測試開始"
        endAriaLabel="測試結束"
        onStartChange={onStartChange}
        onEndChange={onEndChange}
        onApply={onApply}
      />,
    );

    await user.selectOptions(screen.getByLabelText('測試開始'), '1');
    expect(onStartChange).toHaveBeenCalledWith(1);

    await user.selectOptions(screen.getByLabelText('測試結束'), '1');
    expect(onEndChange).toHaveBeenCalledWith(1);

    expect(screen.getByText('共 3 筆')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '套用測試' }));
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it('falls back to index 0 when the selected value is invalid', () => {
    const onStartChange = vi.fn();

    render(
      <ChartRangeControls
        label="測試恆溫穩定期"
        start={0}
        end={0}
        timeLabels={['09:00']}
        applyLabel="套用測試"
        startAriaLabel="測試開始"
        endAriaLabel="測試結束"
        onStartChange={onStartChange}
        onEndChange={() => undefined}
        onApply={() => undefined}
      />,
    );

    fireEvent.change(screen.getByLabelText('測試開始'), { target: { value: 'invalid' } });
    expect(onStartChange).toHaveBeenCalledWith(0);
  });
});
