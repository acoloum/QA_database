import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PatrolMeasurementTable from './PatrolMeasurementTable';
import type { PatrolDetailInput, PatrolTolerance } from './patrolFormUtils';

describe('PatrolMeasurementTable', () => {
  it('renders measurement cells and marks NG values', () => {
    const details: PatrolDetailInput[] = [
      { group: '第1組', pos: '前段', item: '外徑', min: '84', max: '86' },
    ];
    const tolerances = [
      { 項目: '外徑', 位置: '', 尺寸下限: 85, 尺寸上限: 86, 公差下限: null, 公差上限: null, 標準值: null, 單位: 'mm' },
    ] as PatrolTolerance[];

    render(
      <PatrolMeasurementTable
        groupCount={1}
        showInner={false}
        details={details}
        tolerances={tolerances}
        specStdValues={{}}
        onDetailChange={vi.fn()}
      />,
    );

    expect(screen.getByDisplayValue('84')).toHaveClass('is-invalid-breathing');
    expect(screen.queryByText('內徑')).not.toBeInTheDocument();
  });
});
