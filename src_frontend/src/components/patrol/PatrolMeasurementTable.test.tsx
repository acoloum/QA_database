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

  it('即時模式有違規時，標記黃框並顯示提示文字；沒有違規的儲存格不受影響', () => {
    const details: PatrolDetailInput[] = [
      { group: '第1組', pos: '前段', item: '外徑', min: '85', max: '85.4' },
      { group: '第1組', pos: '前段', item: '厚度', min: '2.5', max: '3.0' },
    ];

    render(
      <PatrolMeasurementTable
        groupCount={1}
        showInner={false}
        details={details}
        tolerances={[]}
        specStdValues={{}}
        onDetailChange={vi.fn()}
        liveViolations={{
          '前段|外徑|第1組': { chartKind: 'location', label: 'Rule 1: 超出控制限', hint: '單點急劇偏移，先重量一次確認非量測失誤' },
        }}
      />,
    );

    expect(screen.getByDisplayValue('85')).toHaveClass('patrol-live-warning');
    expect(screen.getByText(/單點急劇偏移/)).toBeInTheDocument();
    // 沒有對應 liveViolations key 的儲存格（前段｜厚度）不應被標記黃框
    expect(screen.getByDisplayValue('2.5')).not.toHaveClass('patrol-live-warning');
  });
});
