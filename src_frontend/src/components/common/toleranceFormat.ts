export interface ToleranceDisplayItem {
    項目?: string | null;
    尺寸下限?: number | null;
    尺寸上限?: number | null;
    公差下限?: number | null;
    公差上限?: number | null;
    標準值?: number | null;
    單位?: string | null;
}

const hasValue = (value: number | null | undefined): value is number => value !== null && value !== undefined;

export const formatToleranceRange = (tolerance: ToleranceDisplayItem): string => {
    if (tolerance.項目 === '同心度') {
        if (hasValue(tolerance.標準值)) return `最大${tolerance.標準值}`;
        if (hasValue(tolerance.公差上限)) return `最大${tolerance.公差上限}`;
        if (hasValue(tolerance.公差下限)) return `最小${tolerance.公差下限}`;
    }

    if (hasValue(tolerance.尺寸下限) && hasValue(tolerance.尺寸上限)) {
        return `${tolerance.尺寸下限}~${tolerance.尺寸上限}`;
    }

    if (hasValue(tolerance.公差下限) && hasValue(tolerance.公差上限)) {
        const max = tolerance.公差上限;
        const min = tolerance.公差下限;
        if (max === min) return `±${max}`;
        if (min === 0 && max > 0) return `+${max}/-${min}`;
        return `+${max}/${min}`;
    }

    if (hasValue(tolerance.尺寸上限)) return `最大${tolerance.尺寸上限}`;
    if (hasValue(tolerance.尺寸下限)) return `最小${tolerance.尺寸下限}`;
    if (hasValue(tolerance.公差上限)) return `±${tolerance.公差上限}`;
    if (hasValue(tolerance.公差下限)) return `${tolerance.公差下限}`;
    if (hasValue(tolerance.標準值)) return `最大${tolerance.標準值}`;

    return '';
};
