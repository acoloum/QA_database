import { describe, expect, it } from 'vitest';

import {
  buildReworkCostPayload,
  buildReworkExecutionPayload,
  formatDateTimeLocal,
} from './reworkFormPayload';

describe('reworkFormPayload', () => {
  it('將執行紀錄表單轉為後端 payload', () => {
    expect(buildReworkExecutionPayload({
      reworkNumber: 'RW-001',
      responsiblePerson: '王小明',
      department: '製造部',
      collaborators: '',
      startTime: '2026-06-20T08:30',
      expectedEndTime: '',
      actualEndTime: '',
      equipment: 'A1',
      method: '重工',
      sopNo: 'SOP-1',
      consumables: '',
      completedQty: '3',
      defectQty: '',
      status: '完成',
      abnormalStatus: '',
    })).toMatchObject({
      重工單號: 'RW-001',
      負責人員姓名: '王小明',
      完成數量: 3,
      不良數量: 0,
    });
  });

  it('計算成本總額並保留幣別', () => {
    expect(buildReworkCostPayload({
      reworkNumber: 'RW-001',
      costType: '材料成本',
      costItem: '鋁棒',
      unitCost: '12.5',
      quantity: '4',
      currency: 'TWD',
      recorder: '李小華',
      remark: '補料',
    })).toMatchObject({
      成本類型: '材料成本',
      單位成本: 12.5,
      數量: 4,
      總成本: 50,
      成本幣別: 'TWD',
    });
  });

  it('格式化 datetime-local 不受 UTC 轉換偏移', () => {
    expect(formatDateTimeLocal('2026-06-20T09:05:00')).toBe('2026-06-20T09:05');
  });
});
