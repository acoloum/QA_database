import { describe, expect, it } from 'vitest';

import type { ActionTask } from '../types';
import { normalizeTaskListResponse } from './taskResponseUtils';

const task = { id: 1, status: 'pending' } as ActionTask;

describe('taskResponseUtils', () => {
  it('支援直接回傳任務陣列', () => {
    expect(normalizeTaskListResponse([task])).toEqual([task]);
  });

  it('支援分頁格式中的 data 任務陣列', () => {
    expect(normalizeTaskListResponse({ data: [task] })).toEqual([task]);
  });

  it('異常回應格式回傳空陣列', () => {
    expect(normalizeTaskListResponse({ data: null })).toEqual([]);
    expect(normalizeTaskListResponse(null)).toEqual([]);
  });
});
