import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ProcessCapabilityCard from './ProcessCapabilityCard';
import WecoViolationAlert from './WecoViolationAlert';

describe('PatrolChartsParts', () => {
  it('顯示製程能力指標', () => {
    render(<ProcessCapabilityCard processCapability={{
      available: true,
      cp: 1.5,
      cpk: 1.33,
      pp: 1.4,
      ppk: 1.2,
      usl: 10,
      lsl: 8,
      ppm: { upper: 10, lower: 5, total: 15 },
    }} statsItem="外徑" />);

    expect(screen.getByText('製程能力指標')).toBeInTheDocument();
    expect(screen.getByText('1.330')).toBeInTheDocument();
  });

  it('顯示 WECO 異常筆數', () => {
    render(<WecoViolationAlert violations={[{ label: '06/20', type: 'xbar', reasons: ['超出 UCL'] }]} />);
    expect(screen.getByText(/偵測到 1 個製程異常數據點/)).toBeInTheDocument();
  });
});
