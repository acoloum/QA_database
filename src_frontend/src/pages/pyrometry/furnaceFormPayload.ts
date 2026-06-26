import type { Furnace } from '../../types';

type FurnaceIntegerField = 'TUS點數' | 'SAT點數' | 'TUS頻率_月' | 'SAT頻率_月';

export type FurnaceFormState = Omit<Partial<Furnace>, FurnaceIntegerField> & {
  [key in FurnaceIntegerField]?: number | string | null;
};

const text = (value: unknown) => String(value ?? '').trim();

const positiveInteger = (value: unknown, label: string, fallback: number) => {
  const parsed = Number(value ?? fallback);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${label}需為正整數`);
  }
  return parsed;
};

export const buildFurnacePayload = (form: FurnaceFormState): Partial<Furnace> => {
  const code = text(form.爐號);
  const name = text(form.名稱);
  if (!code) throw new Error('爐號為必填');
  if (!name) throw new Error('名稱為必填');

  return {
    爐號: code,
    名稱: name,
    製程類型: text(form.製程類型),
    TUS點數: positiveInteger(form.TUS點數, 'TUS點數', 12),
    SAT點數: positiveInteger(form.SAT點數, 'SAT點數', 2),
    TUS頻率_月: positiveInteger(form.TUS頻率_月, 'TUS頻率(月)', 3),
    SAT頻率_月: positiveInteger(form.SAT頻率_月, 'SAT頻率(月)', 3),
    TUS允許公差: text(form.TUS允許公差),
    SAT允許誤差: text(form.SAT允許誤差),
    有效加熱區尺寸: text(form.有效加熱區尺寸),
    儀器型式: text(form.儀器型式),
    CQI9等級: text(form.CQI9等級),
    啟用狀態: form.啟用狀態 ?? true,
    備註: text(form.備註),
  };
};
