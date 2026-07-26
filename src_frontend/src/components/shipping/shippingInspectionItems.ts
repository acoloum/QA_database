import type { ShippingItemConfig } from './shippingMeasurementUtils';

export const ANTAI_VENDOR_NAME = '安泰';

export const BASE_SHIPPING_ITEMS: ShippingItemConfig[] = [
  { label: '外徑', key: '外徑', type: 'minmax', segmentable: true },
  { label: '內徑', key: '內徑', type: 'minmax' },
  { label: '厚度', key: '厚度', type: 'minmax' },
  { label: '同心度', key: '同心度', type: 'single' },
  { label: '長度', key: '長度', type: 'single' },
  { label: '硬度', key: '硬度', type: 'single' },
  { label: '真直度', key: '真直度', type: 'single' },
];

const ROUNDNESS_ITEM: ShippingItemConfig = { label: '真圓度', key: '真圓度', type: 'single' };
const VICKERS_HARDNESS_ITEM: ShippingItemConfig = { label: '韋伯氏硬度(HW)', key: '韋伯氏硬度', type: 'single' };

/** 公差檔用來表示「主硬度」的項目名稱，依優先序排列。
 *
 * 量測明細一律以 `硬度` 為鍵存放（標度只影響顯示與比對目標），但公差主檔的
 * 項目名稱有「洛氏硬度」與未指明標度的「硬度」兩種寫法並存。公差比對是字串
 * 完全相等（見 shippingMeasurementUtils），對不上就整項靜默不判定，因此比對
 * 目標必須依公差檔實際內容決定，不能依廠商硬編碼。
 * 「韋伯氏硬度」是另一種標度（Webster HW），不屬於主硬度。
 */
const PRIMARY_HARDNESS_ITEMS: { toleranceKey: string; label: string }[] = [
  { toleranceKey: '洛氏硬度', label: '洛氏硬度(HRB)' },
  { toleranceKey: '硬度', label: '硬度' },
];

/** 依公差檔實際存在的項目決定主硬度的比對目標與標籤；無從判斷時回傳 null。 */
export const resolvePrimaryHardness = (
  toleranceItems?: string[],
): { toleranceKey: string; label: string } | null => {
  if (!toleranceItems?.length) return null;
  return PRIMARY_HARDNESS_ITEMS.find(
    candidate => toleranceItems.includes(candidate.toleranceKey),
  ) ?? null;
};

const WEBSTER_HARDNESS_KEY = '韋伯氏硬度';

/**
 * 依廠商與（可選的）公差項目清單組出檢驗項目設定。
 *
 * 公差項目清單決定兩件事：主硬度的比對目標與標籤，以及是否顯示韋伯氏硬度欄。
 * 未提供（尚未載入或查無公差）時沿用原本依廠商的預設，避免標籤閃動。
 *
 * 欄位顯示的兩條安全規則：
 *  - 安泰的韋伯欄即使公差未定義也保留：實際有 65 筆紀錄在無韋伯公差的規格上
 *    填了值，公差只該影響判定而不是讓輸入欄位消失。
 *  - presentKeys（該筆已有資料的項目）一律不隱藏，避免既有值被孤立。
 *
 * 當公差只以韋伯標度管制（有韋伯、無洛氏／硬度）時隱藏主硬度欄，
 * 否則留著空欄會誘導檢驗員把韋伯值填進主硬度而重蹈標度混用。
 */
export const getShippingInspectionItems = (
  vendorName: string,
  toleranceItems?: string[],
  presentKeys?: ReadonlySet<string>,
): ShippingItemConfig[] => {
  const isAntai = vendorName.includes(ANTAI_VENDOR_NAME);
  const resolved = resolvePrimaryHardness(toleranceItems);
  const hasWebsterTolerance = !!toleranceItems?.includes(WEBSTER_HARDNESS_KEY);
  const has = (key: string) => !!presentKeys?.has(key);

  const items = [...BASE_SHIPPING_ITEMS];
  if (isAntai) items.splice(2, 0, ROUNDNESS_ITEM);

  const hardnessIndex = items.findIndex(item => item.key === '硬度');
  if (hardnessIndex !== -1) {
    // 韋伯專用規格（有韋伯公差、無可用的主硬度公差）隱藏主硬度欄；已有資料者不動
    const websterOnly = hasWebsterTolerance && resolved === null;
    if (websterOnly && !has('硬度')) {
      items.splice(hardnessIndex, 1);
    } else {
      // 公差未載入時的預設：安泰沿用洛氏硬度，其餘廠商沿用未指明標度的「硬度」
      const fallback = isAntai ? PRIMARY_HARDNESS_ITEMS[0] : PRIMARY_HARDNESS_ITEMS[1];
      const { toleranceKey, label } = resolved ?? fallback;
      items[hardnessIndex] = { ...items[hardnessIndex], label, toleranceKey };
    }
    if (isAntai || hasWebsterTolerance || has(WEBSTER_HARDNESS_KEY)) {
      const insertAt = items.findIndex(item => item.key === '硬度');
      items.splice(insertAt === -1 ? hardnessIndex : insertAt + 1, 0, VICKERS_HARDNESS_ITEM);
    }
  }
  return items;
};

export const getShippingItemInputOffsets = (items: ShippingItemConfig[]) => {
  const itemOffsets = items.reduce((offsets, _, index) => {
    const previousOffset = index > 0 ? offsets[index - 1] : 0;
    const previousCount = index > 0 && items[index - 1].type === 'minmax' ? 2 : index > 0 ? 1 : 0;
    offsets.push(previousOffset + previousCount);
    return offsets;
  }, [] as number[]);
  const lastItem = items[items.length - 1];
  const totalInputsPerGroup = itemOffsets[items.length - 1] + (lastItem.type === 'minmax' ? 2 : 1);
  return { itemOffsets, totalInputsPerGroup };
};
