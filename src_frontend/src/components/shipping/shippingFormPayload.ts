import type { ShippingCreateInput, ShippingMeasurementItem, ShippingMeasurements } from '../../types';
import type { ShippingGroupMeasurements, ShippingItemConfig } from './shippingMeasurementUtils';

export const emptyShippingGroup = (items: ShippingItemConfig[]): ShippingGroupMeasurements =>
  Object.fromEntries(items.map(item => [item.key, { is_ng: false }]));

export const initEmptyShippingGroups = (
  count: number,
  items: ShippingItemConfig[],
): Record<string, ShippingGroupMeasurements> =>
  Object.fromEntries(
    Array.from({ length: count }, (_, index) => [String(index + 1), emptyShippingGroup(items)]),
  );

interface ShippingFormValues {
  date: string;
  inspectorName: string;
  vendorName: string;
  material: string;
  spec: string;
  items: ShippingItemConfig[];
  groups: Record<string, ShippingGroupMeasurements>;
}

export const validateShippingForm = ({
  date,
  inspectorName,
  vendorName,
  material,
  spec,
  items,
  groups,
}: ShippingFormValues) => {
  const validationErrors: string[] = [];
  if (!date) validationErrors.push('請選擇檢驗日期');
  if (!inspectorName) validationErrors.push('請選擇檢驗人員');
  if (!vendorName) validationErrors.push('請選擇廠商');
  if (!spec) validationErrors.push('請輸入檢驗規格');
  if (!material) validationErrors.push('請輸入材質');

  const fieldErrors: Record<string, string> = {};
  const numPattern = /^[+-]?\d+(\.\d+)?$/;
  Object.entries(groups).forEach(([groupKey, groupData]) => {
    items.forEach(item => {
      const measItem = groupData[item.key] ?? {};
      if (item.type === 'minmax') {
        const minValue = measItem.value_min;
        const maxValue = measItem.value_max;
        if (minValue != null && !numPattern.test(String(minValue))) {
          fieldErrors[`${groupKey}:${item.key}:value_min`] = `「${item.label}第${groupKey}組最小值」需為有效數字`;
        }
        if (maxValue != null && !numPattern.test(String(maxValue))) {
          fieldErrors[`${groupKey}:${item.key}:value_max`] = `「${item.label}第${groupKey}組最大值」需為有效數字`;
        }
      } else {
        const value = measItem.value_single;
        if (value != null && !numPattern.test(String(value))) {
          fieldErrors[`${groupKey}:${item.key}:value_single`] = `「${item.label}第${groupKey}組」需為有效數字`;
        }
      }
    });
  });

  return { validationErrors, fieldErrors };
};

interface BuildShippingPayloadParams extends ShippingFormValues {
  orderNo: string;
}

const toNumberOrNull = (value: number | string | null | undefined) =>
  value != null && value !== '' ? Number(value) : null;

export const buildShippingPayload = ({
  date,
  inspectorName,
  vendorName,
  material,
  spec,
  orderNo,
  items,
  groups,
}: BuildShippingPayloadParams): ShippingCreateInput => {
  const measurements: ShippingMeasurements = {};

  Object.entries(groups).forEach(([groupKey, groupData]) => {
    const groupOutput: Record<string, ShippingMeasurementItem> = {};
    items.forEach(item => {
      const measurement = groupData[item.key] ?? {};
      groupOutput[item.key] = {
        lower_limit: measurement.lower_limit ?? null,
        upper_limit: measurement.upper_limit ?? null,
        value_min: item.type === 'minmax' ? toNumberOrNull(measurement.value_min) : null,
        value_max: item.type === 'minmax' ? toNumberOrNull(measurement.value_max) : null,
        value_single: item.type === 'single' ? toNumberOrNull(measurement.value_single) : null,
        is_ng: measurement.is_ng ?? false,
      };
    });
    measurements[groupKey] = groupOutput;
  });

  return {
    檢驗日期: date,
    檢驗人員姓名: inspectorName,
    廠商中文名稱: vendorName,
    檢驗規格: spec,
    材質: material,
    訂單號碼: orderNo,
    組數: Object.keys(groups).length,
    measurements,
  };
};
