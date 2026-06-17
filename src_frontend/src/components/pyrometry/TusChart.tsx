import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, annotationPlugin,
);

interface TusChartProps {
  時間: string[];
  數值: Record<string, number[]>;
  設定溫度: number;
  公差: number;
  startIdx?: number;
  endIdx?: number;
  標題?: string;
}

const COLORS = [
  '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
  '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
  '#dcbeff', '#9a6324',
];

const TusChart = ({ 時間, 數值, 設定溫度, 公差, startIdx, endIdx, 標題 }: TusChartProps) => {
  const channels = Object.keys(數值);
  const upper = 設定溫度 + 公差;
  const lower = 設定溫度 - 公差;
  const hasRange = startIdx !== undefined && endIdx !== undefined;

  // 恆溫穩定期內：超上限→紅、低於下限→藍
  const inSoak = (j: number) =>
    hasRange && j >= (startIdx as number) && j <= (endIdx as number);
  const ptStateColor = (v: number | null, j: number, base: string) => {
    if (!inSoak(j) || v == null) return base;
    if (v > upper) return '#dc3545';   // 超上限：紅
    if (v < lower) return '#0d6efd';   // 低於下限：藍
    return base;
  };
  const ptIsOut = (v: number | null, j: number) =>
    inSoak(j) && v != null && (v > upper || v < lower);

  const datasets = [
    ...channels.map((ch, i) => {
      const base = COLORS[i % COLORS.length];
      const ptColor = 數值[ch].map((v, j) => ptStateColor(v, j, base));
      const ptRadius = 數值[ch].map((v, j) => (ptIsOut(v, j) ? 4 : 2));
      return {
        label: ch,
        data: 數值[ch],
        borderColor: base,
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointBackgroundColor: ptColor,
        pointBorderColor: ptColor,
        pointRadius: ptRadius,
        tension: 0.3,
      };
    }),
    {
      label: `上限 (${upper}°C)`,
      data: Array(時間.length).fill(upper),
      borderColor: '#ff0000',
      backgroundColor: 'transparent',
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
    },
    {
      label: `下限 (${lower}°C)`,
      data: Array(時間.length).fill(lower),
      borderColor: '#ff0000',
      backgroundColor: 'transparent',
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
    },
  ];

  return (
    <Line
      data={{ labels: 時間, datasets }}
      options={{
        responsive: true,
        plugins: {
          legend: { position: 'bottom' as const },
          title: { display: true, text: 標題 || 'TUS 溫度曲線' },
          annotation: hasRange
            ? {
                annotations: {
                  soakRange: {
                    type: 'box' as const,
                    xMin: startIdx,
                    xMax: endIdx,
                    backgroundColor: 'rgba(25, 118, 210, 0.12)',
                    borderColor: 'rgba(25, 118, 210, 0.4)',
                    borderWidth: 1,
                    label: {
                      display: true,
                      content: '恆溫穩定期',
                      position: 'start' as const,
                      color: '#1565c0',
                      font: { size: 11 },
                    },
                  },
                },
              }
            : {},
        },
        scales: {
          y: { title: { display: true, text: '溫度 (°C)' } },
          x: { title: { display: true, text: '時間' } },
        },
      }}
    />
  );
};

export default TusChart;
