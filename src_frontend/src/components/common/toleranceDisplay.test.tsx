import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ToleranceBadgeList } from './toleranceDisplay';
import { formatToleranceRange } from './toleranceFormat';

describe('toleranceDisplay', () => {
  it('formats size limits, relative tolerances and one-sided limits', () => {
    expect(formatToleranceRange({ 尺寸下限: 9.8, 尺寸上限: 10.2 })).toBe('9.8~10.2');
    expect(formatToleranceRange({ 公差下限: -0.1, 公差上限: 0.2 })).toBe('+0.2/-0.1');
    expect(formatToleranceRange({ 尺寸上限: 10.2 })).toBe('最大10.2');
    expect(formatToleranceRange({ 尺寸下限: 9.8 })).toBe('最小9.8');
  });

  it('uses max display for concentricity standard values', () => {
    expect(formatToleranceRange({ 項目: '同心度', 標準值: 0.4, 公差下限: 0, 公差上限: 0.4 })).toBe('最大0.4');
  });

  it('renders tolerance badges with units', () => {
    render(
      <ToleranceBadgeList
        tolerances={[
          { 項目: '外徑', 尺寸下限: 9.8, 尺寸上限: 10.2, 單位: 'mm' },
          { 項目: '同心度', 標準值: 0.4, 單位: 'mm' },
        ]}
      />,
    );

    expect(screen.getByText('外徑: 9.8~10.2 mm')).toBeInTheDocument();
    expect(screen.getByText('同心度: 最大0.4 mm')).toBeInTheDocument();
  });
});
