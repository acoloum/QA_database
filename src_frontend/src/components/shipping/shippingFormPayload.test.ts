import { describe, expect, it } from 'vitest';

import {
  buildShippingPayload,
  getSortedShippingGroupKeys,
  initEmptyShippingGroups,
  validateShippingForm,
} from './shippingFormPayload';
import type { ShippingMeasurements } from '../../types';
import type { ShippingItemConfig } from './shippingMeasurementUtils';

const items: ShippingItemConfig[] = [
  { label: '外徑', key: '外徑', type: 'minmax' },
  { label: '硬度', key: '硬度', type: 'single' },
];

describe('shippingFormPayload', () => {
  it('建立指定組數的空白量測資料', () => {
    const groups = initEmptyShippingGroups(2, items);

    expect(Object.keys(groups)).toEqual(['1', '2']);
    expect(groups['1'].外徑).toEqual({ is_ng: false });
    expect(groups['2'].硬度).toEqual({ is_ng: false });
  });

  it('以實際 groups key 排序，避免刪除中間組後漏判剩餘組', () => {
    const keys = getSortedShippingGroupKeys({
      '1': { 外徑: { is_ng: false } },
      '3': { 外徑: { value_min: '4.8', is_ng: true } },
    });

    expect(keys).toEqual(['1', '3']);
  });

  it('驗證必填欄位與量測數字格式', () => {
    const result = validateShippingForm({
      date: '',
      inspectorName: '',
      vendorName: '廠商A',
      material: '',
      spec: '',
      items,
      groups: {
        '1': {
          外徑: { value_min: 'abc', value_max: '10.2', is_ng: false },
          硬度: { value_single: 'HRB', is_ng: false },
        },
      },
    });

    expect(result.validationErrors).toEqual(['請選擇檢驗日期', '請選擇檢驗人員', '請輸入檢驗規格', '請輸入材質']);
    expect(result.fieldErrors).toEqual({
      '1:外徑:value_min': '「外徑第1組最小值」需為有效數字',
      '1:硬度:value_single': '「硬度第1組」需為有效數字',
    });
  });

  it('組出後端需要的出貨檢驗 payload', () => {
    const payload = buildShippingPayload({
      date: '2026-06-20',
      inspectorName: '檢驗員A',
      vendorName: '廠商A',
      material: 'A6061',
      spec: '10',
      orderNo: 'SO-1',
      items,
      groups: {
        '1': {
          外徑: { lower_limit: 9, upper_limit: 11, value_min: '9.8', value_max: '10.2', is_ng: true },
          硬度: { value_single: '', is_ng: false },
        },
      },
    });

    expect(payload).toMatchObject({
      檢驗日期: '2026-06-20',
      檢驗人員姓名: '檢驗員A',
      廠商中文名稱: '廠商A',
      檢驗規格: '10',
      材質: 'A6061',
      訂單號碼: 'SO-1',
      組數: 1,
    });
    expect(payload.measurements).toEqual({
      '1': {
        外徑: {
          lower_limit: 9,
          upper_limit: 11,
          value_min: 9.8,
          value_max: 10.2,
          value_single: null,
          is_ng: true,
        },
        硬度: {
          lower_limit: null,
          upper_limit: null,
          value_min: null,
          value_max: null,
          value_single: null,
          is_ng: false,
        },
      },
    });
  });

  it('組出 payload 時非法量測值轉為 null 且保留 0', () => {
    const payload = buildShippingPayload({
      date: '2026-06-21',
      inspectorName: '檢驗員A',
      vendorName: '廠商A',
      material: 'A6061',
      spec: '10',
      orderNo: '',
      items,
      groups: {
        '1': {
          外徑: { value_min: 'abc', value_max: '0', is_ng: false },
          硬度: { value_single: 'bad', is_ng: false },
        },
      },
    });

    const measurements = payload.measurements as ShippingMeasurements;
    expect(measurements['1'].外徑.value_min).toBeNull();
    expect(measurements['1'].外徑.value_max).toBe(0);
    expect(measurements['1'].硬度.value_single).toBeNull();
  });
});
