import type { TooltipItem } from 'chart.js';
import { Card } from 'react-bootstrap';
import { Line } from 'react-chartjs-2';
import type { CpkTrend } from '../../types';

interface CpkTrendChartProps {
  cpkTrend: CpkTrend[];
}

const CpkTrendChart = ({ cpkTrend }: CpkTrendChartProps) => (
  <Card className="shadow-sm">
    <Card.Body>
      <h5 className="card-title text-center">Cpk 月趨勢圖</h5>
      <div style={{ height: '280px' }}>
        <Line
          data={{
            labels: cpkTrend.map((trend: CpkTrend) => trend.month),
            datasets: [
              {
                label: 'Cpk',
                data: cpkTrend.map((trend: CpkTrend) => trend.cpk),
                borderColor: '#0d6efd',
                backgroundColor: cpkTrend.map((trend: CpkTrend) => {
                  if (trend.cpk >= 1.33) return '#28a745';
                  if (trend.cpk >= 1.0) return '#ffc107';
                  return '#dc3545';
                }),
                pointRadius: 6,
                pointBorderWidth: 2,
                pointBorderColor: '#fff',
                tension: 0.2,
                fill: false,
              },
              {
                label: '目標線 (1.33)',
                data: Array(cpkTrend.length).fill(1.33),
                borderColor: '#28a745',
                borderDash: [8, 4],
                borderWidth: 1,
                pointRadius: 0,
                fill: false,
              },
              {
                label: '警戒線 (1.0)',
                data: Array(cpkTrend.length).fill(1.0),
                borderColor: '#dc3545',
                borderDash: [5, 5],
                borderWidth: 1,
                pointRadius: 0,
                fill: false,
              },
            ],
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
                  afterLabel: (ctx: TooltipItem<'line'>) => {
                    if (ctx.datasetIndex !== 0) return '';
                    const trend = cpkTrend[ctx.dataIndex];
                    return trend ? `樣本數: ${trend.count}` : '';
                  },
                },
              },
            },
            scales: {
              y: {
                title: { display: true, text: 'Cpk' },
                beginAtZero: true,
              },
            },
          }}
        />
      </div>
    </Card.Body>
  </Card>
);

export default CpkTrendChart;
