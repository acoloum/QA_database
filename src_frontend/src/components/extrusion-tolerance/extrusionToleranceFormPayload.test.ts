import { describe, expect, it } from 'vitest';

import { buildExtrusionTolerancePayload, createExtrusionToleranceRow } from './extrusionToleranceFormPayload';

describe('extrusionToleranceFormPayload', () => {
  it('建立擠型公差 payload 並保留 0 數值', () => {
    const payload = buildExtrusionTolerancePayload({
      material: '6061',
      spec: '85*2.8',
      vendor: 'A廠',
      note: '量產',
      createdAt: '2026-06-21',
      rows: [{
        測量項目: '外徑',
        公差下限: '0',
        公差上限: '0.2',
        標準值: '85',
        特性重要度: '主要',
      }],
    });

    expect(payload).toEqual({
      材質: '6061',
      規格: '85*2.8',
      廠商: 'A廠',
      備註: '量產',
      建立日期: '2026-06-21',
      details: [{
        測量項目: '外徑',
        公差下限: 0,
        公差上限: 0.2,
        標準值: 85,
        單位: 'mm',
        特性重要度: '主要',
      }],
    });
  });

  it('空白與非法數值轉為 null', () => {
    const payload = buildExtrusionTolerancePayload({
      material: '6061',
      spec: '',
      vendor: '',
      note: '',
      createdAt: '2026-06-21',
      rows: [{
        測量項目: '厚度',
        公差下限: '',
        公差上限: 'abc',
        標準值: '',
        特性重要度: '其他',
      }],
    });

    expect(payload).toMatchObject({
      規格: null,
      廠商: null,
      備註: null,
      details: [{
        測量項目: '厚度',
        公差下限: null,
        公差上限: null,
        標準值: null,
        單位: 'mm',
      }],
    });
  });

  it('建立預設明細列', () => {
    expect(createExtrusionToleranceRow()).toEqual({
      測量項目: '外徑',
      公差下限: '',
      公差上限: '',
      標準值: '',
      特性重要度: '其他',
    });
  });
});
