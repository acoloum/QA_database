import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { SpcStudyResult } from '../../../types';

vi.mock('react-chartjs-2', () => ({
  Line: () => <div data-testid="attribute-chart-line" />,
}));

import AttributeStudyPanel from './AttributeStudyPanel';

const npNotApplicableResult = {
  analysis_family: 'attribute',
  method_version: '2026.2',
  charts: null,
  applicability: {
    applicable: false,
    reason_code: 'NP_REQUIRES_FIXED_SUBGROUP_SIZE',
    message: 'np 圖需要固定子組大小',
  },
  stability: { evaluated: false, stable: null, violations: [], rules_used: [] },
} as unknown as SpcStudyResult;

const applicableResult = {
  analysis_family: 'attribute',
  method_version: '2026.2',
  charts: {
    chart_type: 'p',
    values: [0.1, 0.2], cl: [0.15, 0.15], ucl: [0.3, 0.31], lcl: [0, 0],
    n: [10, 20], x: [1, 4],
    counts: [
      { key: '2026-07-01', inspected: 10, nonconforming: 1, proportion: 0.1 },
      { key: '2026-07-02', inspected: 20, nonconforming: 4, proportion: 0.2 },
    ],
  },
  applicability: { applicable: true, chart_type: 'p', eligibility: { excluded: 2 } },
  stability: { evaluated: true, stable: true, violations: [], rules_used: [] },
} as unknown as SpcStudyResult;

describe('AttributeStudyPanel', () => {
  it('np 子組不固定時顯示原因而不畫誤導圖表', () => {
    render(<AttributeStudyPanel result={npNotApplicableResult} />);

    expect(screen.getByText(/np 圖需要固定子組大小/)).toBeInTheDocument();
    expect(screen.queryByTestId('attribute-chart')).not.toBeInTheDocument();
  });

  it('適用的 p 圖以逐點界限與子組計數輸出 tooltip 證據', () => {
    render(<AttributeStudyPanel result={applicableResult} />);

    expect(screen.getByTestId('attribute-chart')).toBeInTheDocument();
    expect(screen.getByText('已排除 2 筆無法判定符合性的資料')).toBeInTheDocument();
  });
});
