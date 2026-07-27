/** MSA API 共用的 JSON 物件邊界；未經解析的來源欄位不得假設其結構。 */
export type MsaJsonObject = Record<string, unknown>;

export type EquipmentStatus = 'pending_review' | 'active' | 'maintenance' | 'inactive' | 'scrapped';
export type CalibrationType = 'internal' | 'external' | 'exempt';
export type CalibrationResult = 'pending' | 'pass' | 'fail' | 'limited_use';
export type CalibrationRecordStatus = 'draft' | 'approved';
export type CalibrationStatus = 'valid' | 'due_soon' | 'expired' | 'failed' | 'missing' | 'exempt';
export type EquipmentStatusEventType =
  | 'calibration_overdue'
  | 'calibration_failed'
  | 'maintenance'
  | 'major_adjustment'
  | 'inactive'
  | 'scrapped'
  | 'reactivated';

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
  traceability_standard: string | null;
  uncertainty_statement: string | null;
  result: CalibrationResult;
  applicable_modes: string[];
  restriction_conditions: string | null;
  approval_reason: string | null;
  certificate_attachment_id: number | null;
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
  sort: 'equipment_no' | 'name' | 'status' | 'updated_at';
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
  rows: EquipmentImportRow[];
}

export type EquipmentImportBatchSummary = Omit<EquipmentImportBatch, 'rows'>;

export interface EquipmentImportHistoryParams {
  page: number;
  page_size: number;
}

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
}
