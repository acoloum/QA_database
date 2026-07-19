export type SpcChartType = 'xbar_s' | 'xbar_r' | 'i_mr' | 'p' | 'np';
export type SpcVariableChartType = Exclude<SpcChartType, 'p' | 'np'>;
export type SpcAnalysisFamily = 'variable' | 'attribute' | 'machine';
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
  chart_type: SpcVariableChartType;
  location: SpcChartSeries;
  variation: SpcChartSeries;
  subgroup_sizes: number[];
  sigma_within: number;
  variation_source_pairs?: Array<Record<string, number[]> | null>;
}

/** 屬性型 p／np 圖的逐子組可追溯計數。 */
export interface SpcAttributeCount {
  key: string;
  inspected: number;
  nonconforming: number;
  proportion: number;
}

/** 後端 2026.2 屬性圖結果；界限必須逐點保留，不可重複套用固定值。 */
export interface SpcAttributeChartData {
  chart_type: Extract<SpcChartType, 'p' | 'np'>;
  values: number[];
  cl: number[];
  ucl: number[];
  lcl: number[];
  n: number[];
  x: number[];
  counts?: SpcAttributeCount[];
  warnings?: Record<string, boolean>;
  exclusion_evidence?: Array<Record<string, unknown>>;
}

export const isSpcAttributeChartData = (
  charts: SpcChartSet | SpcAttributeChartData | null | undefined,
): charts is SpcAttributeChartData => charts?.chart_type === 'p' || charts?.chart_type === 'np';

export const isSpcChartSet = (
  charts: SpcChartSet | SpcAttributeChartData | null | undefined,
): charts is SpcChartSet => Boolean(charts && !isSpcAttributeChartData(charts));

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

export type SpcTransformationModel = 'boxcox' | 'johnson_su' | 'johnson_sb' | 'johnson_sl';

/** 後端轉換引擎保存的完整候選；具名參數不可退化成不具語意的陣列。 */
export interface SpcTransformationCandidate {
  model: SpcTransformationModel;
  label: string;
  params: Record<string, number>;
  epsilon: number;
  fit_method: string | null;
  ad_statistic: number | null;
  ad_p_value: number | null;
  tail_quantiles: number[];
  monotonic: boolean;
  roundtrip_relative_error: number | null;
  accepted: boolean;
  reason_code: string | null;
  rank: number | null;
  fit_error?: string;
}

export interface SpcTransformationEvidence {
  available: boolean;
  reason_code: string | null;
  n: number;
  minimum_sample_size: number;
  alpha: number;
  fit_bias_note: string;
}

export interface SpcTransformationDecision extends SpcTransformationCandidate {
  confirmed: true;
  confirmed_by: number;
  confirmed_at: string;
  confirmation_reason: string;
  original_model: string | null;
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
  scale?: 'original' | 'transformed';
  original_model?: string | null;
  original_distribution?: SpcDistributionAssessment;
  original_characteristic?: string;
  transformation_candidates?: SpcTransformationCandidate[];
  transformation_recommendation?: SpcTransformationCandidate | null;
  transformation_reason_code?: string | null;
  transformation_evidence?: SpcTransformationEvidence;
  transformation_decision?: SpcTransformationDecision | null;
}

export type SpcTimeModelCode = 'A1' | 'A2' | 'B' | 'C1' | 'C2' | 'C3' | 'C4' | 'D';

export interface SpcHolmEvidenceRow {
  raw_p_value: number;
  adjusted_p_value: number;
  threshold: number;
  reject: boolean;
  [key: string]: unknown;
}

export interface SpcTrendEvidence {
  method: string;
  indexes: number[];
  tau: number | null;
  slope: number | null;
  detected: boolean;
}

export interface SpcChangePointEvidence {
  method: string;
  min_segment: number;
  detected: boolean;
  change_points: number[];
  windows: SpcHolmEvidenceRow[];
}

export interface SpcVarianceChangeEvidence {
  method: string;
  min_segment: number;
  detected: boolean;
  change_indexes: number[];
  windows: SpcHolmEvidenceRow[];
}

export interface SpcRandomLocationEvidence {
  method: string;
  statistic: number | null;
  raw_p_value: number;
  adjusted_p_value: number;
  threshold: number;
  statistical_reject: boolean;
  omega_squared: number;
  effect_threshold: number;
  reject: boolean;
  subgroup_sizes: number[];
  grand_mean: number;
  ss_between: number;
  ss_within: number;
  df_between: number;
  df_within: number;
}

export interface SpcFormalStabilityChartEvidence {
  evaluated: boolean;
  stable: boolean | null;
  rules_used: string[];
  violations: SpcStabilityViolation[];
}

export interface SpcFormalStabilityEvidence {
  evaluated: boolean;
  stable: boolean | null;
  rules_used: string[];
  location: SpcFormalStabilityChartEvidence;
  variation: SpcFormalStabilityChartEvidence;
}

export interface SpcInstantaneousDistributionEvidence {
  available: boolean;
  accepted: boolean;
  unimodal: boolean;
  normal: boolean | null;
  method?: string;
  statistic?: number | null;
  p_value?: number;
  adjusted_p_value?: number;
  threshold?: number;
  residual_scale?: number;
  sample_count?: number;
  acceptance_method?: string;
  reason_code: string | null;
}

export interface SpcAggregateModalityEvidence {
  available: boolean;
  method?: string;
  grid_points?: number;
  bandwidth?: number;
  peak_indexes?: number[];
  peak_values?: number[];
  peak_threshold?: number;
  peak_count?: number;
  unimodal?: boolean;
  reason_code?: string;
}

export interface SpcAggregateNormalityEvidence {
  available: boolean;
  method?: string;
  p_value?: number | null;
  threshold?: number;
  normal?: boolean;
  reason_code?: string;
}

export interface SpcTimeDiagnosticEvidence {
  subgroup_count: number;
  minimum_subgroups?: number;
  trend?: SpcTrendEvidence;
  change_points?: SpcChangePointEvidence;
  variance_change?: SpcVarianceChangeEvidence;
  random_location?: SpcRandomLocationEvidence;
  formal_stability?: SpcFormalStabilityEvidence;
  instantaneous_distribution?: SpcInstantaneousDistributionEvidence;
  aggregate_modality?: SpcAggregateModalityEvidence;
  aggregate_normality?: SpcAggregateNormalityEvidence;
  aggregate_distribution?: SpcDistributionAssessment;
  multiple_testing?: { method: 'Holm' | string; families: Record<string, SpcHolmEvidenceRow[]> };
  thresholds?: Record<string, number>;
}

export interface SpcTimeModel {
  candidate: SpcTimeModelCode | null;
  candidate_options?: SpcTimeModelCode[];
  model?: SpcTimeModelCode | null;
  system_candidate?: SpcTimeModelCode;
  overridden?: boolean;
  confirmed: boolean;
  statistically_controlled: boolean;
  diagnostic_version?: string;
  alpha?: number;
  reason_code?: string | null;
  evidence?: SpcTimeDiagnosticEvidence;
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
  eligibility?: Record<string, unknown>;
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
  scale?: 'original' | 'transformed';
  transformed_specification?: ToleranceLimits;
  original_scale?: {
    scale: 'original';
    quantiles: number[];
    ppm: { upper: number | null; lower: number | null; total: number | null };
    model: SpcTransformationModel | null;
    transformed_distribution_params: number[];
  };
  transformation_decision?: SpcTransformationDecision;
}

/** 機器績效研究的後端結果；不與製程 Cp/Cpk 共用欄位。 */
export interface MachineStudyEvidence {
  source_semantics: 'patrol_min_max_observations' | string | null;
  operators: number[];
  record_ids: number[];
  detail_ids: number[];
  date_span: { start: string | null; end: string | null };
  conditions_confirmed: boolean;
  condition_reason: string | null;
}

export interface MachinePerformanceResult {
  available: boolean;
  approvable: boolean;
  preliminary: boolean;
  index_family: 'machine';
  method: 'G';
  n: number;
  reason_code: string | null;
  distribution: {
    model: string | null;
    label: string | null;
    accepted: boolean;
    reason_code: string | null;
  };
  quantiles: { q_0_135: number | null; q_50: number | null; q_99_865: number | null };
  usl: number | null;
  lsl: number | null;
  pm: number | null;
  pmu: number | null;
  pml: number | null;
  pmk: number | null;
  targets: { class: string; pm: number; pmk: number };
  evidence: MachineStudyEvidence;
}

export const isMachinePerformanceResult = (
  capability: ProcessCapability | MachinePerformanceResult | null | undefined,
): capability is MachinePerformanceResult => Boolean(capability && 'index_family' in capability && capability.index_family === 'machine');

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

export type SpcOcapStatus = 'open' | 'closed';

export interface SpcOcapRecord {
  id: number;
  event_id: number;
  investigation_6m: Record<string, unknown> | null;
  remeasurement: Record<string, unknown> | null;
  process_adjustment: string | null;
  product_disposition: string | null;
  owner_id: number | null;
  effectiveness: string | null;
  status: SpcOcapStatus;
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
  status: 'open' | 'investigating' | 'closed';
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
  analysis_family?: SpcAnalysisFamily;
  process_stream_key: string;
  filters: Record<string, unknown>;
  options?: Record<string, unknown>;
  version_no: number;
  method_version: string;
  code_version: string | null;
  data_hash: string;
  specification: ToleranceLimits;
  charts: SpcChartSet | SpcAttributeChartData | null;
  stability: SpcStability;
  distribution: SpcDistributionAssessment;
  time_model: SpcTimeModel;
  capability: ProcessCapability | MachinePerformanceResult;
  applicability: SpcApplicability;
  status: 'draft' | 'submitted' | 'approved' | 'active' | 'retired' | 'rejected' | 'superseded' | 'legacy_imported';
  audit_incomplete: boolean;
  created_by: number | null;
  created_at: string;
  samples?: SpcStudySample[];
  limit_versions?: SpcLimitVersionSummary[];
  monitoring_limit?: SpcLimitVersionSummary | null;
}

export const isVariableSpcStudyResult = (
  version: SpcStudyResult | null | undefined,
): version is SpcStudyResult & { analysis_family: 'variable' } => version?.analysis_family === 'variable';

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

export interface SpcStudyHistoryPage {
  items: SpcStudyVersionSummary[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
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
