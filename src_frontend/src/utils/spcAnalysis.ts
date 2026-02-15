export interface AnalyzedData {
    statuses: ('violation' | null)[];
    violations: { label: string; reasons: string[] }[];
}

export function analyzeWECO(data: number[], cl: number, ucl: number, lcl: number, labels: string[]): AnalyzedData {
    let violations: { label: string; reasons: string[] }[] = [];
    let statuses: ('violation' | null)[] = new Array(data.length).fill(null);

    // Safety check
    if (data.length === 0) return { statuses, violations };

    const sigma = (ucl - cl) / 3;
    const sigma1_above = cl + sigma;
    const sigma1_below = cl - sigma;
    const sigma2_above = cl + 2 * sigma;
    const sigma2_below = cl - 2 * sigma;

    for (let i = 0; i < data.length; i++) {
        let val = data[i];
        let reasons: string[] = [];

        // Rule 1: 單點超出控制限 (±3σ)
        if (val > ucl || val < lcl) reasons.push("Rule 1: 超出控制限");

        // Rule 2: 連續9點在中心線同側
        if (i >= 8) {
            let last9 = data.slice(i - 8, i + 1);
            if (last9.every(v => v > cl) || last9.every(v => v < cl))
                reasons.push("Rule 2: 連續9點同側");
        }

        // Rule 3: 連續6點連續上升或下降
        if (i >= 5) {
            let last6 = data.slice(i - 5, i + 1);
            let increasing = true, decreasing = true;
            for (let j = 1; j < last6.length; j++) {
                if (last6[j] <= last6[j - 1]) increasing = false;
                if (last6[j] >= last6[j - 1]) decreasing = false;
            }
            if (increasing || decreasing) reasons.push("Rule 3: 連續6點趨勢");
        }

        // Rule 4: 連續14點交替上升下降
        if (i >= 13) {
            let last14 = data.slice(i - 13, i + 1);
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
        if (i >= 2) {
            let last3 = data.slice(i - 2, i + 1);
            let countAbove = last3.filter(v => v > sigma2_above).length;
            let countBelow = last3.filter(v => v < sigma2_below).length;
            if (countAbove >= 2 || countBelow >= 2)
                reasons.push("Rule 5: 3點中2點在2σ外");
        }

        // Rule 6: 連續5點中有4點落在1σ外
        if (i >= 4) {
            let last5 = data.slice(i - 4, i + 1);
            let count = last5.filter(v => v > sigma1_above || v < sigma1_below).length;
            if (count >= 4) reasons.push("Rule 6: 5點中4點在1σ外");
        }

        // Rule 7: 連續15點在1σ内
        if (i >= 14) {
            let last15 = data.slice(i - 14, i + 1);
            if (last15.every(v => v >= sigma1_below && v <= sigma1_above))
                reasons.push("Rule 7: 連續15點在1σ内");
        }

        // Rule 8: 連續8點在中心線兩側但都不在1σ内
        if (i >= 7) {
            let last8 = data.slice(i - 7, i + 1);
            // The logic in shipping.html was a bit complex, simplifying here to match concept:
            // "8 points in a row on both sides of centerline with none in Zone C (within 1 sigma)"
            // Actually Rule 8 is "8 consecutive points on both sides of center line with no points in Zone C"
            let inZoneC = last8.some(v => v > sigma1_below && v < sigma1_above);
            if (!inZoneC) reasons.push("Rule 8: 8點在1σ外且兩側");
        }

        if (reasons.length > 0) {
            statuses[i] = "violation";
            violations.push({ label: labels[i], reasons: reasons });
        }
    }
    return { statuses, violations };
}
