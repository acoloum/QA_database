import type { ShippingGroupMeasurements, ShippingItemConfig } from './shippingMeasurementUtils';

export const SEGMENT_POSITIONS = ['前段', '中段', '後段'] as const;
export type SegmentPosition = (typeof SEGMENT_POSITIONS)[number];

const SEGMENT_SHORT_LABELS: Record<SegmentPosition, string> = {
  前段: '前',
  中段: '中',
  後段: '後',
};

/** 組出複合鍵「基鍵@位置」(與後端 shipping_measurement_keys 對應) */
export const buildSegmentKey = (baseKey: string, position: SegmentPosition) => `${baseKey}@${position}`;

/** 將啟用分段的項目展開為前/中/後三列;其餘項目原樣保留 */
export const expandSegmentedItems = (
  items: ShippingItemConfig[],
  segmentedKeys: Set<string>,
): ShippingItemConfig[] =>
  items.flatMap(item => {
    if (!item.segmentable || !segmentedKeys.has(item.key)) return [item];
    return SEGMENT_POSITIONS.map(position => ({
      ...item,
      key: buildSegmentKey(item.key, position),
      label: `${item.label}(${SEGMENT_SHORT_LABELS[position]})`,
      toleranceKey: item.toleranceKey ?? item.key,
      baseKey: item.key,
      position,
    }));
  });

/** 從已載入的量測資料偵測哪些可分段項目已啟用分段(存在「基鍵@」開頭的鍵) */
export const detectSegmentedKeys = (
  measurements: Record<string, ShippingGroupMeasurements>,
  items: ShippingItemConfig[],
): Set<string> => {
  const segmentableKeys = new Set(items.filter(i => i.segmentable).map(i => i.key));
  const found = new Set<string>();
  for (const groupData of Object.values(measurements ?? {})) {
    for (const key of Object.keys(groupData ?? {})) {
      const [base, position] = key.split('@');
      if (position && segmentableKeys.has(base)) found.add(base);
    }
  }
  return found;
};

/** 分段的中段/後段已有量測值時回傳 true(關閉分段前需使用者確認) */
export const hasMidRearSegmentValues = (
  groups: Record<string, ShippingGroupMeasurements>,
  baseKey: string,
): boolean =>
  Object.values(groups).some(groupData =>
    (['中段', '後段'] as const).some(pos => {
      const meas = groupData[buildSegmentKey(baseKey, pos)];
      return meas != null && (meas.value_min != null || meas.value_max != null);
    }),
  );

/** 切換分段時搬移量測值:開啟時單段值搬到前段;關閉時只保留前段值 */
export const remapGroupsOnSegmentToggle = (
  groups: Record<string, ShippingGroupMeasurements>,
  baseKey: string,
  enable: boolean,
): Record<string, ShippingGroupMeasurements> =>
  Object.fromEntries(
    Object.entries(groups).map(([gKey, groupData]) => {
      const next = { ...groupData };
      if (enable) {
        const single = next[baseKey];
        delete next[baseKey];
        next[buildSegmentKey(baseKey, '前段')] = single ?? { is_ng: false };
        next[buildSegmentKey(baseKey, '中段')] = { is_ng: false };
        next[buildSegmentKey(baseKey, '後段')] = { is_ng: false };
      } else {
        const front = next[buildSegmentKey(baseKey, '前段')];
        for (const pos of SEGMENT_POSITIONS) delete next[buildSegmentKey(baseKey, pos)];
        next[baseKey] = front ?? { is_ng: false };
      }
      return [gKey, next];
    }),
  );
