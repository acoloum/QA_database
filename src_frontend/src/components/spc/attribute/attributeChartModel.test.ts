import { describe, expect, it } from 'vitest';
import { buildAttributeChartModel } from './attributeChartModel';

describe('buildAttributeChartModel', () => {
  it('保留逐點界限、n/x 與可稽核 tooltip 證據', () => {
    const model = buildAttributeChartModel({
      chart_type: 'p', values: [0.1, 0.2], cl: [0.15, 0.15], ucl: [0.3, 0.31], lcl: [0, 0],
      n: [10, 20], x: [1, 4],
    }, ['attribute:2026-07-01', 'attribute:2026-07-02']);

    expect(model.data.datasets.find(dataset => dataset.label === 'UCL')?.data).toEqual([0.3, 0.31]);
    const callbacks = model.options.plugins?.tooltip?.callbacks as unknown as {
      title: (items: unknown[]) => string;
      label: (item: unknown) => string[];
    };
    expect(callbacks.title([{ dataIndex: 1 }])).toBe('子組：attribute:2026-07-02');
    expect(callbacks.label({ dataIndex: 1, dataset: { label: '不符合比例 p' }, raw: 0.2 })).toEqual([
      'x（不符合）：4', 'n（受檢）：20', '比例：0.2000', 'CL：0.1500', 'LCL：0.0000', 'UCL：0.3100',
    ]);
  });
});
