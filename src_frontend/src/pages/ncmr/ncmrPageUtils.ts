export const formatNcmrQuantity = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '';
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.floor(parsed).toString() : '';
};
