import { describe, expect, it } from 'vitest';

import { addLocalDays, formatLocalDate, formatLocalMonth } from './dateUtils';

describe('dateUtils', () => {
  it('用指定時區格式化本地日期，避免 UTC 日期偏移', () => {
    const utcLateNight = new Date('2026-06-19T16:30:00.000Z');

    expect(formatLocalDate(utcLateNight, 'Asia/Taipei')).toBe('2026-06-20');
    expect(formatLocalMonth(utcLateNight, 'Asia/Taipei')).toBe('2026-06');
  });

  it('以日期文字做本地加天，不經過 UTC 轉換', () => {
    expect(addLocalDays('2026-06-20', 3)).toBe('2026-06-23');
    expect(addLocalDays('2026-01-31', 1)).toBe('2026-02-01');
  });
});
