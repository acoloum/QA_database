/**
 * Parse a spec string like '62.5*2.3*450' into dimensional values.
 * Handles various separator formats: ×, x, X, *
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
