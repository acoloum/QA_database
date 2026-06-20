import type { ShippingInspection } from '../../types';
import type { ShippingToleranceMap } from '../../hooks/useShippingToleranceMap';

const MINMAX_ITEMS = new Set(['外徑', '內徑', '厚度']);
const ALL_ITEMS = ['外徑', '內徑', '真圓度', '厚度', '同心度', '長度', '硬度', '真直度', '韋伯氏硬度'];

export interface ShippingViolationResult {
    found: boolean;
    hasViolation: boolean;
}

const getToleranceKey = (item: ShippingInspection) => {
    const material = item.材質 ?? item.material;
    const spec = item.檢驗規格 ?? item.spec ?? '';
    const vendor = item.廠商中文名稱 ?? item.vendor_name ?? '';
    return `${material ?? ''}|||${spec}|||${vendor}`;
};

export const evaluateShippingViolation = (
    item: ShippingInspection,
    tolerances: ShippingToleranceMap,
): ShippingViolationResult => {
    const std = tolerances[getToleranceKey(item)];
    if (!std) return { hasViolation: false, found: false };

    if (item.measurements && Object.keys(item.measurements).length > 0) {
        for (const groupData of Object.values(item.measurements)) {
            for (const itemName of ALL_ITEMS) {
                const tol = std[itemName];
                if (!tol) continue;
                const measItem = groupData[itemName];
                if (!measItem) continue;

                if (MINMAX_ITEMS.has(itemName)) {
                    const minValue = measItem.value_min != null ? Number(measItem.value_min) : NaN;
                    const maxValue = measItem.value_max != null ? Number(measItem.value_max) : NaN;
                    if (!Number.isNaN(minValue) && (minValue < tol.lsl || minValue > tol.usl)) {
                        return { hasViolation: true, found: true };
                    }
                    if (!Number.isNaN(maxValue) && (maxValue < tol.lsl || maxValue > tol.usl)) {
                        return { hasViolation: true, found: true };
                    }
                } else {
                    const value = measItem.value_single != null ? Number(measItem.value_single) : NaN;
                    if (!Number.isNaN(value) && (value < tol.lsl || value > tol.usl)) {
                        return { hasViolation: true, found: true };
                    }
                }
            }
        }
    }

    return { hasViolation: false, found: true };
};
