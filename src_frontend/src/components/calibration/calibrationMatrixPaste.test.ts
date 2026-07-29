import { describe, expect, it } from 'vitest';

import {
  CalibrationMatrixPasteError,
  parseCalibrationMatrixPaste,
} from './calibrationMatrixPaste';

describe('校正矩陣貼上解析', () => {
  it('保留 Decimal 字串並移除儲存格外圍空白', () => {
    expect(parseCalibrationMatrixPaste(
      ' 10.0010 \t 9.9990 \r\n10.0020\t10.0000\r\n',
      2,
      2,
    )).toEqual([
      ['10.0010', '9.9990'],
      ['10.0020', '10.0000'],
    ]);
  });

  it('維度不符時原子拒絕並回報實際列欄', () => {
    expect(() => parseCalibrationMatrixPaste('1\t2\n3\t4', 3, 1))
      .toThrow(CalibrationMatrixPasteError);
    try {
      parseCalibrationMatrixPaste('1\t2\n3\t4', 3, 1);
    } catch (error) {
      expect(error).toMatchObject({ rows: 2, columns: 2 });
    }
  });

  it('不接受每列欄數不一致', () => {
    expect(() => parseCalibrationMatrixPaste('1\t2\n3', 2, 2))
      .toThrow('貼上資料每列欄數不一致');
  });
});
