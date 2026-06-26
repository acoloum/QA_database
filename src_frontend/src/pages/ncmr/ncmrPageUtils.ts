export const formatNcmrQuantity = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '';
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.floor(parsed).toString() : '';
};

export const escapeHtml = (value: unknown) => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');

type NcmrPrintDetail = Record<string, unknown>;

const field = (detail: NcmrPrintDetail, key: string) => escapeHtml(detail[key]);

const firstField = (detail: NcmrPrintDetail, keys: string[]) => {
  const value = keys.map(key => detail[key]).find(item => item !== null && item !== undefined && item !== '');
  return escapeHtml(value);
};

export const buildNcmrPrintHtml = (detail: NcmrPrintDetail) => {
  const ncmrNo = firstField(detail, ['NCMR單號', '單號']) || (
    detail.識別碼 ? escapeHtml(`NCMR-${detail.識別碼}`) : ''
  );

  return `<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><title>不合格品異常單 - ${ncmrNo}</title>
<style>body{font-family:'Microsoft JhengHei',Arial,sans-serif;padding:20px}table{width:100%;border-collapse:collapse;margin-bottom:20px}th,td{border:1px solid #333;padding:8px;font-size:14px}th{background:#f0f0f0;text-align:center;width:150px}</style>
</head><body>
<div style="text-align:center"><h2>不合格品異常單 (NCMR)</h2></div>
<table>
<tr><th>單號</th><td>${ncmrNo}</td><th>發現日期</th><td>${firstField(detail, ['日期', '發現日期'])}</td></tr>
<tr><th>來源</th><td>${field(detail, '來源')}</td><th>廠商</th><td>${field(detail, '廠商')}</td></tr>
<tr><th>材質</th><td>${field(detail, '材質')}</td><th>規格</th><td>${field(detail, '產品資訊')}</td></tr>
<tr><th>不合格數量</th><td colspan="3">${escapeHtml(formatNcmrQuantity(detail.不合格數量))}</td></tr>
<tr><th>批號/訂單號</th><td colspan="3">${field(detail, '批號')}</td></tr>
<tr><th>不良描述</th><td colspan="3">${field(detail, '不良描述')}</td></tr>
<tr><th>不良原因大類</th><td>${field(detail, '不良原因大類')}</td><th>不良原因細項</th><td>${field(detail, '不良原因細項')}</td></tr>
<tr><th>發現人員</th><td>${field(detail, '發現人員姓名')}</td><th>判定結果</th><td>${field(detail, '判定結果')}</td></tr>
<tr><th>狀態</th><td>${field(detail, '狀態')}</td><th>建立日期</th><td>${firstField(detail, ['建立日期', '日期'])}</td></tr>
</table>
<div style="text-align:center;margin-top:20px">
<button onclick="window.print()" style="padding:10px 20px;font-size:16px;cursor:pointer">列印</button>
<button onclick="window.close()" style="padding:10px 20px;font-size:16px;cursor:pointer;margin-left:10px">關閉</button>
</div></body></html>`;
};

export const buildReworkFromNcmrUrl = (id: number, no: string | number | null | undefined) => {
  const params = new URLSearchParams({
    ncmr_id: String(id),
    ncmr_no: String(no || id),
  });
  return `/rework?${params.toString()}`;
};
