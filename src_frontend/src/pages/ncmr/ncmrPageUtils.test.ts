import { describe, expect, it } from 'vitest';

import {
  buildNcmrPrintHtml,
  buildReworkFromNcmrUrl,
  escapeHtml,
  formatNcmrQuantity,
} from './ncmrPageUtils';

describe('ncmrPageUtils', () => {
  it('格式化 NCMR 數量時保留 0', () => {
    expect(formatNcmrQuantity(0)).toBe('0');
    expect(formatNcmrQuantity('0')).toBe('0');
  });

  it('格式化 NCMR 數量時空值回傳空字串', () => {
    expect(formatNcmrQuantity(null)).toBe('');
    expect(formatNcmrQuantity(undefined)).toBe('');
    expect(formatNcmrQuantity('')).toBe('');
  });

  it('轉義列印 HTML 的特殊字元', () => {
    expect(escapeHtml(`<img src=x onerror="alert('x')">&`)).toBe(
      '&lt;img src=x onerror=&quot;alert(&#39;x&#39;)&quot;&gt;&amp;',
    );
  });

  it('建立 NCMR 列印 HTML 時會轉義動態欄位', () => {
    const html = buildNcmrPrintHtml({
      識別碼: 7,
      NCMR單號: 'NCMR<&>"\'',
      廠商: '<script>alert(1)</script>',
      不良描述: '<img src=x onerror="alert(1)">',
      不合格數量: '2.9',
    });

    expect(html).toContain('NCMR&lt;&amp;&gt;&quot;&#39;');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).not.toContain('<img src=x');
    expect(html).toContain('<td colspan="3">2</td>');
  });

  it('建立轉重工 URL 時會正確編碼 NCMR 單號', () => {
    expect(buildReworkFromNcmrUrl(12, 'NCMR A&B#1')).toBe('/rework?ncmr_id=12&ncmr_no=NCMR+A%26B%231');
    expect(buildReworkFromNcmrUrl(12, '')).toBe('/rework?ncmr_id=12&ncmr_no=12');
  });
});
