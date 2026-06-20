import { describe, expect, it } from 'vitest';

import { buildPyrometryEditFormState } from './pyrometryFormHydration';

describe('buildPyrometryEditFormState', () => {
  it('將編輯資料轉為爐溫測試表單狀態並相容舊點位格式', () => {
    const state = buildPyrometryEditFormState({
      main: {
        爐子ID: 7,
        測試類型: 'SAT',
        測試日期: '2026-06-20',
        設定溫度: '180',
        允許公差: '5',
        測試人員: 3,
        測試儀器編號: 'REC-01',
        標準校正儀器編號: 'STD-01',
        儀器校正到期日: '2027-01-01',
        備註: '測試備註',
      },
      tus_points: [
        { 點位: 'P1', 熱電偶編號: 'TC-01', 修正值: '0.1', 最高溫: '181', 最低溫: '179' },
      ],
      sat_points: [
        { 控溫區: 'Zone 1', 修正值: '0.2', readings: [] },
      ],
      曲線資料: {
        時間: ['08:00', '08:10'],
        數值: { CH1: [180, 181] },
        穩定開始: 1,
        穩定結束: 1,
        爐體時間: ['08:00'],
        爐體數值: { F1: [180.2] },
        爐體穩定開始: 0,
      },
      報告欄位: {
        客戶名稱: '測試客戶',
        是否急件: true,
        料號批次: [
          { 工件料號: 'P-001', 生產批號: 'B-001', 內外徑尺寸: '40x3', 支數: '10' },
        ],
      },
    });

    expect(state).toMatchObject({
      furnaceId: '7',
      testType: 'SAT',
      testDate: '2026-06-20',
      setpoint: '180',
      tolerance: '5',
      testerId: '3',
      testInstrument: 'REC-01',
      stdInstrument: 'STD-01',
      calDueDate: '2027-01-01',
      note: '測試備註',
      satChartData: { 時間: ['08:00', '08:10'], 數值: { CH1: [180, 181] } },
      satRangeStart: 1,
      satRangeEnd: 1,
      furnaceChartData: { 時間: ['08:00'], 數值: { F1: [180.2] } },
      furnaceRangeStart: 0,
      furnaceRangeEnd: 0,
      reportMeta: { 客戶名稱: '測試客戶', 是否急件: 'true' },
    });
    expect(state.tusPoints[0]).toMatchObject({ 點位: 'TUS-1', 頻道: 1 });
    expect(state.satPoints[0]).toMatchObject({
      控溫區: 'Zone 1',
      頻道: 13,
      readings: [{ 控制儀表讀值: '', 校正測試讀值: '' }],
    });
    expect(state.itemRows).toEqual([
      { 工件料號: 'P-001', 生產批號: 'B-001', 內外徑尺寸: '40x3', 支數: '10' },
    ]);
  });

  it('報告料號批次空白時保留一列空白列', () => {
    const state = buildPyrometryEditFormState({ 報告欄位: {} });

    expect(state.itemRows).toEqual([
      { 工件料號: '', 生產批號: '', 內外徑尺寸: '', 支數: '' },
    ]);
  });
});
