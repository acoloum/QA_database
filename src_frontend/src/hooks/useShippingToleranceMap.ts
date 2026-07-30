import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import api from '../services/api';
import type { ShippingInspection, ToleranceItem, ToleranceResult, Vendor } from '../types';
import { parseSpec } from '../utils/parseSpec';

export type ShippingToleranceMap = Record<string, Record<string, { lsl: number; usl: number }> | null>;

const makeComboKey = (material: string, spec: string, vendor: string) => `${material}|||${spec}|||${vendor}`;

const getInspectionCombo = (item: ShippingInspection): string | null => {
  const material = item.材質 ?? item.material;
  const spec = item.檢驗規格 ?? item.spec ?? '';
  const vendor = item.廠商中文名稱 ?? item.vendor_name ?? '';
  if (!material) return null;
  return makeComboKey(material, spec, vendor);
};

export const resolveToleranceStandardValue = (
  parsedValue: number | undefined,
  configuredValue: number | null,
) => {
  if (parsedValue !== undefined && parsedValue !== 0) return parsedValue;
  if (configuredValue !== null && configuredValue !== 0) return configuredValue;
  return null;
};

export const toToleranceLimits = (result: ToleranceResult, spec: string) => {
  if (!result.success || !result.found) return null;

  const specValues = parseSpec(spec);
  const standards: Record<string, { lsl: number; usl: number }> = {};

  result.tolerances.forEach((t: ToleranceItem) => {
    let lsl: number;
    let usl: number;

    if (t.尺寸下限 !== null && t.尺寸上限 !== null) {
      lsl = t.尺寸下限;
      usl = t.尺寸上限;
    } else if (t.公差下限 !== null && t.公差上限 !== null) {
      const standardValue = resolveToleranceStandardValue(specValues[t.項目], t.標準值);
      if (standardValue === null) return;
      lsl = standardValue + t.公差下限;
      usl = standardValue + t.公差上限;
    } else if (t.尺寸上限 !== null) {
      lsl = 0;
      usl = t.尺寸上限;
    } else if (t.尺寸下限 !== null) {
      lsl = t.尺寸下限;
      usl = Infinity;
    } else {
      return;
    }

    standards[t.項目] = { lsl, usl };
    // 量測明細一律以「硬度」為鍵存放，但公差項目可能寫成「洛氏硬度」；
    // 兩種寫法都要對應到「硬度」鍵，否則該廠商的硬度就查不到界限而漏判。
    // 不可依廠商名稱判斷：公差正名後非安泰廠商同樣會出現「洛氏硬度」。
    if (t.項目 === '洛氏硬度') {
      standards['硬度'] = { lsl, usl };
    }
  });

  return standards;
};

export const useShippingToleranceMap = (inspections: ShippingInspection[]) => {
  const combos = useMemo(
    () => Array.from(new Set(inspections.map(getInspectionCombo).filter(Boolean) as string[])).sort(),
    [inspections],
  );

  return useQuery({
    queryKey: ['shippingToleranceMap', combos],
    queryFn: async () => {
      if (!combos.length) return {};

      const vendorsRes = await api.get<Vendor[]>('/vendors');
      const vendorMap: Record<string, number> = {};
      vendorsRes.data.forEach(v => {
        vendorMap[v.name] = v.id;
      });

      const entries = await Promise.all(combos.map(async combo => {
        const [material, spec, vendorName] = combo.split('|||');
        const vendorId = vendorMap[vendorName] || '';
        const res = await api.get<ToleranceResult>(
          `/tolerance/check?material=${encodeURIComponent(material)}&spec=${encodeURIComponent(spec)}&vendor_id=${vendorId}`,
        );
        return [combo, toToleranceLimits(res.data, spec)] as const;
      }));

      return Object.fromEntries(entries) as ShippingToleranceMap;
    },
    enabled: combos.length > 0,
    staleTime: 5 * 60 * 1000,
  });
};
