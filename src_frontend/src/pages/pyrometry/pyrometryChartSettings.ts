export const parsePyrometryChartNumber = (value: string, fallback: number) => {
  const text = value.trim();
  if (text === '') return fallback;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const resolvePyrometryChartSettings = ({
  setpoint,
  tolerance,
}: {
  setpoint: string;
  tolerance: string;
}) => ({
  setpointValue: parsePyrometryChartNumber(setpoint, 180),
  toleranceValue: parsePyrometryChartNumber(tolerance, 10),
});
