/**
 * 查詢參數工具。
 *
 * 刻意與 services/api.ts 分開：那個模組匯出的是 axios 實例，
 * 測試普遍會整個 mock 掉；純函式放在那裡會一併被 mock 成 undefined。
 */

/**
 * 過濾掉 undefined / null / 空字串後的查詢參數，供 axios 的 `params` 使用。
 *
 * axios 預設只會略過 undefined，空字串仍會送出 `?vendor=`；
 * 這與各 hook 原本手寫 `if (value) append(...)` 的語意不符，故統一在此收斂。
 * `false` 與 `0` 是有效值，必須保留。
 */
export const compactParams = <T extends object>(params: T): Partial<T> => (
    Object.fromEntries(
        Object.entries(params).filter(([, value]) => (
            value !== undefined && value !== null && value !== ''
        )),
    ) as Partial<T>
);
