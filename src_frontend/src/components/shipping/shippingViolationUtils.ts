import type { ShippingInspection } from '../../types';
import type { ShippingToleranceMap } from '../../hooks/useShippingToleranceMap';
import { ZERO_AS_UNMEASURED_ITEMS, isMeasurementOutOfTolerance } from './shippingMeasurementNumber';

const MINMAX_ITEMS = new Set(['外徑', '內徑', '厚度']);
const ALL_ITEMS = new Set(['外徑', '內徑', '真圓度', '厚度', '同心度', '長度', '硬度', '真直度', '韋伯氏硬度']);

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
            for (const [measKey, measItem] of Object.entries(groupData)) {
                // 分段複合鍵(如 外徑@中段)以基礎項目名比對公差
                const itemName = measKey.split('@')[0];
                if (!ALL_ITEMS.has(itemName) || !measItem) continue;
                const tol = std[itemName];
                if (!tol) continue;

                const zeroUnmeasured = ZERO_AS_UNMEASURED_ITEMS.has(itemName);
                if (MINMAX_ITEMS.has(itemName)) {
                    if (isMeasurementOutOfTolerance(measItem.value_min, tol, zeroUnmeasured)) {
                        return { hasViolation: true, found: true };
                    }
                    if (isMeasurementOutOfTolerance(measItem.value_max, tol, zeroUnmeasured)) {
                        return { hasViolation: true, found: true };
                    }
                } else {
                    if (isMeasurementOutOfTolerance(measItem.value_single, tol, zeroUnmeasured)) {
                        return { hasViolation: true, found: true };
                    }
                }
            }
        }
    }

    return { hasViolation: false, found: true };
};
