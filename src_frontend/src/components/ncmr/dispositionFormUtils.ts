const parseDispositionNumber = (value: string) => {
  const text = value.trim();
  if (text === '') return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
};

export const parseDispositionNumberInput = (value: string) =>
  parseDispositionNumber(value) ?? 0;

export const parseNullableDispositionNumberInput = (value: string) =>
  parseDispositionNumber(value);
