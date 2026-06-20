export interface SpcViolation {
  label: string;
  reasons: string[];
  type: 'xbar' | 'r';
}

export interface ProcessCapability {
  available: boolean;
  reason?: string;
  usl?: number;
  lsl?: number;
  one_sided?: 'upper' | 'lower' | null;
  cp?: number;
  cpk?: number;
  cpu?: number;
  cpl?: number;
  pp?: number;
  ppk?: number;
  ppu?: number;
  ppl?: number;
  sigma_within?: number;
  sigma_overall?: number;
  valid_count?: number;
  ppm?: {
    upper: number;
    lower: number;
    total: number;
  };
}

export interface DistributionStats {
  skewness?: number;
  kurtosis?: number;
  normality?: 'good' | 'moderate' | 'poor';
  normality_label?: string;
}

export interface CpkTrend {
  month: string;
  cpk: number;
  count: number;
}

export interface ToleranceLimits {
  USL?: number | null;
  LSL?: number | null;
  公差上限?: number | null;
  公差下限?: number | null;
  尺寸上限?: number | null;
  尺寸下限?: number | null;
  found: boolean;
}

export interface SpcChartData {
  labels: string[];
  ids: string[];
  dates: string[];
  avgs: number[];
  ranges: number[];
  subgroup_sizes: number[];
  all_values: number[];
  x_cl: number;
  x_ucl: number;
  x_lcl: number;
  r_cl: number;
  r_ucl: number;
  r_lcl: number;
  avg_subgroup_size: number;
  tolerance: ToleranceLimits;
  process_capability: ProcessCapability;
  distribution_stats: DistributionStats;
  cpk_trend: CpkTrend[];
}

export interface HistogramBin {
  label: string;
  count: number;
  min: number;
  max: number;
  midpoint: number;
}
