import type { ShippingItemConfig } from './shippingMeasurementUtils';

export const ANTAI_VENDOR_NAME = '安泰';

export const BASE_SHIPPING_ITEMS: ShippingItemConfig[] = [
  { label: '外徑', key: '外徑', type: 'minmax' },
  { label: '內徑', key: '內徑', type: 'minmax' },
  { label: '厚度', key: '厚度', type: 'minmax' },
  { label: '同心度', key: '同心度', type: 'single' },
  { label: '長度', key: '長度', type: 'single' },
  { label: '硬度', key: '硬度', type: 'single' },
  { label: '真直度', key: '真直度', type: 'single' },
];

const ROUNDNESS_ITEM: ShippingItemConfig = { label: '真圓度', key: '真圓度', type: 'single' };
const VICKERS_HARDNESS_ITEM: ShippingItemConfig = { label: '韋伯氏硬度(HW)', key: '韋伯氏硬度', type: 'single' };

export const getShippingInspectionItems = (vendorName: string): ShippingItemConfig[] => {
  if (!vendorName.includes(ANTAI_VENDOR_NAME)) return BASE_SHIPPING_ITEMS;

  const items = [...BASE_SHIPPING_ITEMS];
  items.splice(2, 0, ROUNDNESS_ITEM);
  const hardnessIndex = items.findIndex(item => item.key === '硬度');
  if (hardnessIndex !== -1) {
    items[hardnessIndex] = { ...items[hardnessIndex], label: '洛氏硬度(HRB)', toleranceKey: '洛氏硬度' };
    items.splice(hardnessIndex + 1, 0, VICKERS_HARDNESS_ITEM);
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
