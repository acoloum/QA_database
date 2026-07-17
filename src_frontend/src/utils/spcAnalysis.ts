export interface AnalyzedData {
    statuses: ('violation' | null)[];
    violations: { label: string; reasons: string[] }[];
}

// 後端規則 id → 前端規則實作對映；預設集與後端 DEFAULT_STABILITY_RULES 一致。
// 注意：此清單需與後端 backend/services/spc_stability.py 的 DEFAULT_STABILITY_RULES
// 保持同步，避免前後端對「失控」的判定準則產生落差。
export const DEFAULT_RULES = ['beyond_limits', 'run_9_same_side', 'trend_6'];

export function analyzeWECO(
    data: number[], cl: number, ucl: number, lcl: number, labels: string[],
    enabledRules: string[] = DEFAULT_RULES,
): AnalyzedData {
    const violations: { label: string; reasons: string[] }[] = [];
    const statuses: ('violation' | null)[] = new Array(data.length).fill(null);

    // Safety check
    if (data.length === 0) return { statuses, violations };

    const sigma = (ucl - cl) / 3;
    const sigma1_above = cl + sigma;
    const sigma1_below = cl - sigma;
    const sigma2_above = cl + 2 * sigma;
    const sigma2_below = cl - 2 * sigma;

    for (let i = 0; i < data.length; i++) {
        const val = data[i];
        const reasons: string[] = [];

        // Rule 1: 單點超出控制限 (±3σ)
        if (enabledRules.includes('beyond_limits') && (val > ucl || val < lcl)) reasons.push("Rule 1: 超出控制限");

        // Rule 2: 連續9點在中心線同側
        if (enabledRules.includes('run_9_same_side') && i >= 8) {
            const last9 = data.slice(i - 8, i + 1);
            if (last9.every(v => v > cl) || last9.every(v => v < cl))
                reasons.push("Rule 2: 連續9點同側");
        }

        // Rule 3: 連續6點連續上升或下降
        if (enabledRules.includes('trend_6') && i >= 5) {
            const last6 = data.slice(i - 5, i + 1);
            let increasing = true, decreasing = true;
            for (let j = 1; j < last6.length; j++) {
                if (last6[j] <= last6[j - 1]) increasing = false;
                if (last6[j] >= last6[j - 1]) decreasing = false;
            }
            if (increasing || decreasing) reasons.push("Rule 3: 連續6點趨勢");
        }

        // Rule 4: 連續14點交替上升下降
        if (enabledRules.includes('alternating_14') && i >= 13) {
            const last14 = data.slice(i - 13, i + 1);
            let alternating = true;
            for (let j = 1; j < last14.length; j++) {
                if ((j % 2 === 0 && last14[j] < last14[j - 1]) ||
                    (j % 2 !== 0 && last14[j] > last14[j - 1])) {
                    alternating = false;
                    break;
                }
            }
            if (alternating) reasons.push("Rule 4: 14點交替");
        }

        // Rule 5: 連續3點中有2點落在2σ外
        if (enabledRules.includes('two_of_three_beyond_2s') && i >= 2) {
            const last3 = data.slice(i - 2, i + 1);
            const countAbove = last3.filter(v => v > sigma2_above).length;
            const countBelow = last3.filter(v => v < sigma2_below).length;
            if (countAbove >= 2 || countBelow >= 2)
                reasons.push("Rule 5: 3點中2點在2σ外");
        }

        // Rule 6: 連續5點中有4點落在1σ外
        if (enabledRules.includes('four_of_five_beyond_1s') && i >= 4) {
            const last5 = data.slice(i - 4, i + 1);
            const count = last5.filter(v => v > sigma1_above || v < sigma1_below).length;
            if (count >= 4) reasons.push("Rule 6: 5點中4點在1σ外");
        }

        // Rule 7: 連續15點在1σ内
        if (enabledRules.includes('fifteen_within_1s') && i >= 14) {
            const last15 = data.slice(i - 14, i + 1);
            if (last15.every(v => v >= sigma1_below && v <= sigma1_above))
                reasons.push("Rule 7: 連續15點在1σ内");
        }

        // Rule 8: 連續8點在中心線兩側但都不在1σ内
        if (enabledRules.includes('eight_beyond_1s_both') && i >= 7) {
            const last8 = data.slice(i - 7, i + 1);
            // The logic in shipping.html was a bit complex, simplifying here to match concept:
            // "8 points in a row on both sides of centerline with none in Zone C (within 1 sigma)"
            // Actually Rule 8 is "8 consecutive points on both sides of center line with no points in Zone C"
            const inZoneC = last8.some(v => v > sigma1_below && v < sigma1_above);
            if (!inZoneC) reasons.push("Rule 8: 8點在1σ外且兩側");
        }

        if (reasons.length > 0) {
            statuses[i] = "violation";
            violations.push({ label: labels[i], reasons: reasons });
        }
    }
    return { statuses, violations };
}

// --- Process Capability Helpers ---

export interface ProcessCapabilityGrade {
    label: string;
    color: string;
    bgColor: string;
    description: string;
}

export function getCpkGrade(cpk: number | null | undefined): ProcessCapabilityGrade {
    if (cpk == null) return { label: 'N/A', color: '#6c757d', bgColor: '#e9ecef', description: '無法計算' };
    if (cpk >= 1.67) return { label: 'A', color: '#155724', bgColor: '#d4edda', description: '優秀' };
    if (cpk >= 1.33) return { label: 'B', color: '#0c5460', bgColor: '#d1ecf1', description: '良好' };
    if (cpk >= 1.0) return { label: 'C', color: '#856404', bgColor: '#fff3cd', description: '可接受' };
    return { label: 'D', color: '#721c24', bgColor: '#f8d7da', description: '不足' };
}

// --- Histogram ---

export interface HistogramBin {
    label: string;
    min: number;
    max: number;
    count: number;
    midpoint: number;
}

export function generateHistogramBins(data: number[], binCount?: number): HistogramBin[] {
    if (data.length === 0) return [];

    const sorted = [...data].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const range = max - min;

    if (range === 0) {
        return [{ label: min.toFixed(3), min, max, count: data.length, midpoint: min }];
    }

    // Sturges' formula
    const n = binCount || Math.ceil(Math.log2(data.length) + 1);
    const binWidth = range / n;

    const bins: HistogramBin[] = [];
    for (let i = 0; i < n; i++) {
        const bMin = min + i * binWidth;
        const bMax = i === n - 1 ? max + 0.0001 : min + (i + 1) * binWidth;
        const count = data.filter(v => v >= bMin && v < bMax).length;
        bins.push({
            label: `${bMin.toFixed(2)}~${(min + (i + 1) * binWidth).toFixed(2)}`,
            min: bMin,
            max: bMax,
            count,
            midpoint: (bMin + bMax) / 2
        });
    }
    return bins;
}

// --- Normal Distribution PDF ---

export function normalPDF(x: number, mean: number, stdDev: number): number {
    if (stdDev <= 0) return 0;
    const exponent = -0.5 * Math.pow((x - mean) / stdDev, 2);
    return (1 / (stdDev * Math.sqrt(2 * Math.PI))) * Math.exp(exponent);
}

// --- Moving Average ---

export function movingAverage(data: number[], window: number = 5): (number | null)[] {
    return data.map((_, i) => {
        if (i < window - 1) return null;
        const slice = data.slice(i - window + 1, i + 1);
        return slice.reduce((a, b) => a + b, 0) / window;
    });
}

// --- R-chart WECO analysis (simplified: Rule 1 + Rule 2) ---
export function analyzeRChartWECO(data: number[], r_cl: number, r_ucl: number, labels: string[]): AnalyzedData {
    const violations: { label: string; reasons: string[] }[] = [];
    const statuses: ('violation' | null)[] = new Array(data.length).fill(null);

    if (data.length === 0) return { statuses, violations };

    for (let i = 0; i < data.length; i++) {
        const val = data[i];
        const reasons: string[] = [];

        // Rule 1: Beyond UCL
        if (val > r_ucl) reasons.push("R Rule 1: 超出管制上限");

        // Rule 2: 9 consecutive points on same side of CL
        if (i >= 8) {
            const last9 = data.slice(i - 8, i + 1);
            if (last9.every(v => v > r_cl) || last9.every(v => v < r_cl))
                reasons.push("R Rule 2: 連續9點同側");
        }

        // Rule 3: 6 consecutive increasing or decreasing
        if (i >= 5) {
            const last6 = data.slice(i - 5, i + 1);
            let inc = true, dec = true;
            for (let j = 1; j < last6.length; j++) {
                if (last6[j] <= last6[j - 1]) inc = false;
                if (last6[j] >= last6[j - 1]) dec = false;
            }
            if (inc || dec) reasons.push("R Rule 3: 連續6點趨勢");
        }

        if (reasons.length > 0) {
            statuses[i] = 'violation';
            violations.push({ label: labels[i], reasons });
        }
    }
    return { statuses, violations };
}

// --- PPM formatting ---
export function formatPPM(ppm: number): string {
    if (ppm >= 1000000) return '> 1M';
    if (ppm >= 10000) return `${(ppm / 1000).toFixed(1)}K`;
    if (ppm >= 1) return ppm.toFixed(0);
    if (ppm >= 0.001) return ppm.toFixed(2);
    return '< 0.001';
}

// --- PPM grade color ---
export function getPpmGrade(ppm: number): { color: string; bgColor: string; label: string } {
    if (ppm <= 3.4) return { color: '#155724', bgColor: '#d4edda', label: '六標準差水準' };
    if (ppm <= 63) return { color: '#0c5460', bgColor: '#d1ecf1', label: '極低不良率' };
    if (ppm <= 6210) return { color: '#856404', bgColor: '#fff3cd', label: '中等不良率' };
    return { color: '#721c24', bgColor: '#f8d7da', label: '需要改善' };
}
