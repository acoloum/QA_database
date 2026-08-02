import { describe, expect, it } from 'vitest';
import {
  buildReworkListQuery,
  getReworkErrorMessage,
  resolveReworkFollowUp,
} from './reworkPageUtils';
import type { ReworkApplication } from '../../types';

const baseRework: ReworkApplication = {
  識別碼: 7,
  申請單號: 'RW-001',
  申請日期: '2026-06-20',
  NCMR_ID: 12,
  ncmr_number: 'NCMR-012',
  申請人員姓名: '王小明',
  部門: '品保',
  產品資訊: 'A-100',
  重工數量: 3,
  緊急程度: '普通',
  狀態: '執行中',
};

describe('reworkPageUtils', () => {
  it('只把有值的篩選條件加入重工列表查詢參數', () => {
    expect(buildReworkListQuery({
      statusFilter: '執行中',
      startDate: '',
      endDate: '2026-06-30',
    })).toEqual({ status: '執行中', end_date: '2026-06-30' });
  });

  it('從 API error 取出後端訊息，沒有訊息時回傳預設文案', () => {
    expect(getReworkErrorMessage({
      response: { data: { error: '不可刪除已完成資料' } },
    }, '刪除失敗')).toBe('不可刪除已完成資料');

    expect(getReworkErrorMessage(new Error('network'), '刪除失敗')).toBe('刪除失敗');
  });

  it('NCMR 尚未關聯 CAPA 時產生結案追蹤提示資料', () => {
    expect(resolveReworkFollowUp(baseRework, {
      related_capa_id: null,
      NCMR單號: 'NCMR-BACKEND',
    })).toEqual({
      show: true,
      ncmrId: 12,
      ncmrNumber: 'NCMR-012',
    });
  });

  it('已關聯 CAPA 或沒有 NCMR_ID 時不產生結案追蹤提示', () => {
    expect(resolveReworkFollowUp(baseRework, { related_capa_id: 5 })).toBeNull();
    expect(resolveReworkFollowUp({ ...baseRework, NCMR_ID: 0 }, { related_capa_id: null })).toBeNull();
  });
});
