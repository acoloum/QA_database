import { describe, expect, it } from 'vitest';

import {
  buildTolerancePayload,
  createToleranceDetailRow,
  mapToleranceDetailToRow,
  validateToleranceRows,
} from './toleranceFormUtils';

describe('toleranceFormUtils', () => {
  it('建立預設明細列與載入編輯明細列', () => {
    expect(createToleranceDetailRow('row-1')).toEqual({
      id: 'row-1',
      item: '',
      position: '',
      size_min: '',
      size_max: '',
      tol_min: '',
      tol_max: '',
      std: '',
      unit: 'mm',
      remark: '',
    });

    expect(mapToleranceDetailToRow({
      測量項目: '外徑',
      測量位置: '前段',
      尺寸下限: 9.8,
      尺寸上限: 10.2,
      公差下限: -0.1,
      公差上限: 0.1,
      標準值: 10,
      單位: 'mm',
      備註: '重點尺寸',
    }, 'loaded-1')).toEqual({
      id: 'loaded-1',
      item: '外徑',
      position: '前段',
      size_min: '9.8',
      size_max: '10.2',
      tol_min: '-0.1',
      tol_max: '0.1',
      std: '10',
      unit: 'mm',
      remark: '重點尺寸',
    });
  });

  it('驗證明細數字欄位格式', () => {
    const result = validateToleranceRows([
      { ...createToleranceDetailRow('row-1'), item: '外徑', size_min: 'abc', tol_max: '0.1' },
      { ...createToleranceDetailRow('row-2'), item: '厚度', std: '1.2.3' },
    ]);

    expect(result).toEqual({
      'row-1:size_min': '「外徑」的尺寸下限需為有效數字',
      'row-2:std': '「厚度」的標準值需為有效數字',
    });
  });

  it('組出公差 payload 並過濾空白明細列', () => {
    const payload = buildTolerancePayload({
      date: '2026-06-20',
      material: '6061',
      spec: 'T6',
      vendorId: '5',
      remark: '量產使用',
      details: [
        {
          id: 'row-1',
          item: '外徑',
          position: '',
          size_min: '9.8',
          size_max: '10.2',
          tol_min: '',
          tol_max: '',
          std: '',
          unit: 'mm',
          remark: '',
        },
        createToleranceDetailRow('row-2'),
      ],
    });

    expect(payload).toEqual({
      建立日期: '2026-06-20',
      材質: '6061',
      規格: 'T6',
      廠商ID: 5,
      備註: '量產使用',
      details: [{
        測量項目: '外徑',
        測量位置: '',
        尺寸下限: 9.8,
        尺寸上限: 10.2,
        公差下限: null,
        公差上限: null,
        標準值: null,
        單位: 'mm',
        備註: '',
      }],
    });
  });

  it('組出公差 payload 時非法數字轉為 null 且保留 0', () => {
    const payload = buildTolerancePayload({
      date: '2026-06-21',
      material: '6061',
      spec: 'T6',
      vendorId: '',
      remark: '',
      details: [{
        id: 'row-1',
        item: '厚度',
        position: '',
        size_min: 'abc',
        size_max: '0',
        tol_min: '',
        tol_max: 'bad',
        std: '2.8',
        unit: 'mm',
        remark: '',
      }],
    });

    expect(payload.details[0]).toMatchObject({
      尺寸下限: null,
      尺寸上限: 0,
      公差下限: null,
      公差上限: null,
      標準值: 2.8,
    });
  });
});
