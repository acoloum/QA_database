import type { ChartData, ChartOptions, TooltipItem } from 'chart.js';
import type { SpcAttributeChartData, SpcAttributeCount } from '../../../types';

const decimal = (value: number | undefined) => value == null ? '—' : value.toFixed(4);

const countFor = (chart: SpcAttributeChartData, subgroupKeys: string[], index: number): SpcAttributeCount => {
  const supplied = chart.counts?.[index];
  const inspected = supplied?.inspected ?? chart.n[index];
  const nonconforming = supplied?.nonconforming ?? chart.x[index];
  return {
    key: subgroupKeys[index], inspected, nonconforming,
    proportion: supplied?.proportion ?? nonconforming / inspected,
  };
};

export const buildAttributeChartModel = (chart: SpcAttributeChartData, subgroupKeys: string[]) => {
  const data: ChartData<'line'> = {
    labels: subgroupKeys,
    datasets: [
      { label: chart.chart_type === 'p' ? '不符合比例 p' : '不符合單位 np', data: chart.values, borderColor: '#0d6efd', backgroundColor: '#0d6efd', tension: 0.1, order: 1 },
      { label: 'UCL', data: chart.ucl, borderColor: '#dc3545', borderDash: [5, 5], pointRadius: 0, order: 2 },
      { label: 'CL', data: chart.cl, borderColor: '#198754', pointRadius: 0, order: 2 },
      { label: 'LCL', data: chart.lcl, borderColor: '#dc3545', borderDash: [5, 5], pointRadius: 0, order: 2 },
    ],
  };
  const options: ChartOptions<'line'> = {
    responsive: true,
    plugins: { tooltip: { callbacks: {
      title: (items: TooltipItem<'line'>[]) => {
        const index = items[0]?.dataIndex ?? 0;
        return `子組：${countFor(chart, subgroupKeys, index).key}`;
      },
      label: (item: TooltipItem<'line'>) => {
        const index = item.dataIndex;
        const count = countFor(chart, subgroupKeys, index);
        if (item.dataset.label === 'UCL' || item.dataset.label === 'CL' || item.dataset.label === 'LCL') return `${item.dataset.label}：${decimal(Number(item.raw))}`;
        return [
          `x（不符合）：${count.nonconforming}`, `n（受檢）：${count.inspected}`,
          `比例：${decimal(count.proportion)}`, `CL：${decimal(chart.cl[index])}`,
          `LCL：${decimal(chart.lcl[index])}`, `UCL：${decimal(chart.ucl[index])}`,
        ];
      },
    } } },
    scales: { y: { beginAtZero: true } },
  };
  return { data, options };
};
