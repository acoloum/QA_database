import { describe, expect, it } from 'vitest';

import {
  buildNcmrFormPayload,
  buildNcmrFormState,
  getTodayText,
  type NcmrFormValues,
} from './ncmrFormPayload';

describe('ncmrFormPayload', () => {
  it('編輯資料回填時保留不合格數量 0', () => {
    const state = buildNcmrFormState({
      日期: '2026-06-20',
      建立日期: '2026-06-21',
      來源: '巡檢',
      廠商: 'A廠',
      材質: '6061',
      產品資訊: '85*2.8',
      批號: 'B-001',
      不合格數量: 0,
      不良描述: '尺寸異常',
      不良原因大類: 'E',
      不良原因細項: 'E-07',
      發現人員姓名: '王小明',
      判定結果: '待處置',
    }, '2026-06-22');

    expect(state).toMatchObject({
      date: '2026-06-20',
      createDate: '2026-06-21',
      source: '巡檢',
      defectQty: '0',
      inspector: '王小明',
    });
  });

  it('空資料回填時使用預設日期與空白欄位', () => {
    expect(buildNcmrFormState(null, '2026-06-20')).toMatchObject({
      date: '2026-06-20',
      createDate: '2026-06-20',
      source: '進料',
      defectQty: '',
    });
  });

  it('建立 NCMR payload', () => {
    const values: NcmrFormValues = {
      date: '2026-06-20',
      createDate: '2026-06-21',
      source: '出貨檢',
      vendor: 'A廠',
      material: '6061',
      productInfo: '85*2.8',
      batch: 'B-001',
      defectQty: '0',
      desc: '尺寸異常',
      category: 'E',
      reason: 'E-07',
      inspector: '王小明',
      result: '待處置',
    };

    expect(buildNcmrFormPayload(values)).toEqual({
      日期: '2026-06-20',
      建立日期: '2026-06-21',
      來源: '出貨檢',
      廠商: 'A廠',
      材質: '6061',
      產品資訊: '85*2.8',
      批號: 'B-001',
      不合格數量: '0',
      不良描述: '尺寸異常',
      不良原因大類: 'E',
      不良原因細項: 'E-07',
      發現人員姓名: '王小明',
      判定結果: '待處置',
    });
  });

  it('更新 NCMR payload 時包含識別碼', () => {
    const payload = buildNcmrFormPayload(buildNcmrFormState(null, getTodayText()), 12);

    expect(payload).toMatchObject({ 識別碼: 12 });
  });
});
