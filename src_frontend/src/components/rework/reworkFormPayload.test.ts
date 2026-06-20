import { describe, expect, it } from 'vitest';

import {
  buildReworkApplicationPayload,
  buildReworkCostPayload,
  buildReworkExecutionPayload,
  calculateReworkTotalCost,
  formatDateTimeLocal,
  parseReworkCostNumber,
} from './reworkFormPayload';

describe('reworkFormPayload', () => {
  it('將重工申請表單轉為後端 payload', () => {
    expect(buildReworkApplicationPayload({
      ncmrId: '12',
      applicant: '王小明',
      department: '品保部',
      urgency: '緊急',
      productInfo: '85*2.8',
      batchNo: 'B-001',
      quantity: '0',
      reason: '尺寸異常',
      expectedDate: '2026-06-30',
    })).toEqual({
      NCMR_ID: 12,
      申請人員姓名: '王小明',
      部門: '品保部',
      緊急程度: '緊急',
      產品資訊: '85*2.8',
      批號: 'B-001',
      重工數量: 0,
      申請原因: '尺寸異常',
      預計完成日期: '2026-06-30',
    });
  });

  it('重工申請數字欄位非法或空白時使用可預期的空值', () => {
    expect(buildReworkApplicationPayload({
      ncmrId: '',
      applicant: '',
      department: '',
      urgency: '普通',
      productInfo: '',
      batchNo: '',
      quantity: 'abc',
      reason: '',
      expectedDate: '',
    })).toMatchObject({
      NCMR_ID: null,
      重工數量: 0,
    });
  });

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

  it('成本數字解析保留 0 並在空白時套用指定預設值', () => {
    expect(parseReworkCostNumber('0', 1)).toBe(0);
    expect(parseReworkCostNumber('', 1)).toBe(1);
    expect(parseReworkCostNumber('abc', 1)).toBe(1);
  });

  it('預估成本顯示以空白數量視為 0', () => {
    expect(calculateReworkTotalCost('12.5', '4')).toBe(50);
    expect(calculateReworkTotalCost('12.5', '')).toBe(0);
  });

  it('成本 payload 允許數量為 0，不會被預設值覆蓋', () => {
    expect(buildReworkCostPayload({
      reworkNumber: 'RW-001',
      costType: '其他成本',
      costItem: '折讓',
      unitCost: '12.5',
      quantity: '0',
      currency: 'TWD',
      recorder: '',
      remark: '',
    })).toMatchObject({
      數量: 0,
      總成本: 0,
    });
  });

  it('格式化 datetime-local 不受 UTC 轉換偏移', () => {
    expect(formatDateTimeLocal('2026-06-20T09:05:00')).toBe('2026-06-20T09:05');
  });
});
