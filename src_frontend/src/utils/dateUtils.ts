const pad2 = (value: number) => String(value).padStart(2, '0');

const parseDateText = (value: string) => {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day));
};

const formatWithTimeZone = (date: Date, timeZone?: string) => {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
};

export const formatLocalDate = (date = new Date(), timeZone?: string) =>
  timeZone
    ? formatWithTimeZone(date, timeZone)
    : `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;

export const formatLocalMonth = (date = new Date(), timeZone?: string) =>
  formatLocalDate(date, timeZone).slice(0, 7);

export const addLocalDays = (dateText: string, days: number) => {
  const date = parseDateText(dateText);
  if (!date) return '';
  date.setDate(date.getDate() + days);
  return formatLocalDate(date);
};
