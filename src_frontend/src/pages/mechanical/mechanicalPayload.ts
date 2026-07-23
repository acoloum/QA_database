import type { MechItem, MechLocation, MechanicalMeasurement } from '../../types';

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
        if (raw !== undefined && raw !== '') {
          const num = Number(raw);
          out.push({
            量測項目: item,
            測量位置: loc,
            取樣序: s,
            量測值: Number.isFinite(num) ? num : null,
          });
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
