import type { ChartData } from 'chart.js';
import type {
  CpkTrend,
  DistributionStats,
  HistogramBin,
  ProcessCapability,
  SpcChartData,
  SpcStability,
  SpcViolation,
} from '../types';
import {
  analyzeRChartWECO,
  analyzeWECO,
  generateHistogramBins,
  movingAverage,
  normalPDF,
} from './spcAnalysis';

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

export interface SpcChartModel {
  chartData: {
    xBar: ChartData<'line'>;
    rChart: ChartData<'line'>;
  } | null;
  ids: string[];
  analysis: { statuses: ('violation' | null)[]; violations: SpcViolation[] } | null;
  rAnalysis: { statuses: ('violation' | null)[]; violations: SpcViolation[] } | null;
  statsSummary: SpcStatsSummary | null;
  processCapability: ProcessCapability | null;
  histogramData: SpcHistogramData | null;
  distributionStats: DistributionStats | null;
  cpkTrend: CpkTrend[] | null;
  stability: SpcStability | null;
}

const emptySpcChartModel = (): SpcChartModel => ({
  chartData: null,
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

export const buildSpcChartModel = (statsData: SpcChartData | null | undefined): SpcChartModel => {
  if (!statsData || !statsData.avgs || statsData.avgs.length === 0) {
    return emptySpcChartModel();
  }

  const data = statsData;
  const ids = data.ids || [];
  const count = data.avgs.length;

  const wecoRaw = analyzeWECO(data.avgs, data.x_cl, data.x_ucl, data.x_lcl, data.labels);
  const weco = {
    ...wecoRaw,
    violations: wecoRaw.violations.map(v => ({ ...v, type: 'xbar' as const })),
  };

  const rWecoRaw = analyzeRChartWECO(data.ranges, data.r_cl, data.r_ucl, data.labels);
  const rWeco = {
    ...rWecoRaw,
    violations: rWecoRaw.violations.map(v => ({ ...v, type: 'r' as const })),
  };

  const mean = data.avgs.reduce((a: number, b: number) => a + b, 0) / count;
  const sorted = [...data.avgs].sort((a: number, b: number) => a - b);
  const min = sorted[0];
  const max = sorted[count - 1];
  const range = max - min;
  const variance = count > 1
    ? data.avgs.reduce((acc: number, val: number) => acc + Math.pow(val - mean, 2), 0) / (count - 1)
    : 0;
  const stdDev = Math.sqrt(variance);
  const cv = mean !== 0 ? (stdDev / Math.abs(mean)) * 100 : 0;

  const summary: SpcStatsSummary = {
    count,
    mean: mean.toFixed(3),
    min: min.toFixed(3),
    max: max.toFixed(3),
    range: range.toFixed(3),
    stdDev: stdDev.toFixed(3),
    cv: cv.toFixed(2),
    violations: weco.violations.length + rWeco.violations.length,
  };

  const pc = data.process_capability || null;
  const allValues = data.all_values || [];
  let histData: SpcHistogramData | null = null;
  if (allValues.length > 0) {
    const bins = generateHistogramBins(allValues);
    const allMean = allValues.reduce((a: number, b: number) => a + b, 0) / allValues.length;
    const allVariance = allValues.length > 1
      ? allValues.reduce((a: number, v: number) => a + Math.pow(v - allMean, 2), 0) / (allValues.length - 1)
      : 0;
    const allStdDev = Math.sqrt(allVariance);
    const binWidth = bins.length > 1 ? bins[1].midpoint - bins[0].midpoint : 1;
    const totalArea = allValues.length * binWidth;
    const normalCurve = bins.map(b => normalPDF(b.midpoint, allMean, allStdDev) * totalArea);

    histData = { bins, normalCurve, allMean, allStdDev, usl: pc?.usl, lsl: pc?.lsl };
  }

  const ma = movingAverage(data.avgs, 5);
  const sigma = (data.x_ucl - data.x_cl) / 3;
  const zone1Upper = Array(count).fill(data.x_cl + sigma);
  const zone1Lower = Array(count).fill(data.x_cl - sigma);
  const zone2Upper = Array(count).fill(data.x_cl + 2 * sigma);
  const zone2Lower = Array(count).fill(data.x_cl - 2 * sigma);

  const pointColors = data.avgs.map((val: number, i: number) => {
    if (val > data.x_ucl || val < data.x_lcl) return '#dc3545';
    if (weco.statuses[i] === 'violation') return '#fd7e14';
    return '#0d6efd';
  });

  const pointRadius = data.avgs.map((_: number, i: number) => {
    if (weco.statuses[i] === 'violation') return 8;
    return 4;
  });

  const pointBorderColor = data.avgs.map((_: number, i: number) => {
    if (weco.statuses[i] === 'violation') return '#fff';
    return '#0d6efd';
  });

  const rPointColors = data.ranges.map((val: number, i: number) => {
    if (val > data.r_ucl) return '#dc3545';
    if (rWeco.statuses[i] === 'violation') return '#fd7e14';
    return '#6f42c1';
  });

  const rPointRadius = data.ranges.map((_: number, i: number) => {
    if (rWeco.statuses[i] === 'violation') return 8;
    return 4;
  });

  const xBarDatasets: ChartData<'line'>['datasets'] = [
    {
      label: '平均值',
      data: data.avgs,
      borderColor: '#0d6efd',
      backgroundColor: pointColors,
      pointRadius,
      pointBorderColor,
      pointBorderWidth: 2,
      tension: 0.1,
      order: 1,
    },
    {
      label: '移動平均 (MA5)',
      data: ma,
      borderColor: '#20c997',
      borderWidth: 2,
      borderDash: [8, 4],
      pointRadius: 0,
      tension: 0.3,
      order: 2,
    },
    { label: '+1σ', data: zone1Upper, borderColor: 'transparent', backgroundColor: 'rgba(40, 167, 69, 0.08)', fill: '+1', pointRadius: 0, order: 10 },
    { label: '-1σ', data: zone1Lower, borderColor: 'transparent', backgroundColor: 'rgba(40, 167, 69, 0.08)', fill: '-1', pointRadius: 0, order: 10 },
    { label: '+2σ', data: zone2Upper, borderColor: 'rgba(255, 193, 7, 0.3)', borderWidth: 1, borderDash: [3, 3], backgroundColor: 'rgba(255, 193, 7, 0.06)', fill: '-2', pointRadius: 0, order: 10 },
    { label: '-2σ', data: zone2Lower, borderColor: 'rgba(255, 193, 7, 0.3)', borderWidth: 1, borderDash: [3, 3], backgroundColor: 'rgba(255, 193, 7, 0.06)', fill: '+2', pointRadius: 0, order: 10 },
    { label: 'UCL', data: Array(count).fill(data.x_ucl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0, order: 5 },
    { label: 'CL', data: Array(count).fill(data.x_cl), borderColor: 'green', pointRadius: 0, order: 5 },
    { label: 'LCL', data: Array(count).fill(data.x_lcl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0, order: 5 },
  ];

  if (pc?.available && pc.usl != null && pc.lsl != null) {
    xBarDatasets.push(
      { label: 'USL', data: Array(count).fill(pc.usl), borderColor: '#e83e8c', borderDash: [10, 5], borderWidth: 2, pointRadius: 0, order: 4 },
      { label: 'LSL', data: Array(count).fill(pc.lsl), borderColor: '#e83e8c', borderDash: [10, 5], borderWidth: 2, pointRadius: 0, order: 4 },
    );
  }

  return {
    chartData: {
      xBar: {
        labels: data.labels,
        datasets: xBarDatasets,
      },
      rChart: {
        labels: data.labels,
        datasets: [
          {
            label: '全距 R',
            data: data.ranges,
            borderColor: '#6f42c1',
            backgroundColor: rPointColors,
            pointRadius: rPointRadius,
            pointBorderColor: rPointColors,
            pointBorderWidth: 2,
            tension: 0.1,
          },
          { label: 'UCL', data: Array(count).fill(data.r_ucl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0 },
          { label: 'R̄', data: Array(count).fill(data.r_cl), borderColor: 'green', pointRadius: 0 },
        ],
      },
    },
    ids,
    analysis: weco,
    rAnalysis: rWeco,
    statsSummary: summary,
    processCapability: pc,
    histogramData: histData,
    distributionStats: data.distribution_stats || null,
    cpkTrend: data.cpk_trend || [],
    stability: data.stability || null,
  };
};
