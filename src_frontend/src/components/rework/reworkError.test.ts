import { describe, expect, it } from 'vitest';
import { getReworkErrorMessage } from './reworkError';

describe('getReworkErrorMessage', () => {
  it('優先顯示後端 error 欄位', () => {
    expect(getReworkErrorMessage({
      response: { data: { error: '目前狀態不可新增執行記錄' } },
    }, '新增失敗')).toBe('目前狀態不可新增執行記錄');
  });

  it('支援後端 message 欄位並在無 API 訊息時回傳預設文案', () => {
    expect(getReworkErrorMessage({
      response: { data: { message: '缺少必要欄位' } },
    }, '送出失敗')).toBe('缺少必要欄位');

    expect(getReworkErrorMessage(new Error('network'), '送出失敗')).toBe('送出失敗');
  });
});
