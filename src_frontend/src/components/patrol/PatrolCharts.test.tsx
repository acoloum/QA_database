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
  mergeOngoingStudyForDisplay: (data: unknown) => data,
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
  chartType: 'xbar_r',
  locationLabel: '平均值 X̄',
  variationLabel: '全距 R',
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

vi.mock('../spc/SpcStudyPanel', () => ({
  default: ({ source, filters }: { source: string; filters: Record<string, unknown> }) => (
    <div data-testid="spc-study-panel">SPC 研究與基準 · {source} · {String(filters.mat)}</div>
  ),
}));

vi.mock('../../hooks/usePatrol', async () => {
    const actual = await vi.importActual('../../hooks/usePatrol');
    return {
        ...actual,
        usePatrolStats: vi.fn(),
        useExportPatrolSpcReport: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
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

    it('顯示共用研究流程並移除舊凍結入口', () => {
        vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({
            data: { ...baseStatsData, limits_frozen: true },
        } as never);
        render(<PatrolCharts {...defaultProps} />);
        expect(screen.getByTestId('spc-study-panel')).toHaveTextContent('patrol · 6061');
        expect(screen.queryByRole('button', { name: '凍結目前界限' })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: '解除凍結' })).not.toBeInTheDocument();
        expect(screen.getByRole('link', { name: '進階變數分析' })).toHaveAttribute(
            'href',
            '/spc/advanced?family=variable&source=patrol&mat=6061&spec=10*2&item=%E5%A4%96%E5%BE%91&s=2026-01-01&e=2026-01-31',
        );
    });

    it('固定機台、材質、規格、項目與位置齊全時提供機器績效入口', () => {
        vi.mocked(usePatrolHooks.usePatrolStats).mockReturnValue({ data: baseStatsData } as never);
        render(<PatrolCharts {...defaultProps} machine="7" operator="9" customer="3" statsPos="前段" />);
        expect(screen.getByRole('link', { name: '進階機器績效' })).toHaveAttribute(
            'href',
            '/spc/advanced?family=machine&source=patrol&m_id=7&op_id=9&cust_id=3&mat=6061&spec=10*2&item=%E5%A4%96%E5%BE%91&pos=%E5%89%8D%E6%AE%B5&s=2026-01-01&e=2026-01-31',
        );
        expect(screen.queryByRole('link', { name: '進階變數分析' })).not.toBeInTheDocument();
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
