import { describe, expect, it } from 'vitest';

import { getClickedPointId, setChartPointCursor, shouldShowControlLegendLabel } from './spcChartOptions';

describe('spcChartOptions', () => {
  it('隱藏 sigma 輔助線 legend', () => {
    expect(shouldShowControlLegendLabel('+1σ')).toBe(false);
    expect(shouldShowControlLegendLabel('-2σ')).toBe(false);
    expect(shouldShowControlLegendLabel('平均值')).toBe(true);
  });

  it('由 chart 點選位置取得對應 id', () => {
    expect(getClickedPointId([10, 20, 30], [{ index: 1 }])).toBe(20);
    expect(getClickedPointId([10], [])).toBeNull();
  });

  it('依 hover 是否有資料點切換 cursor', () => {
    const target = { style: { cursor: '' } };
    const event = { native: { target } };

    setChartPointCursor(event, [{ index: 0 }]);
    expect(target.style.cursor).toBe('pointer');

    setChartPointCursor(event, []);
    expect(target.style.cursor).toBe('default');
  });
});
