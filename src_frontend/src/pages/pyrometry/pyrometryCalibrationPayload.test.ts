import { describe, expect, it } from 'vitest';

import {
  buildRecorderPayload,
  buildThermocouplePayload,
  cellKey,
  validateRecorderGrid,
  validateThermocoupleRows,
} from './pyrometryCalibrationPayload';

describe('pyrometryCalibrationPayload', () => {
  it('建立熱電偶校正 payload 並略過未填完整列', () => {
    const payload = buildThermocouplePayload(
      { 編號: 'TC-01', 型式: 'TYPE K', 校正日期: '2026-06-20', 到期日: '', 啟用狀態: true, 備註: '' },
      [
        { 標準溫度: '100', 器差值: '-0.2' },
        { 標準溫度: '200', 器差值: '' },
      ],
    );

    expect(payload).toMatchObject({
      編號: 'TC-01',
      校正點: [{ 標準溫度: 100, 器差值: -0.2 }],
    });
  });

  it('驗證熱電偶校正點必須是有效數字', () => {
    expect(validateThermocoupleRows([{ 標準溫度: 'abc', 器差值: '0.1' }])).toEqual({
      '0:標準溫度': '第 1 列標準溫度需為有效數字',
    });
  });

  it('建立記錄器校正 payload 並轉換已填寫格子的數字', () => {
    const payload = buildRecorderPayload(
      { 編號: 'REC-01', 校正日期: '2026-06-20', 到期日: '', 啟用狀態: true, 備註: '' },
      { [cellKey(1, 100)]: '-0.3', [cellKey(2, 200)]: '' },
    );

    expect(payload).toMatchObject({
      編號: 'REC-01',
      校正點: [{ 頻道: 1, 標準溫度: 100, 器差值: -0.3 }],
    });
  });

  it('驗證記錄器格線值必須是有效數字', () => {
    expect(validateRecorderGrid({ [cellKey(1, 100)]: 'bad' })).toEqual({
      [cellKey(1, 100)]: 'CH1 / 100°C 器差值需為有效數字',
    });
  });
});
