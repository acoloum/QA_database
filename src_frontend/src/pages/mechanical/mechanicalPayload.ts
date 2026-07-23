import type {
  MechItem,
  MechLocation,
  MechanicalMeasurement,
  MechanicalTraceNumber,
} from '../../types';

export const JUDGED_ITEMS: MechItem[] = ['硬度', '抗拉強度', '降伏強度', '伸長率'];
export const ALL_ITEMS: MechItem[] = ['硬度', '抗拉強度', '降伏強度', '伸長率', 'EC值'];
export const LOCATIONS: MechLocation[] = ['爐門', '爐頂'];
export const SAMPLES = [1, 2] as const;

// grid[item][location][sampleNo] = 字串輸入值
export type MechGrid = Record<MechItem, Record<MechLocation, Record<number, string>>>;

export function emptyGrid(): MechGrid {
  const grid = {} as MechGrid;
  for (const item of ALL_ITEMS) {
    grid[item] = { 爐門: {}, 爐頂: {} } as Record<MechLocation, Record<number, string>>;
    for (const loc of LOCATIONS) {
      for (const s of SAMPLES) grid[item][loc][s] = '';
    }
  }
  return grid;
}

export function buildMeasurements(grid: MechGrid): MechanicalMeasurement[] {
  const out: MechanicalMeasurement[] = [];
  for (const item of ALL_ITEMS) {
    for (const loc of LOCATIONS) {
      for (const s of SAMPLES) {
        const raw = grid[item]?.[loc]?.[s];
        const trimmed = raw?.trim();
        if (trimmed) {
          const num = Number(trimmed);
          // 非數值（如手誤打字）視同空白，不輸出該格
          if (Number.isFinite(num)) {
            out.push({
              量測項目: item,
              測量位置: loc,
              取樣序: s,
              量測值: num,
            });
          }
        }
      }
    }
  }
  return out;
}

export function hydrateGrid(measurements: MechanicalMeasurement[]): MechGrid {
  const grid = emptyGrid();
  for (const m of measurements) {
    if (grid[m.量測項目]?.[m.測量位置] && m.量測值 !== null && m.量測值 !== undefined) {
      grid[m.量測項目][m.測量位置][m.取樣序] = String(m.量測值);
    }
  }
  return grid;
}

export const emptyTraceNumber = (sequence: number): MechanicalTraceNumber => ({
  序號: sequence,
  編號: '',
});

export function buildTraceNumbers(
  values: MechanicalTraceNumber[],
): MechanicalTraceNumber[] {
  return values
    .map((value) => value.編號.trim())
    .filter(Boolean)
    .map((編號, index) => ({ 序號: index + 1, 編號 }));
}

export function hydrateTraceNumbers(
  values: MechanicalTraceNumber[],
): MechanicalTraceNumber[] {
  const hydrated = [...values]
    .sort((left, right) => left.序號 - right.序號)
    .map((value, index) => ({ 序號: index + 1, 編號: value.編號 }));
  return hydrated.length > 0 ? hydrated : [emptyTraceNumber(1)];
}

export function duplicateTraceNumberIndexes(
  values: MechanicalTraceNumber[],
): Set<number> {
  const byNumber = new Map<string, number[]>();
  values.forEach((value, index) => {
    const number = value.編號.trim();
    if (!number) return;
    byNumber.set(number, [...(byNumber.get(number) ?? []), index]);
  });
  return new Set(
    [...byNumber.values()]
      .filter((indexes) => indexes.length > 1)
      .flat(),
  );
}

export function removeTraceNumber(
  values: MechanicalTraceNumber[],
  removeIndex: number,
): MechanicalTraceNumber[] {
  const remaining = values
    .filter((_, index) => index !== removeIndex)
    .map((value, index) => ({ ...value, 序號: index + 1 }));
  return remaining.length > 0 ? remaining : [emptyTraceNumber(1)];
}
