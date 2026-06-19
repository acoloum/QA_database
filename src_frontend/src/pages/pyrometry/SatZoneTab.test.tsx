import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { SatPoint } from '../../types';
import SatZoneTab from './SatZoneTab';

describe('SatZoneTab', () => {
  const point: SatPoint = {
    控溫區: 'Zone1',
    頻道: 13,
    修正值: '0.1',
    readings: [{ 控制儀表讀值: '180', 校正測試讀值: '179.8' }],
  };

  it('updates zone fields and readings', async () => {
    const user = userEvent.setup();
    const onUpdateField = vi.fn();
    const onUpdateReading = vi.fn();

    render(
      <SatZoneTab
        point={point}
        tolerance="1"
        onUpdateField={onUpdateField}
        onUpdateReading={onUpdateReading}
        onAddReading={() => undefined}
        onRemoveReading={() => undefined}
      />,
    );

    await user.type(screen.getByLabelText('控溫區名稱'), 'A');
    expect(onUpdateField).toHaveBeenCalledWith('控溫區', expect.stringContaining('A'));

    await user.type(screen.getByLabelText('控制儀表讀值 1'), '1');
    expect(onUpdateReading).toHaveBeenCalledWith(0, '控制儀表讀值', expect.stringContaining('1'));
  });

  it('adds and removes readings through callbacks', async () => {
    const user = userEvent.setup();
    const onAddReading = vi.fn();
    const onRemoveReading = vi.fn();

    render(
      <SatZoneTab
        point={{ ...point, readings: [...point.readings, { 控制儀表讀值: '', 校正測試讀值: '' }] }}
        tolerance="1"
        onUpdateField={() => undefined}
        onUpdateReading={() => undefined}
        onAddReading={onAddReading}
        onRemoveReading={onRemoveReading}
      />,
    );

    await user.click(screen.getByRole('button', { name: '＋ 新增讀值' }));
    expect(onAddReading).toHaveBeenCalledTimes(1);

    await user.click(screen.getAllByRole('button', { name: '✕' })[0]);
    expect(onRemoveReading).toHaveBeenCalledWith(0);
  });
});
