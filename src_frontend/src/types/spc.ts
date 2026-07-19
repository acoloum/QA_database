export type SpcChartType = 'xbar_s' | 'xbar_r' | 'i_mr';
export type SpcChartKind = 'location' | 'variation';

export interface SpcReason {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface SpcViolation {
  label: string;
  reasons: string[];
  type: 'xbar' | 'r';
  chart_kind?: SpcChartKind;
  index?: number;
  window_start?: number;
  window_end?: number;
}

export interface SpcChartSeries {
  statistic: 'xbar' | 's' | 'r' | 'individual' | 'mr' | string;
  values: (number | null)[];
  cl: number[];
  ucl: number[];
  lcl: number[];
}

export interface SpcChartSet {
  chart_type: SpcChartType;
  location: SpcChartSeries;
  variation: SpcChartSeries;
  subgroup_sizes: number[];
  sigma_within: number;
  variation_source_pairs?: Array<Record<string, number[]> | null>;
}

export interface SpcStabilityViolation {
  index: number;
  window_start: number;
  window_end: number;
  rule: string;
  label: string;
  chart_kind: SpcChartKind;
}

export interface SpcChartStability {
  evaluated: boolean;
  stable: boolean | null;
  violations: SpcStabilityViolation[];
  rules_used: string[];
  chart_kind: SpcChartKind;
}

export interface SpcStability {
  evaluated: boolean;
  stable: boolean | null;
  violations: SpcStabilityViolation[];
  rules_used: string[];
  location?: SpcChartStability;
  variation?: SpcChartStability;
  reason_code?: string;
}

export interface SpcDistributionCandidate {
  model: string;
  params: number[];
  statistic: number;
  p_value: number;
  method: string;
  accepted: boolean;
  reason_code: string | null;
}

export interface SpcDistributionAssessment {
  model: string | null;
  label: string;
  params: number[];
  accepted: boolean;
  normal_ok: boolean;
  unimodal: boolean;
  reason_code: string | null;
  candidates: SpcDistributionCandidate[];
  fit_method: string | null;
  alpha: number;
  n?: number;
  ad_stat?: number | null;
}

export interface SpcTimeModel {
  candidate: 'A1' | 'A2' | 'B' | 'C1' | 'C2' | 'C3' | 'C4' | 'D' | null;
  candidate_options?: string[];
  model?: 'A1' | 'A2' | null;
  confirmed: boolean;
  statistically_controlled: boolean;
  reason_code?: string | null;
  evidence?: Record<string, unknown>;
  confirmed_by?: number;
  confirmed_at?: string;
  confirmation_reason?: string;
}

export interface SpcApplicability {
  applicable: boolean;
  chart_type?: SpcChartType;
  reason_code?: string | null;
  message?: string;
  reasons?: SpcReason[];
}

export interface ProcessCapability {
  available: boolean;
  reason?: string;
  capability_reason?: string | null;
  usl?: number;
  lsl?: number;
  one_sided?: 'upper' | 'lower' | null;
  cp?: number | null;
  cpk?: number | null;
  cpu?: number | null;
  cpl?: number | null;
  pp?: number | null;
  ppk?: number | null;
  ppu?: number | null;
  ppl?: number | null;
  sigma_within?: number;
  sigma_overall?: number;
  valid_count?: number;
  ppm?: { upper: number | null; lower: number | null; total: number | null };
  applicable?: 'capability' | 'performance';
  method?: 'G' | 'Z';
  cw?: number | null;
  cwk?: number | null;
  stability_stable?: boolean | null;
  targets?: SpcTargets;
  achieved?: boolean;
  preliminary?: boolean;
  time_model?: SpcTimeModel;
  distribution?: SpcDistributionAssessment;
}

export interface SpcTargets {
  class: string;
  confidence: string;
  base_p_target: number;
  base_pk_target: number;
  p_target: number;
  pk_target: number;
  adjusted: boolean;
  insufficient_sample: boolean;
}

export interface DistributionStats {
  skewness?: number;
  kurtosis?: number;
  normality?: 'good' | 'moderate' | 'poor';
  normality_label?: string;
  model?: string;
  model_label?: string;
}

export interface CpkTrend { month: string; cpk: number; count: number }

export interface ToleranceLimits {
  USL?: number | null;
  LSL?: number | null;
  公差上限?: number | null;
  公差下限?: number | null;
  尺寸上限?: number | null;
  尺寸下限?: number | null;
  found: boolean;
  characteristic_class?: string;
  [key: string]: unknown;
}

export interface SpcStudySample {
  id: number;
  key: string;
  order: number;
  timestamp: string | null;
  values: number[];
  distribution_values: number[];
  record_ids: number[];
  measurement_ids: number[];
  exclusion_snapshot: Array<{
    measurement_id: number;
    excluded: boolean;
    reason: string | null;
  }>;
}

export interface SpcOcapRecord {
  id: number;
  event_id: number;
  investigation_6m: Record<string, unknown> | null;
  remeasurement: Record<string, unknown> | null;
  process_adjustment: string | null;
  product_disposition: string | null;
  owner_id: number | null;
  effectiveness: string | null;
  status: string;
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface SpcAssignee {
  id: number;
  username: string;
  role: 'qa_supervisor' | 'qc_manager' | 'admin';
  role_name: string;
}

export interface SpcEventSummary {
  id: number;
  limit_version_id: number;
  study_version_id: number;
  sample_id: number | null;
  chart_kind: SpcChartKind;
  rule_code: string;
  point_index: number;
  source_point_key?: string | null;
  observed_value: number | null;
  status: string;
  created_at: string;
  ocap: SpcOcapRecord | null;
}

export interface SpcLimitVersionSummary {
  id: number;
  study_version_id: number;
  revision: number;
  chart_type: SpcChartType;
  limits: Record<string, unknown>;
  status: 'active' | 'retired';
  reason?: string | null;
  audit_incomplete?: boolean;
  approved_by: number | null;
  approved_at: string | null;
  effective_at?: string | null;
  retired_by?: number | null;
  retired_at?: string | null;
  events: SpcEventSummary[];
}

export interface SpcStudyResult {
  id: number;
  study_id: number;
  source: 'shipping' | 'patrol';
  study_type: 'retrospective' | 'ongoing';
  process_stream_key: string;
  filters: Record<string, unknown>;
  version_no: number;
  method_version: string;
  code_version: string | null;
  data_hash: string;
  specification: ToleranceLimits;
  charts: SpcChartSet | null;
  stability: SpcStability;
  distribution: SpcDistributionAssessment;
  time_model: SpcTimeModel;
  capability: ProcessCapability;
  applicability: SpcApplicability;
  status: 'draft' | 'submitted' | 'approved' | 'active' | 'retired' | 'rejected' | 'superseded' | 'legacy_imported';
  audit_incomplete: boolean;
  created_by: number | null;
  created_at: string;
  samples?: SpcStudySample[];
  limit_versions?: SpcLimitVersionSummary[];
  monitoring_limit?: SpcLimitVersionSummary | null;
}

export type SpcStudyVersionSummary = Omit<SpcStudyResult, 'samples'>;

export interface SpcStudySummary {
  id: number;
  source: 'shipping' | 'patrol';
  study_type: 'retrospective' | 'ongoing';
  process_stream_key: string;
  characteristic: string;
  filters: Record<string, unknown>;
  msa_status: string | null;
  sampling_note: string | null;
  status: string;
  legacy_limit_id: number | null;
  created_by: number | null;
  created_at: string;
  latest_version: SpcStudyVersionSummary | null;
  versions?: SpcStudyResult[];
}

/** 舊頁面過渡契約；權威資料位於 charts/stability/distribution/capability。 */
export interface SpcChartData {
  schema_version?: string;
  labels: string[];
  ids: string[];
  dates: string[];
  avgs: number[];
  ranges: (number | null)[];
  subgroup_sizes: number[];
  all_values: number[];
  x_cl: number | null;
  x_ucl: number | null;
  x_lcl: number | null;
  r_cl: number | null;
  r_ucl: number | null;
  r_lcl: number | null;
  x_cls?: number[];
  x_ucls?: number[];
  x_lcls?: number[];
  r_cls?: number[];
  r_ucls?: number[];
  r_lcls?: number[];
  avg_subgroup_size: number | null;
  tolerance: ToleranceLimits;
  process_capability: ProcessCapability;
  distribution_stats: DistributionStats;
  cpk_trend: CpkTrend[];
  charts?: SpcChartSet | null;
  stability?: SpcStability;
  distribution?: SpcDistributionAssessment;
  time_model?: SpcTimeModel;
  capability?: ProcessCapability;
  applicability?: SpcApplicability;
  study_version?: SpcStudyVersionSummary | null;
  process_stream_key?: string;
  data_hash?: string;
  characteristic_class?: string;
  excluded_count?: number;
  limits_frozen?: boolean;
}

export interface HistogramBin {
  label: string;
  count: number;
  min: number;
  max: number;
  midpoint: number;
}
