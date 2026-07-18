import { describe, expect, it } from 'vitest';
import { analyzeWECO } from './spcAnalysis';

// WECO Rule 6（four_of_five_beyond_1s）：連續5點中需有4點「同側」超出1σ才算違規，
// 兩側合計達4點（例如2點在+1σ外、2點在-1σ外）不應觸發。
// 對應後端 backend/services/spc_stability.py 的 above>=4 or below>=4 邏輯。
describe('analyzeWECO - Rule 6 (four_of_five_beyond_1s)', () => {
    const cl = 10;
    const ucl = 13; // sigma = (ucl - cl) / 3 = 1 → 1σ界線為 9 / 11
    const lcl = 7;

    it('兩側合計4點（2點超出+1σ、2點超出-1σ）不應觸發規則6', () => {
        const data = [12, 8, 12, 8, 10];
        const labels = data.map((_, i) => `P${i}`);
        const result = analyzeWECO(data, cl, ucl, lcl, labels, ['four_of_five_beyond_1s']);

        expect(result.statuses[4]).toBeNull();
        expect(result.violations.some(v => v.reasons.some(r => r.startsWith('Rule 6')))).toBe(false);
    });

    it('連續5點中有4點同側超出+1σ應觸發規則6', () => {
        const data = [12, 12.5, 9.5, 12.2, 12.8];
        const labels = data.map((_, i) => `P${i}`);
        const result = analyzeWECO(data, cl, ucl, lcl, labels, ['four_of_five_beyond_1s']);

        expect(result.statuses[4]).toBe('violation');
        expect(result.violations.some(v => v.reasons.some(r => r.startsWith('Rule 6')))).toBe(true);
    });

    it('連續5點中有4點同側超出-1σ應觸發規則6', () => {
        const data = [8, 7.5, 10.5, 7.8, 7.2];
        const labels = data.map((_, i) => `P${i}`);
        const result = analyzeWECO(data, cl, ucl, lcl, labels, ['four_of_five_beyond_1s']);

        expect(result.statuses[4]).toBe('violation');
        expect(result.violations.some(v => v.reasons.some(r => r.startsWith('Rule 6')))).toBe(true);
    });
});

describe('analyzeWECO - 展示工具規則 4 與規則 8', () => {
    it('14 點交替的兩種起始相位都可辨識', () => {
        const labels = Array.from({ length: 14 }, (_, index) => `P${index}`);
        const phaseA = [9, 11, 9, 11, 9, 11, 9, 11, 9, 11, 9, 11, 9, 11];
        const phaseB = [11, 9, 11, 9, 11, 9, 11, 9, 11, 9, 11, 9, 11, 9];

        expect(analyzeWECO(phaseA, 10, 13, 7, labels, ['alternating_14']).statuses[13])
            .toBe('violation');
        expect(analyzeWECO(phaseB, 10, 13, 7, labels, ['alternating_14']).statuses[13])
            .toBe('violation');
    });

    it('規則 8 必須同時分布在中心線兩側', () => {
        const labels = Array.from({ length: 8 }, (_, index) => `P${index}`);
        const oneSide = Array(8).fill(12);
        const bothSides = [12, 8, 12, 8, 12, 8, 12, 8];

        expect(analyzeWECO(oneSide, 10, 13, 7, labels, ['eight_beyond_1s_both']).statuses[7])
            .toBeNull();
        expect(analyzeWECO(bothSides, 10, 13, 7, labels, ['eight_beyond_1s_both']).statuses[7])
            .toBe('violation');
    });
});
