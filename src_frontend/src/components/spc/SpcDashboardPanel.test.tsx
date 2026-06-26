import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SpcDashboardPanel from './SpcDashboardPanel';
import type { SpcChartModel } from '../../utils/spcChartModel';

vi.mock('./CpkTrendChart', () => ({
  default: () => <div data-testid="cpk-trend-chart" />,
}));

vi.mock('./HistogramDistributionChart', () => ({
  default: () => <div data-testid="histogram-chart" />,
}));

vi.mock('../patrol/ControlChartCard', () => ({
  default: ({ title }: { title: string }) => <div>{title}</div>,
}));

vi.mock('../patrol/ProcessCapabilityCard', () => ({
  default: () => <div data-testid="process-capability-card" />,
}));

vi.mock('../patrol/WecoViolationAlert', () => ({
  default: () => <div data-testid="weco-alert" />,
}));

const model: SpcChartModel = {
  chartData: {
    xBar: { labels: ['A'], datasets: [] },
    rChart: { labels: ['A'], datasets: [] },
  },
  ids: ['1'],
  analysis: { statuses: [null], violations: [{ label: 'A', type: 'xbar', reasons: ['超出 UCL'] }] },
  rAnalysis: { statuses: [null], violations: [] },
  statsSummary: {
    count: 1,
    mean: '10.000',
    min: '10.000',
    max: '10.000',
    range: '0.000',
    stdDev: '0.000',
    cv: '0.00',
    violations: 1,
  },
  processCapability: { available: false },
  histogramData: {
    bins: [{ label: '9-11', min: 9, max: 11, midpoint: 10, count: 1 }],
    normalCurve: [1],
    allMean: 10,
    allStdDev: 0,
  },
  distributionStats: {
    skewness: 0,
    kurtosis: 0,
    normality: 'good',
    normality_label: '良好',
  },
  cpkTrend: [
    { month: '2026-05', cpk: 1.1, count: 10 },
    { month: '2026-06', cpk: 1.2, count: 12 },
  ],
};

describe('SpcDashboardPanel', () => {
  it('renders shared SPC cards, charts and legend from a chart model', () => {
    render(
      <SpcDashboardPanel
        model={model}
        statsItem="外徑"
        emptyMessage="沒有資料"
        sampleCount={1}
      />,
    );

    expect(screen.getByTestId('weco-alert')).toBeInTheDocument();
    expect(screen.getByText('樣本數')).toBeInTheDocument();
    expect(screen.getByText('常態性檢查')).toBeInTheDocument();
    expect(screen.getByTestId('process-capability-card')).toBeInTheDocument();
    expect(screen.getByText('X̄ 平均值管制圖')).toBeInTheDocument();
    expect(screen.getByText('R 全距管制圖')).toBeInTheDocument();
    expect(screen.getByText('正常')).toBeInTheDocument();
    expect(screen.getByTestId('cpk-trend-chart')).toBeInTheDocument();
  });

  it('renders configured empty message when chart data is absent', () => {
    render(
      <SpcDashboardPanel
        model={{ ...model, chartData: null }}
        statsItem="外徑"
        emptyMessage="沒有足夠資料"
      />,
    );

    expect(screen.getByText('沒有足夠資料')).toBeInTheDocument();
  });
});
