import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import FurnaceRecorderSection from './FurnaceRecorderSection';
import type { ChartData } from './pyrometryFormUtils';

vi.mock('../../components/pyrometry/TusChart', () => ({
  default: () => <div data-testid="tus-chart" />,
}));

vi.mock('../../components/pyrometry/TusDataTable', () => ({
  default: () => <div data-testid="tus-data-table" />,
}));

describe('FurnaceRecorderSection', () => {
  const chartData: ChartData = {
    時間: ['09:00', '09:10'],
    數值: { F1: [180, 181] },
  };

  it('renders nothing when furnace chart data is absent', () => {
    const { container } = render(
      <FurnaceRecorderSection
        furnaceChartData={null}
        setpoint="180"
        tolerance="10"
        furnaceRangeStart={0}
        furnaceRangeEnd={0}
        furnaceTimeLabels={[]}
        showFurnaceDetail={false}
        onFurnaceRangeStartChange={() => undefined}
        onFurnaceRangeEndChange={() => undefined}
        onApplyRangeFurnace={() => undefined}
        onToggleFurnaceDetail={() => undefined}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('updates furnace range and detail actions', async () => {
    const user = userEvent.setup();
    const onFurnaceRangeStartChange = vi.fn();
    const onFurnaceRangeEndChange = vi.fn();
    const onApplyRangeFurnace = vi.fn();
    const onToggleFurnaceDetail = vi.fn();

    render(
      <FurnaceRecorderSection
        furnaceChartData={chartData}
        setpoint="180"
        tolerance="10"
        furnaceRangeStart={0}
        furnaceRangeEnd={1}
        furnaceTimeLabels={chartData.時間}
        showFurnaceDetail
        onFurnaceRangeStartChange={onFurnaceRangeStartChange}
        onFurnaceRangeEndChange={onFurnaceRangeEndChange}
        onApplyRangeFurnace={onApplyRangeFurnace}
        onToggleFurnaceDetail={onToggleFurnaceDetail}
      />,
    );

    expect(screen.getByTestId('tus-chart')).toBeInTheDocument();
    expect(screen.getByTestId('tus-data-table')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('爐體恆溫穩定期開始'), '1');
    expect(onFurnaceRangeStartChange).toHaveBeenCalledWith(1);

    await user.selectOptions(screen.getByLabelText('爐體恆溫穩定期結束'), '0');
    expect(onFurnaceRangeEndChange).toHaveBeenCalledWith(0);

    await user.click(screen.getByRole('button', { name: '套用並回填控制儀表讀值' }));
    expect(onApplyRangeFurnace).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: '隱藏爐體詳細數據表' }));
    expect(onToggleFurnaceDetail).toHaveBeenCalledTimes(1);
  });
});
