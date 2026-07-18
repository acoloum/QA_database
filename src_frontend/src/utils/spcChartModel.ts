import type { ChartData } from 'chart.js';
import type {
  CpkTrend,
  DistributionStats,
  HistogramBin,
  ProcessCapability,
  SpcChartData,
  SpcChartKind,
  SpcChartSet,
  SpcChartType,
  SpcStability,
  SpcStabilityViolation,
  SpcViolation,
} from '../types';
import { generateHistogramBins, movingAverage, normalPDF } from './spcAnalysis';

export interface SpcStatsSummary {
  count: number;
  mean: string;
  min: string;
  max: string;
  range: string;
  stdDev: string;
  cv: string;
  violations: number;
}

export interface SpcHistogramData {
  bins: HistogramBin[];
  normalCurve: number[];
  allMean: number;
  allStdDev: number;
  usl?: number;
  lsl?: number;
}

interface ChartAnalysis {
  statuses: ('violation' | null)[];
  violations: SpcViolation[];
}

export interface SpcChartModel {
  chartData: { xBar: ChartData<'line'>; rChart: ChartData<'line'> } | null;
  chartType: SpcChartType | null;
  locationLabel: string;
  variationLabel: string;
  ids: string[];
  analysis: ChartAnalysis | null;
  rAnalysis: ChartAnalysis | null;
  statsSummary: SpcStatsSummary | null;
  processCapability: ProcessCapability | null;
  histogramData: SpcHistogramData | null;
  distributionStats: DistributionStats | null;
  cpkTrend: CpkTrend[] | null;
  stability: SpcStability | null;
}

export interface SpcChartModelOptions {
  /** 現場管制圖不預設顯示規格界限；回溯分析可由使用者開啟。 */
  showSpecLimits?: boolean;
}

const CHART_LABELS: Record<SpcChartType, { location: string; variation: string }> = {
  xbar_s: { location: '平均值 X̄', variation: '標準差 S' },
  xbar_r: { location: '平均值 X̄', variation: '全距 R' },
  i_mr: { location: '個別值 I', variation: '移動全距 MR' },
};

const emptySpcChartModel = (): SpcChartModel => ({
  chartData: null,
  chartType: null,
  locationLabel: '位置統計量',
  variationLabel: '變異統計量',
  ids: [],
  analysis: null,
  rAnalysis: null,
  statsSummary: null,
  processCapability: null,
  histogramData: null,
  distributionStats: null,
  cpkTrend: null,
  stability: null,
});

const repeat = (value: number | null, count: number): number[] =>
  value == null ? [] : Array(count).fill(value);

const legacyChartSet = (data: SpcChartData): SpcChartSet | null => {
  const count = data.avgs.length;
  if (count === 0 || [data.x_cl, data.x_ucl, data.x_lcl, data.r_cl, data.r_ucl, data.r_lcl]
    .some(value => value == null)) return null;
  return {
    chart_type: 'xbar_r',
    subgroup_sizes: data.subgroup_sizes,
    sigma_within: 0,
    location: {
      statistic: 'xbar', values: data.avgs,
      cl: data.x_cls ?? repeat(data.x_cl, count),
      ucl: data.x_ucls ?? repeat(data.x_ucl, count),
      lcl: data.x_lcls ?? repeat(data.x_lcl, count),
    },
    variation: {
      statistic: 'r', values: data.ranges,
      cl: data.r_cls ?? repeat(data.r_cl, count),
      ucl: data.r_ucls ?? repeat(data.r_ucl, count),
      lcl: data.r_lcls ?? repeat(data.r_lcl, count),
    },
  };
};

const violationsFor = (
  stability: SpcStability | undefined,
  chartKind: SpcChartKind,
): SpcStabilityViolation[] => {
  const nested = stability?.[chartKind];
  if (nested) return nested.violations;
  return (stability?.violations ?? []).filter(item => item.chart_kind === chartKind);
};

const analysisFromBackend = (
  stability: SpcStability | undefined,
  chartKind: SpcChartKind,
  labels: string[],
  count: number,
): ChartAnalysis => {
  const statuses: ('violation' | null)[] = Array(count).fill(null);
  const type = chartKind === 'location' ? 'xbar' : 'r';
  const violations = violationsFor(stability, chartKind).map(item => {
    if (item.index >= 0 && item.index < count) statuses[item.index] = 'violation';
    return {
      label: labels[item.index] ?? String(item.index),
      reasons: [item.label],
      type,
      chart_kind: chartKind,
      index: item.index,
      window_start: item.window_start,
      window_end: item.window_end,
    } satisfies SpcViolation;
  });
  return { statuses, violations };
};

export const buildSpcChartModel = (
  statsData: SpcChartData | null | undefined,
  options: SpcChartModelOptions = {},
): SpcChartModel => {
  if (!statsData) return emptySpcChartModel();
  const charts = statsData.charts ?? legacyChartSet(statsData);
  if (!charts || charts.location.values.length === 0) return emptySpcChartModel();

  const labels = statsData.labels;
  const locationValues = charts.location.values.filter((value): value is number => value != null);
  const count = charts.location.values.length;
  const analysis = analysisFromBackend(statsData.stability, 'location', labels, count);
  const rAnalysis = analysisFromBackend(statsData.stability, 'variation', labels, count);
  const chartLabels = CHART_LABELS[charts.chart_type];

  const mean = locationValues.reduce((sum, value) => sum + value, 0) / locationValues.length;
  const sorted = [...locationValues].sort((a, b) => a - b);
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  const variance = locationValues.length > 1
    ? locationValues.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (locationValues.length - 1)
    : 0;
  const stdDev = Math.sqrt(variance);
  const summary: SpcStatsSummary = {
    count: locationValues.length,
    mean: mean.toFixed(3),
    min: min.toFixed(3),
    max: max.toFixed(3),
    range: (max - min).toFixed(3),
    stdDev: stdDev.toFixed(3),
    cv: (mean !== 0 ? (stdDev / Math.abs(mean)) * 100 : 0).toFixed(2),
    violations: analysis.violations.length + rAnalysis.violations.length,
  };

  const processCapability = statsData.capability ?? statsData.process_capability ?? null;
  const allValues = statsData.all_values ?? [];
  let histogramData: SpcHistogramData | null = null;
  if (allValues.length > 0) {
    const bins = generateHistogramBins(allValues);
    const allMean = allValues.reduce((sum, value) => sum + value, 0) / allValues.length;
    const allVariance = allValues.length > 1
      ? allValues.reduce((sum, value) => sum + (value - allMean) ** 2, 0) / (allValues.length - 1)
      : 0;
    const allStdDev = Math.sqrt(allVariance);
    const binWidth = bins.length > 1 ? bins[1].midpoint - bins[0].midpoint : 1;
    const totalArea = allValues.length * binWidth;
    histogramData = {
      bins,
      normalCurve: bins.map(bin => normalPDF(bin.midpoint, allMean, allStdDev) * totalArea),
      allMean,
      allStdDev,
      usl: processCapability?.usl,
      lsl: processCapability?.lsl,
    };
  }

  const locationNumbers = charts.location.values.map(value => value ?? Number.NaN);
  const movingAverageValues = movingAverage(locationNumbers, 5);
  const zone1Upper = charts.location.cl.map((cl, index) =>
    cl + (charts.location.ucl[index] - cl) / 3);
  const zone1Lower = charts.location.cl.map((cl, index) =>
    cl - (charts.location.ucl[index] - cl) / 3);
  const zone2Upper = charts.location.cl.map((cl, index) =>
    cl + 2 * (charts.location.ucl[index] - cl) / 3);
  const zone2Lower = charts.location.cl.map((cl, index) =>
    cl - 2 * (charts.location.ucl[index] - cl) / 3);

  const pointColors = charts.location.values.map((value, index) => {
    if (value != null && (value > charts.location.ucl[index] || value < charts.location.lcl[index])) {
      return '#dc3545';
    }
    return analysis.statuses[index] === 'violation' ? '#fd7e14' : '#0d6efd';
  });
  const rPointColors = charts.variation.values.map((value, index) => {
    if (value != null && (value > charts.variation.ucl[index] || value < charts.variation.lcl[index])) {
      return '#dc3545';
    }
    return rAnalysis.statuses[index] === 'violation' ? '#fd7e14' : '#6f42c1';
  });

  const xBarDatasets: ChartData<'line'>['datasets'] = [
    {
      label: chartLabels.location,
      data: charts.location.values,
      borderColor: '#0d6efd',
      backgroundColor: pointColors,
      pointRadius: analysis.statuses.map(status => status === 'violation' ? 8 : 4),
      pointBorderColor: analysis.statuses.map(status => status === 'violation' ? '#fff' : '#0d6efd'),
      pointBorderWidth: 2,
      tension: 0.1,
      order: 1,
    },
    { label: '移動平均 (MA5)', data: movingAverageValues, borderColor: '#20c997', borderWidth: 2, borderDash: [8, 4], pointRadius: 0, tension: 0.3, order: 2 },
    { label: '+1σ', data: zone1Upper, borderColor: 'transparent', backgroundColor: 'rgba(40, 167, 69, 0.08)', fill: '+1', pointRadius: 0, order: 10 },
    { label: '-1σ', data: zone1Lower, borderColor: 'transparent', backgroundColor: 'rgba(40, 167, 69, 0.08)', fill: '-1', pointRadius: 0, order: 10 },
    { label: '+2σ', data: zone2Upper, borderColor: 'rgba(255, 193, 7, 0.3)', borderWidth: 1, borderDash: [3, 3], backgroundColor: 'rgba(255, 193, 7, 0.06)', fill: '-2', pointRadius: 0, order: 10 },
    { label: '-2σ', data: zone2Lower, borderColor: 'rgba(255, 193, 7, 0.3)', borderWidth: 1, borderDash: [3, 3], backgroundColor: 'rgba(255, 193, 7, 0.06)', fill: '+2', pointRadius: 0, order: 10 },
    { label: 'UCL', data: charts.location.ucl, borderColor: 'red', borderDash: [5, 5], pointRadius: 0, order: 5 },
    { label: 'CL', data: charts.location.cl, borderColor: 'green', pointRadius: 0, order: 5 },
    { label: 'LCL', data: charts.location.lcl, borderColor: 'red', borderDash: [5, 5], pointRadius: 0, order: 5 },
  ];
  if (
    options.showSpecLimits && processCapability?.available
    && processCapability.usl != null && processCapability.lsl != null
  ) {
    xBarDatasets.push(
      { label: 'USL', data: Array(count).fill(processCapability.usl), borderColor: '#e83e8c', borderDash: [10, 5], borderWidth: 2, pointRadius: 0, order: 4 },
      { label: 'LSL', data: Array(count).fill(processCapability.lsl), borderColor: '#e83e8c', borderDash: [10, 5], borderWidth: 2, pointRadius: 0, order: 4 },
    );
  }

  return {
    chartData: {
      xBar: { labels, datasets: xBarDatasets },
      rChart: {
        labels,
        datasets: [
          {
            label: chartLabels.variation,
            data: charts.variation.values,
            borderColor: '#6f42c1',
            backgroundColor: rPointColors,
            pointRadius: rAnalysis.statuses.map(status => status === 'violation' ? 8 : 4),
            pointBorderColor: rPointColors,
            pointBorderWidth: 2,
            tension: 0.1,
          },
          { label: 'UCL', data: charts.variation.ucl, borderColor: 'red', borderDash: [5, 5], pointRadius: 0 },
          { label: `${chartLabels.variation} CL`, data: charts.variation.cl, borderColor: 'green', pointRadius: 0 },
          { label: 'LCL', data: charts.variation.lcl, borderColor: 'red', borderDash: [5, 5], pointRadius: 0 },
        ],
      },
    },
    chartType: charts.chart_type,
    locationLabel: chartLabels.location,
    variationLabel: chartLabels.variation,
    ids: statsData.ids ?? [],
    analysis,
    rAnalysis,
    statsSummary: summary,
    processCapability,
    histogramData,
    distributionStats: statsData.distribution_stats ?? (
      statsData.distribution ? {
        model: statsData.distribution.model ?? undefined,
        model_label: statsData.distribution.label,
      } : null
    ),
    cpkTrend: statsData.cpk_trend ?? [],
    stability: statsData.stability ?? null,
  };
};
