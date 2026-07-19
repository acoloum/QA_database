import { Line } from 'react-chartjs-2';
import type { SpcAttributeChartData } from '../../../types';
import { buildAttributeChartModel } from './attributeChartModel';

interface AttributeControlChartProps {
  chart: SpcAttributeChartData;
  subgroupKeys: string[];
}

const AttributeControlChart = ({ chart, subgroupKeys }: AttributeControlChartProps) => {
  const { data, options } = buildAttributeChartModel(chart, subgroupKeys);

  return (
    <div data-testid="attribute-chart" aria-label={`${chart.chart_type} 屬性管制圖`}>
      <Line data={data} options={options} />
    </div>
  );
};

export default AttributeControlChart;
