export const parseCapaOpenId = (searchParams: URLSearchParams) => {
  const raw = searchParams.get('editId') ?? searchParams.get('openId');
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};
