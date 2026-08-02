/** 把統計輸出攤平成可稽核的路徑／值資料表。 */
export const flattenStatistics = (
  value: unknown, prefix = '',
): Array<{ path: string; value: string }> => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .flatMap(([key, item]) => flattenStatistics(
        item, prefix ? `${prefix}.${key}` : key,
      ));
  }
  if (Array.isArray(value)) {
    if (value.every((item) => typeof item !== 'object' || item === null)) {
      return [{ path: prefix, value: JSON.stringify(value) }];
    }
    return value.flatMap((item, index) => flattenStatistics(
      item, `${prefix}[${index}]`,
    ));
  }
  return [{
    path: prefix,
    value: value == null ? '不可用' : String(value),
  }];
};
