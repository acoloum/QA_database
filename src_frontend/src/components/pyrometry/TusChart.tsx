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
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

interface TusChartProps {
  時間: string[];
  數值: Record<string, number[]>;
  爐體數值?: Record<string, number[]>;
  設定溫度: number;
  公差: number;
}

const COLORS = [
  '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
  '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
  '#dcbeff', '#9a6324',
];

const TusChart = ({ 時間, 數值, 爐體數值, 設定溫度, 公差 }: TusChartProps) => {
  const channels = Object.keys(數值);
  const upper = 設定溫度 + 公差;
  const lower = 設定溫度 - 公差;

  const datasets = [
    ...channels.map((ch, i) => ({
      label: ch,
      data: 數值[ch],
      borderColor: COLORS[i % COLORS.length],
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 2,
      tension: 0.3,
    })),
    ...(爐體數值
      ? Object.keys(爐體數值).map((ch, i) => ({
          label: `${ch}（爐體）`,
          data: 爐體數值[ch],
          borderColor: COLORS[i % COLORS.length],
          backgroundColor: 'transparent',
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 2,
          tension: 0.3,
        }))
      : []),
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
          title: { display: true, text: 'TUS 溫度曲線' },
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
