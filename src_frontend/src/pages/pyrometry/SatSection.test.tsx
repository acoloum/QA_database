import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { SatPoint } from '../../types';
import SatSection from './SatSection';

describe('SatSection', () => {
  const satPoints: SatPoint[] = [
    {
      控溫區: 'Zone1',
      頻道: 13,
      修正值: '0.1',
      readings: [{ 控制儀表讀值: '180', 校正測試讀值: '179.8' }],
    },
  ];

  it('renders SAT zone tabs and correction action', async () => {
    const user = userEvent.setup();
    const onApplyCorrections = vi.fn();
    const onUpdateSatField = vi.fn();

    render(
      <SatSection
        satPoints={satPoints}
        activeZone={0}
        setpoint="180"
        tolerance="1"
        satChartData={null}
        satRangeStart={0}
        satRangeEnd={0}
        satTimeLabels={[]}
        showSatDetail={false}
        furnaceSection={null}
        onSatFileUpload={() => undefined}
        onFurnaceFileUpload={() => undefined}
        onSatRangeStartChange={() => undefined}
        onSatRangeEndChange={() => undefined}
        onApplyRangeSat={() => undefined}
        onToggleSatDetail={() => undefined}
        onActiveZoneChange={() => undefined}
        onUpdateSatField={onUpdateSatField}
        onUpdateSatReading={() => undefined}
        onAddSatReading={() => undefined}
        onRemoveSatReading={() => undefined}
        onApplyCorrections={onApplyCorrections}
      />,
    );

    expect(screen.getByRole('button', { name: /Zone1/ })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '帶入儀器校正補正值' }));
    expect(onApplyCorrections).toHaveBeenCalledTimes(1);

    await user.type(screen.getByLabelText('控溫區名稱'), 'A');
    expect(onUpdateSatField).toHaveBeenCalledWith(0, '控溫區', expect.stringContaining('A'));
  });
});
