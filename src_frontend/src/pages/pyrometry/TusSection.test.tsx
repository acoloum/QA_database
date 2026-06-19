import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { TusPoint } from '../../types';
import TusSection from './TusSection';

describe('TusSection', () => {
  const tusPoints: TusPoint[] = [
    { 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '0.1', 最高溫: '181', 最低溫: '179' },
  ];

  it('updates TUS point fields and applies corrections', async () => {
    const user = userEvent.setup();
    const onUpdateTus = vi.fn();
    const onApplyCorrections = vi.fn();

    render(
      <TusSection
        tusPoints={tusPoints}
        setpoint="180"
        tolerance="10"
        chartData={null}
        rangeStart={0}
        rangeEnd={0}
        showDetail={false}
        timeLabels={[]}
        onFileUpload={() => undefined}
        onRangeStartChange={() => undefined}
        onRangeEndChange={() => undefined}
        onApplyRangeTus={() => undefined}
        onToggleDetail={() => undefined}
        onUpdateTus={onUpdateTus}
        onApplyCorrections={onApplyCorrections}
      />,
    );

    await user.click(screen.getByRole('button', { name: '帶入儀器校正補正值' }));
    expect(onApplyCorrections).toHaveBeenCalledTimes(1);

    await user.type(screen.getByLabelText('點位 1'), 'A');
    expect(onUpdateTus).toHaveBeenCalledWith(0, '點位', expect.stringContaining('A'));
  });
});
