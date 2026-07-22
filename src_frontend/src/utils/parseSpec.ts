/**
 * Parse a spec string into dimensional values.
 * Handles various separator formats: ×, x, X, *
 *
 * 支援兩種規格格式：
 *   三段式 '外徑*厚度或內徑*長度'（如 '62.5*2.3*450'）：第二值以外徑一半為界推斷是厚度或內徑，
 *          再幾何回推另一項。
 *   四段式 '外徑*內徑*厚度*長度'（如 '33*26.5*2.0*244'）：內徑與厚度皆為明列值，直接讀取，
 *          不再幾何回推（避免把明寫的厚度誤算成 (外徑-內徑)/2）。
 */
export const parseSpec = (spec: string): Record<string, number> => {
    if (!spec) return {};
    const parts = spec
        .replace(/[xX×]/g, '*')
        .split('*')
        .map(part => {
            const text = part.trim();
            return /^[+-]?\d+(?:\.\d+)?$/.test(text) ? Number(text) : NaN;
        });
    const result: Record<string, number> = {};

    if (parts.length >= 2 && !Number.isNaN(parts[0])) {
        result['外徑'] = parts[0];

        // 四段式：外徑*內徑*厚度*長度，內徑與厚度直接取用明列值
        if (parts.length >= 4 && !Number.isNaN(parts[1]) && !Number.isNaN(parts[2])) {
            result['內徑'] = parts[1];
            result['厚度'] = parts[2];
            if (!Number.isNaN(parts[3])) {
                result['長度'] = parts[3];
            }
            return result;
        }

        // 二～三段式：外徑*[厚度或內徑]*長度
        if (parts[1] && !Number.isNaN(parts[1])) {
            const val2 = parts[1];
            if (val2 < (parts[0] / 2)) {
                result['厚度'] = val2;
                result['內徑'] = parts[0] - (val2 * 2);
            } else {
                result['內徑'] = val2;
                result['厚度'] = (parts[0] - val2) / 2;
            }
        }
        if (parts[2] && !Number.isNaN(parts[2])) {
            result['長度'] = parts[2];
        }
    }
    return result;
};
