import { describe, expect, it } from 'vitest';

import {
  calculateReworkCostTotal,
  formatReworkCurrency,
  getReworkStatusBadge,
} from './reworkDetailUtils';
import type { ReworkCostDetail } from '../../types';

describe('reworkDetailUtils', () => {
  it('formats invalid and valid cost values consistently', () => {
    expect(formatReworkCurrency(12.5)).toBe('$12.50');
    expect(formatReworkCurrency('abc')).toBe('$0.00');
    expect(formatReworkCurrency(null)).toBe('$0.00');
  });

  it('calculates cost total without parseFloat truncation', () => {
    const costs = [
      { 總成本: '10.5' },
      { 總成本: '2abc' },
      { 總成本: 4 },
    ] as ReworkCostDetail[];

    expect(calculateReworkCostTotal(costs)).toBe(14.5);
  });

  it('maps rework status to badge classes', () => {
    expect(getReworkStatusBadge('已完成')).toBe('bg-info text-dark');
    expect(getReworkStatusBadge('已拒絕')).toBe('bg-danger');
    expect(getReworkStatusBadge('待審核')).toBe('bg-warning text-dark');
  });
});
