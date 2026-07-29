import type { CalibrationWorkflowStatus } from './calibration';

/** MSA API 共用的 JSON 物件邊界；未經解析的來源欄位不得假設其結構。 */
export type MsaJsonObject = Record<string, unknown>;

export type EquipmentStatus = 'pending_review' | 'active' | 'maintenance' | 'inactive' | 'scrapped';
export type CalibrationType = 'internal' | 'external' | 'exempt';
export type CalibrationResult = 'pending' | 'pass' | 'fail' | 'limited_use';
export type CalibrationRecordStatus = CalibrationWorkflowStatus;
export type CalibrationStatus = 'valid' | 'due_soon' | 'expired' | 'failed' | 'missing' | 'exempt';
export type EquipmentStatusEventType =
  | 'calibration_overdue'
  | 'calibration_failed'
  | 'maintenance'
  | 'major_adjustment'
  | 'inactive'
  | 'scrapped'
  | 'reactivated'
  | 'review_completed';

/** 後端將 Decimal 序列化為固定小數文字。 */
export type MsaDecimal = string;

export interface MeasurementEquipment {
  id: number;
  equipment_no: string;
  name: string;
  equipment_type: string | null;
  manufacturer: string | null;
  model: string | null;
  serial_no: string | null;
  range_min: MsaDecimal | null;
  range_max: MsaDecimal | null;
  resolution: MsaDecimal | null;
  unit: string | null;
  department: string | null;
  location: string | null;
  custodian: string | null;
  status: EquipmentStatus;
  calibration_type: CalibrationType | null;
  calibration_exemption_reason: string | null;
  calibration_interval_months: number | null;
  calibration_status: CalibrationStatus;
  next_calibration_date: string | null;
  calibration_block_reason: string | null;
  is_reference_standard: boolean;
  affects_product_decision: boolean;
  created_by: number | null;
  created_at: string;
  updated_by: number | null;
  updated_at: string;
}

export interface EquipmentCorrectionPoint {
  id: number;
  measurement_mode: string | null;
  nominal_value: MsaDecimal;
  indicated_value: MsaDecimal;
  error_value: MsaDecimal | null;
  correction_value: MsaDecimal | null;
  unit: string | null;
  range_start: MsaDecimal | null;
  range_end: MsaDecimal | null;
}

export interface EquipmentCalibration {
  id: number;
  equipment_id: number;
  calibration_type: CalibrationType;
  calibration_date: string;
  effective_date: string | null;
  next_due_date: string | null;
  calibration_provider: string | null;
  certificate_no: string | null;
  reference_standard_no: string | null;
  reference_standard_due_date: string | null;
  traceability_standard: string | null;
  uncertainty_statement: string | null;
  result: CalibrationResult;
  applicable_modes: string[];
  restriction_conditions: string | null;
  approval_reason: string | null;
  certificate_attachment_id: number | null;
  data_level: 'summary_legacy' | 'detailed';
  status: CalibrationRecordStatus;
  created_by: number | null;
  created_at: string;
  approved_by: number | null;
  approved_at: string | null;
  correction_points: EquipmentCorrectionPoint[];
}

export interface EquipmentStatusEvent {
  id: number;
  equipment_id: number;
  event_type: EquipmentStatusEventType;
  occurred_at: string;
  reason: string | null;
  created_by: number | null;
  triggers_msa_restudy: boolean;
  previous_status?: EquipmentStatus;
  target_status?: EquipmentStatus;
}

export interface EquipmentLink {
  id: number;
  equipment_id: number;
  source_module: 'pyrometry';
  source_entity_type: 'Recorder' | 'Thermocouple';
  source_entity_id: number;
  is_current: boolean;
  status: 'current' | 'retired';
}

export interface MeasurementEquipmentDetail extends MeasurementEquipment {
  calibrations: EquipmentCalibration[];
  status_events: EquipmentStatusEvent[];
  links: EquipmentLink[];
}

export interface MsaPage<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface EquipmentListParams {
  page: number;
  page_size: number;
  sort: 'equipment_no' | 'name' | 'status' | 'updated_at' | 'risk';
  order?: 'asc' | 'desc';
  status?: EquipmentStatus;
  calibration_status?: CalibrationStatus;
  q?: string;
  as_of?: string;
}

export interface CreateMsaEquipmentInput {
  equipment_no: string;
  name: string;
  equipment_type?: string | null;
  manufacturer?: string | null;
  model?: string | null;
  serial_no?: string | null;
  range_min?: number | string | null;
  range_max?: number | string | null;
  resolution?: number | string | null;
  unit?: string | null;
  department?: string | null;
  location?: string | null;
  custodian?: string | null;
  status?: EquipmentStatus;
  calibration_type?: CalibrationType | null;
  calibration_exemption_reason?: string | null;
  calibration_interval_months?: number | null;
  is_reference_standard?: boolean;
  affects_product_decision?: boolean;
}

export type UpdateMsaEquipmentInput = Omit<CreateMsaEquipmentInput, 'equipment_no' | 'status'>;

export interface EquipmentCorrectionPointInput {
  measurement_mode?: string | null;
  nominal_value: number | string;
  indicated_value: number | string;
  error_value?: number | string | null;
  correction_value?: number | string | null;
  unit?: string | null;
  range_start?: number | string | null;
  range_end?: number | string | null;
}

export interface CreateMsaCalibrationInput {
  calibration_type: CalibrationType;
  calibration_date: string;
  effective_date?: string | null;
  next_due_date?: string | null;
  calibration_provider?: string | null;
  certificate_no?: string | null;
  reference_standard_no?: string | null;
  reference_standard_due_date?: string | null;
  traceability_standard?: string | null;
  uncertainty_statement?: string | null;
  result: CalibrationResult;
  applicable_modes?: string[];
  restriction_conditions?: string | null;
  certificate_attachment_id?: number | null;
  correction_points: EquipmentCorrectionPointInput[];
}

export interface MsaStatusEventInput {
  equipmentId: number;
  event_type: EquipmentStatusEventType;
  expected_status: EquipmentStatus;
  target_status: EquipmentStatus;
  occurred_at?: string;
  reason: string;
  triggers_msa_restudy?: boolean;
}

export interface ApproveMsaCalibrationInput {
  calibrationId: number;
  equipmentId: number;
  expected_status: 'draft';
  reason: string;
  certificate_attachment_id?: number;
}

interface CreateMsaEquipmentLinkBase {
  equipmentId: number;
  source_module: 'pyrometry';
  source_entity_type: 'Recorder' | 'Thermocouple';
  source_entity_id: number;
}

export type CreateMsaEquipmentLinkInput =
  | (CreateMsaEquipmentLinkBase & {
    is_current?: true;
    expected_current_link_id: number | null;
  })
  | (CreateMsaEquipmentLinkBase & {
    is_current: false;
    expected_current_link_id?: never;
  });

export interface RetireMsaEquipmentLinkInput {
  equipmentId: number;
  linkId: number;
  expected_link_id: number;
  expected_status: 'current';
}

export type EquipmentImportAction = 'accept' | 'pending_review' | 'reject';

export interface EquipmentImportResolution {
  action?: EquipmentImportAction;
  calibration_type?: CalibrationType;
  calibration_exemption_reason?: string;
  resolution?: number | string;
  unit?: string;
  model?: string;
  serial_no?: string;
  custodian?: string;
}

export interface EquipmentImportRow {
  id: number;
  source_row_no: number;
  raw: MsaJsonObject;
  normalized: MsaJsonObject | null;
  issue_codes: string[];
  issue_description: string | null;
  equipment_id: number | null;
  confirmed_by: number | null;
  confirmed_at: string | null;
}

/** CSV 盤點的來源統計型別；目前批次 serializer 僅回傳其總列數與確認計數。 */
export interface EquipmentImportInspectionStatistics {
  total_rows: number;
  status_counts: Record<string, number>;
  serial_review_candidates: number;
  serials_auto_extracted: number;
  html_cleaned_rows: number;
  ambiguous_calibration_rows: number;
  active_expired_rows: number;
}

export interface EquipmentImportBatch {
  id: number;
  original_filename: string;
  file_sha256: string;
  file_size: number;
  status: 'previewed' | 'confirmed';
  total_rows: number;
  success_rows: number;
  pending_rows: number;
  rejected_rows: number;
  parser_version: string;
  uploaded_by: number | null;
  uploaded_at: string | null;
  rows_total: number;
  row_page: number;
  row_page_size: number;
  rows: EquipmentImportRow[];
}

export type EquipmentImportBatchSummary = Omit<
  EquipmentImportBatch,
  'rows' | 'rows_total' | 'row_page' | 'row_page_size'
>;

export interface EquipmentImportHistoryParams {
  page: number;
  page_size: number;
}

export interface EquipmentImportRowPageParams {
  row_page: number;
  row_page_size: number;
}

export type MeasurementEquipmentMutationResult = Omit<
  MeasurementEquipment,
  'calibration_status' | 'next_calibration_date' | 'calibration_block_reason'
>;

export interface PreviewMsaEquipmentImportInput {
  file: File;
  as_of?: string;
}

export interface ConfirmMsaEquipmentImportInput {
  batchId: number;
  resolutions: Record<number, EquipmentImportResolution>;
  confirmation_date?: string;
}

export interface MsaCriteriaListParams {
  page: number;
  page_size: number;
  sort: 'id' | 'name';
  order?: 'asc' | 'desc';
}

export interface MsaCriteriaVersion {
  id: number;
  profile_id: number;
  version_no: number;
  method_version: string;
  effective_date: string;
  thresholds: Record<string, number>;
  stability_rules: MsaJsonObject;
  conditional_actions: string[];
  basis: string | null;
  status: 'draft' | 'approved';
  is_current: boolean;
  created_by: number | null;
  created_at: string;
  approved_by: number | null;
  approved_at: string | null;
}

export interface MsaCriteriaProfileSummary {
  id: number;
  name: string;
  customer_scope: string | null;
  product_scope: string | null;
  product_family_scope: string | null;
  characteristic_scope: string | null;
  characteristic_importance: string | null;
  applicable_study_types: string[];
  current_version_id: number | null;
}

export interface MsaCriteriaProfile extends MsaCriteriaProfileSummary {
  versions: MsaCriteriaVersion[];
}

export interface CreateMsaCriteriaProfileInput {
  name: string;
  customer_scope?: string | null;
  product_scope?: string | null;
  product_family_scope?: string | null;
  characteristic_scope?: string | null;
  characteristic_importance?: string | null;
  applicable_study_types?: string[];
}

export interface CreateMsaCriteriaVersionInput {
  profileId: number;
  method_version?: string;
  effective_date?: string;
  thresholds?: Record<string, number>;
  stability_rules?: MsaJsonObject;
  conditional_actions?: string[];
  basis?: string;
}

export interface ApproveMsaCriteriaVersionInput {
  versionId: number;
  expected_status: 'draft';
  /** 核准理由；只寫入稽核紀錄，不進入不可變的準則快照 */
  reason?: string;
}

// ---------------------------------------------------------------------------
// 研究、計畫、觀測、結果與再研究
// ---------------------------------------------------------------------------

export type MsaStudyType =
  | 'grr_range' | 'grr_xbar_r' | 'grr_anova' | 'bias'
  | 'linearity' | 'stability' | 'attribute' | 'nonreplicable';

export type MsaStudyStatus =
  | 'draft' | 'ready' | 'collecting' | 'ready_for_analysis'
  | 'analyzed' | 'submitted' | 'approved' | 'rejected'
  | 'voided' | 'superseded';

export type MsaMeasurementPurpose = 'product_control' | 'process_control';

export type MsaPercentBasis =
  | 'tolerance' | 'study_variation' | 'process_variation';

export type MsaDisposition =
  | 'acceptable' | 'conditionally_acceptable'
  | 'unacceptable' | 'indeterminate';

export interface MsaStudy {
  id: number;
  study_no: string;
  study_type: MsaStudyType;
  measurement_purpose: MsaMeasurementPurpose;
  characteristic: string;
  unit: string;
  lsl: string | null;
  usl: string | null;
  no_tolerance_reason: string | null;
  process_sigma: string | null;
  criteria_profile_id: number | null;
  responsible_user_id: number | null;
  primary_executor_id: number | null;
  status: MsaStudyStatus;
  current_plan_version_id: number | null;
  current_result_version_id: number | null;
  previous_approved_study_id: number | null;
  next_due_date: string | null;
  created_by_id: number | null;
  created_at: string;
  updated_by_id: number | null;
  updated_at: string;
}

export interface MsaStudyListParams {
  page: number;
  page_size: number;
  sort: 'id' | 'study_no' | 'updated_at';
  order?: 'asc' | 'desc';
  status?: MsaStudyStatus;
}

export interface CreateMsaStudyInput {
  study_type: MsaStudyType;
  measurement_purpose: MsaMeasurementPurpose;
  characteristic: string;
  unit: string;
  lsl?: number | null;
  usl?: number | null;
  no_tolerance_reason?: string | null;
  process_sigma?: number | null;
  criteria_profile_id?: number | null;
  responsible_user_id?: number | null;
  primary_executor_id?: number | null;
}

export interface UpdateMsaStudyInput extends Partial<CreateMsaStudyInput> {
  studyId: number;
  /** 畫面載入時的 updated_at；後端據此偵測他人已更新 */
  expected_updated_at: string;
}

export interface MsaPlanVersion {
  id: number;
  study_id: number;
  plan_version_no: number;
  method_code: string;
  method_version: string;
  design_type: string;
  part_count: number;
  appraiser_count: number;
  trial_count: number;
  random_seed: number;
  category_set: string[];
  sampling_notes: string | null;
  environment_notes: string | null;
  equipment_snapshot: MsaJsonObject;
  criteria_snapshot: MsaJsonObject;
  plan_hash: string | null;
  frozen_by_id: number | null;
  frozen_at: string | null;
  part_blind_codes: string[];
  appraiser_blind_codes: string[];
}

export interface CreateMsaPlanInput {
  studyId: number;
  method_code: string;
  part_count: number;
  appraiser_count: number;
  trial_count: number;
  random_seed: number;
  design_type?: string;
  percent_basis?: MsaPercentBasis;
  category_set?: string[];
  sampling_notes?: string;
  environment_notes?: string;
  equipment: Array<{
    equipment_id: number;
    role: 'primary_gauge' | 'reference_standard' | 'fixture' | 'auxiliary';
    measurement_mode?: string;
    note?: string;
  }>;
  parts: Array<{
    part_identifier?: string;
    reference_value?: string | number;
    reference_uncertainty?: string | number;
    reference_category?: string;
    note?: string;
  }>;
  appraisers: Array<{
    name: string;
    user_id?: number;
    qualification?: string;
  }>;
}

/** 盲測任務只帶盲碼，不含真實件號、參考值或他人讀值 */
export interface MsaBlindTask {
  requested_order: number;
  part_blind_code: string | null;
  appraiser_blind_code: string | null;
  trial_no: number;
  recorded: boolean;
}

export interface MsaObservation {
  id: number;
  plan_version_id: number;
  requested_order: number;
  actual_entry_order: number;
  trial_no: number;
  numeric_value: string | null;
  attribute_value: string | null;
  measured_at: string | null;
  source: 'page_single' | 'page_matrix' | 'excel_import';
  entered_by_id: number;
  is_effective: boolean;
  supersedes_id: number | null;
  correction_reason: string | null;
}

export interface RecordMsaObservationInput {
  planId: number;
  task_order: number;
  numeric_value?: string;
  attribute_value?: string;
  measured_at?: string;
}

export interface CorrectMsaObservationInput {
  observationId: number;
  reason: string;
  numeric_value?: string;
  attribute_value?: string;
}

export interface MsaCompletenessReport {
  plan_version_id: number;
  plan_hash: string | null;
  expected: number;
  recorded: number;
  missing: Array<{ requested_order: number; trial_no: number }>;
  complete: boolean;
}

export interface MsaObservationImportIssue {
  sheet: string;
  row: number;
  cell: string;
  code: string;
  message: string;
}

export interface MsaObservationImportBatch {
  id: number;
  plan_version_id: number;
  file_name: string;
  file_sha256: string;
  plan_hash: string | null;
  status: 'previewed' | 'confirmed' | 'rejected';
  issues: MsaObservationImportIssue[];
  stats: MsaJsonObject;
}

export interface MsaConclusion {
  statistical_result: MsaJsonObject;
  system_disposition: MsaDisposition;
  /** 人工工程判斷只能附加，永遠不覆寫統計結果 */
  engineering_judgment: string | null;
  reasons: string[];
  percent_basis: MsaPercentBasis | null;
}

export interface MsaResultVersion {
  id: number;
  study_id: number;
  plan_version_id: number;
  result_version_no: number;
  method_code: string;
  method_version: string;
  code_version: string;
  data_hash: string;
  applicability_result: MsaJsonObject;
  statistics: MsaJsonObject;
  chart_data: MsaJsonObject;
  criteria_snapshot: MsaJsonObject;
  conclusion: MsaConclusion;
  warnings: Array<{ code: string; message: string }>;
  blockers: Array<{ code: string; message: string }>;
  status:
    | 'analyzed' | 'submitted' | 'approved'
    | 'rejected' | 'voided' | 'superseded';
  created_by_id: number | null;
  created_at: string;
}

export interface MsaWorkflowActionInput {
  resultId: number;
  expected_status: MsaResultVersion['status'];
  reason: string;
  actions?: string[];
  due_date?: string;
}

export interface MsaRestudyRequest {
  id: number;
  source_study_id: number;
  trigger_type: string;
  source_entity_type: string;
  source_entity_id: number | null;
  trigger_payload: MsaJsonObject;
  due_date: string | null;
  status: 'open' | 'in_progress' | 'completed' | 'dismissed';
  new_study_id: number | null;
  created_by_id: number | null;
  created_at: string;
}
