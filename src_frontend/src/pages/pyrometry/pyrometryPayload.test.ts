import { describe, expect, it } from 'vitest';

import type { SatPoint, TusPoint } from '../../types';
import { buildPyrometryPayload } from './pyrometryPayload';
import type { ChartData, ItemRow } from './pyrometryFormUtils';

describe('buildPyrometryPayload', () => {
  const reportMeta = { 客戶名稱: '測試客戶', 測試條件: '滿爐' };
  const itemRows: ItemRow[] = [
    { 工件料號: 'P-001', 生產批號: 'B-001', 內外徑尺寸: '40x3', 支數: '10' },
  ];

  it('builds a TUS payload with recorder curve data and report rows', () => {
    const chartData: ChartData = {
      時間: ['08:00', '08:10'],
      數值: { CH1: [180, 181] },
    };
    const tusPoints: TusPoint[] = [
      { 點位: 'TUS-1', 熱電偶編號: '', 頻道: 1, 修正值: '0.2', 最高溫: '181', 最低溫: '180' },
    ];

    const payload = buildPyrometryPayload({
      furnaceId: '7',
      testType: 'TUS',
      testDate: '2026-06-19',
      setpoint: '180',
      tolerance: '10',
      testerId: '3',
      testInstrument: 'REC-01',
      stdInstrument: 'STD-01',
      calDueDate: '',
      note: '備註',
      tusPoints,
      satPoints: [],
      chartData,
      rangeStart: 0,
      rangeEnd: 1,
      satChartData: null,
      satRangeStart: 0,
      satRangeEnd: 0,
      furnaceChartData: null,
      furnaceRangeStart: 0,
      furnaceRangeEnd: 0,
      reportMeta,
      itemRows,
    });

    expect(payload).toEqual({
      爐子ID: 7,
      測試類型: 'TUS',
      測試日期: '2026-06-19',
      設定溫度: '180',
      允許公差: '10',
      測試人員: 3,
      測試儀器編號: 'REC-01',
      標準校正儀器編號: 'STD-01',
      儀器校正到期日: null,
      備註: '備註',
      points: tusPoints,
      曲線資料: {
        時間: ['08:00', '08:10'],
        數值: { CH1: [180, 181] },
        穩定開始: 0,
        穩定結束: 1,
      },
      報告欄位: { ...reportMeta, 料號批次: itemRows },
    });
  });

  it('builds a SAT payload with SAT and furnace curve data', () => {
    const satChartData: ChartData = {
      時間: ['09:00'],
      數值: { CH13: [179.8] },
    };
    const furnaceChartData: ChartData = {
      時間: ['09:00'],
      數值: { F1: [180.1] },
    };
    const satPoints: SatPoint[] = [
      {
        控溫區: 'Zone1',
        頻道: 13,
        修正值: '0.1',
        readings: [{ 控制儀表讀值: '180', 校正測試讀值: '179.8' }],
      },
    ];

    const payload = buildPyrometryPayload({
      furnaceId: '8',
      testType: 'SAT',
      testDate: '2026-06-19',
      setpoint: '180',
      tolerance: '5',
      testerId: '',
      testInstrument: 'SAT-01',
      stdInstrument: 'STD-02',
      calDueDate: '2027-01-01',
      note: '',
      tusPoints: [],
      satPoints,
      chartData: null,
      rangeStart: 0,
      rangeEnd: 0,
      satChartData,
      satRangeStart: 0,
      satRangeEnd: 0,
      furnaceChartData,
      furnaceRangeStart: 0,
      furnaceRangeEnd: 0,
      reportMeta,
      itemRows,
    });

    expect(payload.測試人員).toBeNull();
    expect(payload.points).toBe(satPoints);
    expect(payload.曲線資料).toEqual({
      時間: ['09:00'],
      數值: { CH13: [179.8] },
      穩定開始: 0,
      穩定結束: 0,
      爐體時間: ['09:00'],
      爐體數值: { F1: [180.1] },
      爐體穩定開始: 0,
      爐體穩定結束: 0,
    });
  });

  it('rejects empty or invalid furnace ids before sending payload', () => {
    const build = (furnaceId: string) => () => buildPyrometryPayload({
      furnaceId,
      testType: 'TUS',
      testDate: '2026-06-19',
      setpoint: '180',
      tolerance: '10',
      testerId: '',
      testInstrument: '',
      stdInstrument: '',
      calDueDate: '',
      note: '',
      tusPoints: [],
      satPoints: [],
      chartData: null,
      rangeStart: 0,
      rangeEnd: 0,
      satChartData: null,
      satRangeStart: 0,
      satRangeEnd: 0,
      furnaceChartData: null,
      furnaceRangeStart: 0,
      furnaceRangeEnd: 0,
      reportMeta,
      itemRows,
    });

    expect(build('')).toThrow('請選擇爐子');
    expect(build('0')).toThrow('請選擇爐子');
    expect(build('abc')).toThrow('請選擇爐子');
  });
});
