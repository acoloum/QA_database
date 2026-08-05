import type {
  MechItem,
  MechLocation,
  MechWaivableItem,
  MechanicalMeasurement,
  MechanicalTraceNumber,
  MechanicalWaivedItem,
} from '../../types';

/** 必測的力學特性：納入完成判定，且可標記免測。 */
export const JUDGED_ITEMS: MechWaivableItem[] = ['硬度', '抗拉強度', '降伏強度', '伸長率'];

/** 依公差檔決定是否顯示的選填項目；不納入完成判定，也不可標記免測。
 *
 * 韋伯氏硬度（HW）與洛氏硬度是兩種不同標度，不可互為別名；真直度受上限管制。
 * 兩者都只有部分廠商／規格有登錄公差，故欄位依公差檔動態顯示。
 */
export const SPEC_DRIVEN_ITEMS: MechItem[] = ['韋伯氏硬度', '真直度'];

export const ALL_ITEMS: MechItem[] = [...JUDGED_ITEMS, ...SPEC_DRIVEN_ITEMS, 'EC值'];
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

/** 規格界限查表；一個項目只會出現在受管制的那一邊。 */
export interface SpecLimits {
  lower: Record<string, number>;
  upper: Record<string, number>;
}

/** 取某項目的界限；回傳 [下限, 上限]，未受管制的那一邊為 undefined。 */
export const itemLimits = (
  limits: SpecLimits | undefined,
  item: MechItem,
): [number | undefined, number | undefined] => [limits?.lower[item], limits?.upper[item]];

/**
 * 決定要顯示哪些依公差驅動的項目（韋伯氏硬度／真直度）。
 *
 * 公差檔有登錄該項目就顯示欄位。另有一條安全規則：**該筆已填過數值的項目
 * 一律不隱藏**——公差改版或查無公差時把欄位藏起來，會讓既有數值變成使用者
 * 看不到也改不掉的孤兒（沿用出貨檢驗表單的同一條規則）。
 */
export function visibleSpecDrivenItems(
  limits: SpecLimits | undefined,
  presentItems?: ReadonlySet<string>,
): MechItem[] {
  return SPEC_DRIVEN_ITEMS.filter((item) => {
    const [lower, upper] = itemLimits(limits, item);
    return lower !== undefined || upper !== undefined || !!presentItems?.has(item);
  });
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

// 免測狀態：四項力學特性各自可標記免測並填原因
export type MechWaivedState = Record<MechItem, { waived: boolean; reason: string }>;

export function emptyWaived(): MechWaivedState {
  const state = {} as MechWaivedState;
  for (const item of ALL_ITEMS) {
    state[item] = { waived: false, reason: '' };
  }
  return state;
}

export function buildWaivedItems(state: MechWaivedState): MechanicalWaivedItem[] {
  return JUDGED_ITEMS
    .filter((item) => state[item]?.waived && state[item].reason.trim())
    .map((item) => ({ 項目: item, 原因: state[item].reason.trim() }));
}

export function hydrateWaivedItems(items: MechanicalWaivedItem[]): MechWaivedState {
  const state = emptyWaived();
  for (const waived of items) {
    if (state[waived.項目]) {
      state[waived.項目] = { waived: true, reason: waived.原因 };
    }
  }
  return state;
}

// 已勾選免測卻沒填原因的項目（供存檔前擋下並提示）
export function waivedItemsMissingReason(state: MechWaivedState): MechItem[] {
  return JUDGED_ITEMS.filter((item) => state[item]?.waived && !state[item].reason.trim());
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
