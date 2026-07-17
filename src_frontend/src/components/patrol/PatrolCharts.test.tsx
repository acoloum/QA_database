import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PatrolCharts from './PatrolCharts';
import * as usePatrolHooks from '../../hooks/usePatrol';

vi.mock('react-chartjs-2', () => ({
  Line: () => <canvas aria-label="patrol control chart" />,
  Bar: () => <canvas aria-label="histogram chart" />,
}));

// 使用 vi.fn() 而非靜態工廠，讓個別測試可用 mockReturnValueOnce 覆寫（例如模擬 ids 重複的情境）
const buildSpcChartModelMock = vi.fn();

vi.mock('../../utils/spcChartModel', () => ({
  buildSpcChartModel: (...args: unknown[]) => buildSpcChartModelMock(...args),
}));

const defaultSpcModel = {
  chartData: {
    xBar: {
      labels: ['1', '2'],
      datasets: [{ label: '平均值', data: [9.8, 10.1] }],
    },
    rChart: {
      labels: ['1', '2'],
      datasets: [{ label: '全距', data: [0.1, 0.2] }],
    },
  },
  ids: ['101', '102'],
  analysis: { violations: [] },
  rAnalysis: { violations: [] },
  statsSummary: { count: 2, mean: '10.0', stdDev: '0.1', cv: '1', min: '9.8', max: '10.1', violations: 0 },
  processCapability: {
    available: true,
    applicable: 'capability',
    method: 'G',
    cp: 1.5,
    cpk: 1.33,
    pp: 1.4,
    ppk: 1.2,
    usl: 11,
    lsl: 9,
    ppm: { upper: 0, lower: 0, total: 0 },
  },
  histogramData: null,
  distributionStats: null,
  cpkTrend: null,
};

vi.mock('../../hooks/usePatrol', async () => {
    const actual = await vi.importActual('../../hooks/usePatrol');
    return {
        ...actual,
        usePatrolStats: vi.fn(),
        useExportPatrolSpcReport: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
        useFreezePatrolLimits: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
        useUnfreezePatrolLimits: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
        // PatrolOutlierManagerModal 一律掛載於畫面中（以 show 屬性控制顯示），
        // 故其內部使用的 hooks 也需一併模擬，避免因缺少 QueryClientProvider 而丟出例外
        usePatrolDetails: vi.fn(() => ({ data: [], isLoading: false })),
        useSetPatrolDetailExclusion: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
    };
});

const baseStatsData = {
    labels: ['1', '2'], ids: ['101', '102'], dates: ['2026-01-01', '2026-01-02'],
    avgs: [9.8, 10.1], ranges: [0.1, 0.2], subgroup_sizes: [2, 2], all_values: [9.7, 9.9, 10.0, 10.2],
    x_cl: 10, x_ucl: 10.9, x_lcl: 9.1, r_cl: 0.2, r_ucl: 0.5, r_lcl: 0,
    avg_subgroup_size: 2, tolerance: { found: true, USL: 11, LSL: 9 },
    process_capability: { available: true, usl: 11, lsl: 9, cpk: 1.33 },
    distribution_stats: {}, cpk_trend: [],
};

const defaultProps = {
    machine: '', operator: '', customer: '', material: '6061', spec: '10*2',
    startDate: '2026-01-01', endDate: '2026-01-31',
    statsItem: '外徑', statsPos: '',
    onItemChange: vi.fn(), onPosChange: vi.fn(),
};

describe('PatrolCharts', () => {
    beforeEach(() => {
        buildSpcChartModelMock.mockReturnValue(defaultSpcModel);
    });

    it('顯示管制界限凍結狀態徽章與操作按鈕', () => {
        vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({
            data: { ...baseStatsData, limits_frozen: true },
        } as never);
        render(<PatrolCharts {...defaultProps} />);
        expect(screen.getByText('管制界限已凍結')).toBeInTheDocument();
    });

    it('未凍結時顯示逐次重算徽章', () => {
        vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({
            data: { ...baseStatsData, limits_frozen: false },
        } as never);
        render(<PatrolCharts {...defaultProps} />);
        expect(screen.getByText('界限逐次重算中')).toBeInTheDocument();
    });

    it('離群值管理按鈕於未選擇記錄時停用', () => {
        vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({ data: baseStatsData } as never);
        render(<PatrolCharts {...defaultProps} />);
        expect(screen.getByRole('button', { name: '離群值管理' })).toBeDisabled();
    });

    it('記錄選單於同一 main_id 橫跨多個組別時仍去除重複', () => {
        // 模擬 get_spc 依 (date, main_id, group) 組成標籤時，同一巡檢主檔 id 於 ids 陣列中重複出現的實際情境
        buildSpcChartModelMock.mockReturnValueOnce({
            ...defaultSpcModel,
            ids: ['101', '101', '102'],
        });
        vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({ data: baseStatsData } as never);
        render(<PatrolCharts {...defaultProps} />);

        const recordSelects = screen.getAllByRole('combobox');
        const recordSelect = recordSelects[recordSelects.length - 1];
        const optionValues = within(recordSelect)
            .getAllByRole('option')
            .map(o => (o as HTMLOptionElement).value)
            .filter(v => v !== '');

        expect(optionValues).toEqual(['101', '102']);
    });
});
