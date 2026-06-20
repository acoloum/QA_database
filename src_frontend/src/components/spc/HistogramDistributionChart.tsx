import type { ChartData, TooltipItem } from 'chart.js';
import { Card } from 'react-bootstrap';
import { Chart } from 'react-chartjs-2';
import type { HistogramBin } from '../../types';
import type { SpcHistogramData } from '../../utils/spcChartModel';

interface HistogramDistributionChartProps {
  histogramData: SpcHistogramData;
  sampleCount: number;
}

const buildSpecLimitDataset = (
  label: string,
  limit: number,
  bins: HistogramBin[],
) => ({
  type: 'line' as const,
  label: `${label} (${limit.toFixed(2)})`,
  data: bins.map((bin: HistogramBin) => {
    const dist = Math.abs(bin.midpoint - limit);
    const binWidth = bins.length > 1 ? bins[1].midpoint - bins[0].midpoint : 1;
    return dist < binWidth / 2 ? Math.max(...bins.map((item: HistogramBin) => item.count)) * 1.1 : null;
  }),
  borderColor: '#e83e8c',
  borderDash: [5, 5],
  borderWidth: 2,
  pointRadius: 0,
  spanGaps: false,
  order: 0,
});

const HistogramDistributionChart = ({ histogramData, sampleCount }: HistogramDistributionChartProps) => (
  <Card className="shadow-sm">
    <Card.Body>
      <h5 className="card-title text-center">量測值分佈直方圖 + 常態分佈曲線</h5>
      <div style={{ height: '320px' }}>
        <Chart
          type="bar"
          data={{
            labels: histogramData.bins.map((bin: HistogramBin) => bin.label),
            datasets: [
              {
                type: 'bar' as const,
                label: '頻次',
                data: histogramData.bins.map((bin: HistogramBin) => bin.count),
                backgroundColor: 'rgba(13, 110, 253, 0.5)',
                borderColor: '#0d6efd',
                borderWidth: 1,
                order: 2,
                barPercentage: 1.0,
                categoryPercentage: 1.0,
              },
              {
                type: 'line' as const,
                label: '常態分佈',
                data: histogramData.normalCurve,
                borderColor: '#dc3545',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.4,
                order: 1,
              },
              ...(histogramData.usl != null ? [buildSpecLimitDataset('USL', histogramData.usl, histogramData.bins)] : []),
              ...(histogramData.lsl != null ? [buildSpecLimitDataset('LSL', histogramData.lsl, histogramData.bins)] : []),
            ] as ChartData<'bar'>['datasets'],
          }}
          options={{
            maintainAspectRatio: false,
            plugins: {
              legend: {
                display: true,
                position: 'bottom',
                labels: { usePointStyle: true, font: { size: 10 } },
              },
              tooltip: {
                callbacks: {
                  title: (items: TooltipItem<'bar'>[]) => items[0]?.label || '',
                  label: (ctx: TooltipItem<'bar'>) => {
                    if (ctx.dataset.label === '頻次') return `數量: ${ctx.raw}`;
                    if (ctx.dataset.label === '常態分佈') return `期望值: ${(ctx.raw as number)?.toFixed(1)}`;
                    return ctx.dataset.label || '';
                  },
                },
              },
            },
            scales: {
              x: { title: { display: true, text: '量測值區間' } },
              y: { title: { display: true, text: '頻次' }, beginAtZero: true },
            },
          }}
        />
      </div>
      <div className="text-center text-muted small mt-2">
        平均值: {histogramData.allMean.toFixed(3)} | 標準差: {histogramData.allStdDev.toFixed(3)} | 樣本數: {sampleCount}
      </div>
    </Card.Body>
  </Card>
);

export default HistogramDistributionChart;
