import type { ShippingMeasurementItem, ToleranceResult } from '../../types';
import { parseSpec } from '../../utils/parseSpec';
import { isMeasurementOutOfTolerance } from './shippingMeasurementNumber';

export interface ShippingItemConfig {
  label: string;
  key: string;
  type: 'minmax' | 'single';
  toleranceKey?: string;
}

export type ShippingGroupMeasurements = Record<string, Partial<ShippingMeasurementItem>>;

interface CalculateShippingViolationsParams {
  items: ShippingItemConfig[];
  groupKeys: string[];
  groups: Record<string, ShippingGroupMeasurements>;
  tolerance: ToleranceResult | null;
  spec: string;
}

const resolveStandardValue = (
  parsedValue: number | undefined,
  configuredValue: number | null,
) => {
  if (parsedValue !== undefined && parsedValue !== 0) return parsedValue;
  if (configuredValue !== null && configuredValue !== 0) return configuredValue;
  return null;
};

export const calculateShippingViolations = ({
  items,
  groupKeys,
  groups,
  tolerance,
  spec,
}: CalculateShippingViolationsParams) => {
  if (!tolerance) return {};

  const violations: Record<string, boolean> = {};
  const specValues = parseSpec(spec);

  items.forEach(item => {
    const toleranceItemKey = item.toleranceKey ?? item.key;
    const tolItem = tolerance.tolerances.find(t => t.項目 === toleranceItemKey);
    if (!tolItem) return;

    let lsl = -Infinity;
    let usl = Infinity;

    if (tolItem.尺寸下限 !== null && tolItem.尺寸上限 !== null) {
      lsl = tolItem.尺寸下限;
      usl = tolItem.尺寸上限;
    } else if (tolItem.公差下限 !== null && tolItem.公差上限 !== null) {
      const standardValue = resolveStandardValue(
        specValues[toleranceItemKey] ?? specValues[item.key],
        tolItem.標準值,
      );
      if (standardValue === null) return;
      lsl = standardValue + (tolItem.公差下限 ?? 0);
      usl = standardValue + (tolItem.公差上限 ?? 0);
    } else if (tolItem.尺寸上限 !== null) {
      lsl = 0;
      usl = tolItem.尺寸上限;
    } else if (tolItem.尺寸下限 !== null) {
      lsl = tolItem.尺寸下限 ?? -Infinity;
      usl = Infinity;
    } else {
      return;
    }

    groupKeys.forEach(gKey => {
      const measItem = groups[gKey]?.[item.key];
      if (!measItem) return;

      if (item.type === 'minmax') {
        const minKey = `${gKey}:${item.key}:value_min`;
        const maxKey = `${gKey}:${item.key}:value_max`;
        if (isMeasurementOutOfTolerance(measItem.value_min, { lsl, usl })) violations[minKey] = true;
        if (isMeasurementOutOfTolerance(measItem.value_max, { lsl, usl })) violations[maxKey] = true;
      } else {
        const key = `${gKey}:${item.key}:value_single`;
        if (isMeasurementOutOfTolerance(measItem.value_single, { lsl, usl })) violations[key] = true;
      }
    });
  });

  return violations;
};
