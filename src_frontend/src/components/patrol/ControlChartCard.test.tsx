import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ControlChartCard from './ControlChartCard';

vi.mock('react-chartjs-2', () => ({
  Line: () => <canvas aria-label="control chart" />,
}));

describe('ControlChartCard', () => {
  it('顯示管制圖標題並渲染折線圖', () => {
    render(
      <ControlChartCard
        title="X̄ 平均值管制圖"
        data={{ labels: ['1'], datasets: [] }}
        ids={[1]}
        getViolationReasons={() => ''}
      />,
    );

    expect(screen.getByText('X̄ 平均值管制圖')).toBeInTheDocument();
    expect(screen.getByLabelText('control chart')).toBeInTheDocument();
  });
});
