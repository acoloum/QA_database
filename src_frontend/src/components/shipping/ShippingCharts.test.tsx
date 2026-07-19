import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ShippingCharts from './ShippingCharts';

vi.mock('react-chartjs-2', () => ({
  Line: () => <canvas aria-label="shipping control chart" />,
  Bar: () => <canvas aria-label="histogram chart" />,
}));

vi.mock('../../utils/spcChartModel', () => ({
  mergeOngoingStudyForDisplay: (data: unknown) => data,
  buildSpcChartModel: () => ({
    chartData: {
      xBar: {
        labels: ['1', '2'],
        datasets: [{ label: '平均值', data: [9.8, 10.1] }],
      },
      rChart: {
        labels: ['1', '2'],
        datasets: [{ label: '全距', data: [0.1, 0.2] }],
      },
    },
    chartType: 'xbar_s',
    locationLabel: '平均值 X̄',
    variationLabel: '標準差 S',
    ids: [1, 2],
    analysis: { violations: [{ label: '2', type: 'xbar', reasons: ['超出 UCL'] }] },
    rAnalysis: { violations: [] },
    statsSummary: { count: 2, mean: '10.0', stdDev: '0.1', cv: '1', min: '9.8', max: '10.1', violations: 1 },
    processCapability: {
      available: true,
      applicable: 'capability',
      method: 'G',
      cp: 1.5,
      cpk: 1.33,
      pp: 1.4,
      ppk: 1.2,
      usl: 11,
      lsl: 9,
      ppm: { upper: 0, lower: 0, total: 0 },
    },
    histogramData: null,
    distributionStats: null,
    cpkTrend: null,
  }),
}));

vi.mock('../spc/SpcStudyPanel', () => ({
  default: ({ source, filters }: { source: string; filters: Record<string, unknown> }) => (
    <div data-testid="spc-study-panel">SPC 研究與基準 · {source} · {String(filters.vendor)}</div>
  ),
}));

vi.mock('../../hooks/useShipping', () => ({
  useShippingStats: () => ({
    data: {},
  }),
  useExportSpcReport: () => ({ mutate: vi.fn(), isPending: false }),
  useShippingMeasurements: () => ({ data: [], isLoading: false }),
  useSetMeasurementExclusion: () => ({ mutate: vi.fn(), isPending: false }),
}));

describe('ShippingCharts', () => {
  it('使用共用 SPC 元件顯示 WECO、能力卡與兩張管制圖', () => {
    render(
      <ShippingCharts
        vendor="A廠"
        material="6061"
        spec="10"
        startDate="2026-06-01"
        endDate="2026-06-20"
      />,
    );

    expect(screen.getByText(/偵測到 1 個製程異常數據點/)).toBeInTheDocument();
    expect(screen.getByText('製程能力指標')).toBeInTheDocument();
    expect(screen.getByText('平均值 X̄ 管制圖')).toBeInTheDocument();
    expect(screen.getByText('標準差 S 管制圖')).toBeInTheDocument();
    expect(screen.getByTestId('spc-study-panel')).toHaveTextContent('shipping · A廠');
    expect(screen.queryByRole('button', { name: '凍結目前界限' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '解除凍結' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '進階變數分析' })).toHaveAttribute(
      'href',
      '/spc/advanced?family=variable&source=shipping&vendor=A%E5%BB%A0&material=6061&spec=10&field=%E5%A4%96%E5%BE%91&start_date=2026-06-01&end_date=2026-06-20',
    );
  });

  it('深層連結省略空白條件且正確編碼', () => {
    render(<ShippingCharts vendor="甲＆乙" material="" spec="10/2" startDate="" endDate="" />);
    expect(screen.getByRole('link', { name: '進階變數分析' })).toHaveAttribute(
      'href',
      '/spc/advanced?family=variable&source=shipping&vendor=%E7%94%B2%EF%BC%86%E4%B9%99&spec=10%2F2&field=%E5%A4%96%E5%BE%91',
    );
  });
});
