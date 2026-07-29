export type CalibrationWorkflowStatus =
  | 'draft'
  | 'in_progress'
  | 'ready_for_submission'
  | 'submitted'
  | 'rejected'
  | 'approved'
  | 'superseded'
  | 'voided';

export type CalibrationResult = 'pending' | 'pass' | 'fail' | 'limited_use';
export type CalibrationType = 'internal' | 'external';
export type CalibrationTemplateStatus = 'active' | 'inactive';
export type CalibrationTemplateVersionStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'superseded';

export interface CalibrationPage<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface CalibrationTemplatePoint {
  id: number;
  template_version_id: number;
  point_order: number;
  point_code: string;
  measurement_mode: string;
  nominal_value: string | null;
  unit: string;
  reference_input_mode: 'certified_value' | 'paired_reading';
  required_repetitions: number;
  error_lower_limit: string | null;
  error_upper_limit: string | null;
  evaluation_basis: string;
  repeatability_rule: string;
  repeatability_limit: string | null;
  qualification_scope_code: string | null;
  qualification_range_start: string | null;
  qualification_range_end: string | null;
  uncertainty_required: boolean;
  required: boolean;
}

export interface CalibrationTemplateVersion {
  id: number;
  template_id: number;
  version_no: number;
  procedure_code: string;
  procedure_name: string;
  procedure_description: string | null;
  default_repetitions: number;
  environment_requirements: Record<string, unknown>;
  allow_limited_use: boolean;
  status: CalibrationTemplateVersionStatus;
  row_version: number;
  revision_reason: string | null;
  created_by: number;
  created_at: string | null;
  submitted_by: number | null;
  submitted_at: string | null;
  approved_by: number | null;
  approved_at: string | null;
  approval_reason: string | null;
  rejection_reason: string | null;
  successor_version_id: number | null;
  points: CalibrationTemplatePoint[];
}

export interface CalibrationTemplateVersionSummary {
  id: number;
  version_no: number;
  procedure_code: string;
  procedure_name: string;
  status: CalibrationTemplateVersionStatus;
  row_version: number;
  approved_at: string | null;
}

export interface CalibrationTemplate {
  id: number;
  template_code: string;
  name: string;
  equipment_type: string;
  description: string | null;
  status: CalibrationTemplateStatus;
  current_approved_version_id: number | null;
  current_approved_version: CalibrationTemplateVersionSummary | null;
  versions?: CalibrationTemplateVersion[];
}

export interface CalibrationTemplateListParams {
  page: number;
  page_size: number;
  status?: CalibrationTemplateStatus;
  equipment_type?: string;
  search?: string;
}

export type CalibrationTemplatePointInput = Omit<
  CalibrationTemplatePoint,
  'id' | 'template_version_id'
>;

export interface CreateCalibrationTemplateInput {
  template_code: string;
  name: string;
  equipment_type: string;
  description?: string | null;
}

export interface CalibrationTemplateVersionInput {
  procedure_code: string;
  procedure_name: string;
  procedure_description?: string | null;
  default_repetitions: number;
  environment_requirements: Record<string, unknown>;
  allow_limited_use: boolean;
  revision_reason?: string | null;
  points: CalibrationTemplatePointInput[];
}

export interface UpdateCalibrationTemplateVersionInput
  extends Partial<CalibrationTemplateVersionInput> {
  templateId: number;
  versionId: number;
  expected_version: number;
}

export interface CalibrationReading {
  id: number;
  trial_no: number;
  standard_reading: string | null;
  indicated_value: string | null;
  effective_reference: string | null;
  error_value: string | null;
  correction_value: string | null;
  result: CalibrationResult;
  entered_by: number | null;
  entered_at: string | null;
  last_modified_by: number | null;
  last_modified_at: string | null;
  revision_reason: string | null;
}

export interface EquipmentCalibrationPoint {
  id: number;
  template_point_id: number;
  point_order: number;
  point_code: string;
  measurement_mode: string;
  nominal_value: string | null;
  unit: string;
  reference_value: string | null;
  error_lower_limit: string | null;
  error_upper_limit: string | null;
  evaluation_basis: string;
  repeatability_rule: string;
  repeatability_limit: string | null;
  qualification_scope_code: string | null;
  qualification_range_start: string | null;
  qualification_range_end: string | null;
  uncertainty_required: boolean;
  required: boolean;
  required_repetitions: number;
  average_value: string | null;
  error_value: string | null;
  repeatability_value: string | null;
  mean_error: string | null;
  mean_correction: string | null;
  minimum_error: string | null;
  maximum_error: string | null;
  error_range: string | null;
  sample_stddev: string | null;
  expanded_uncertainty: string | null;
  coverage_factor: string | null;
  completed_reading_count: number;
  result: CalibrationResult;
  remarks: string | null;
  readings: CalibrationReading[];
}

export interface CalibrationReferenceSnapshot {
  id: number;
  reference_standard_equipment_id: number;
  equipment_no: string;
  name: string;
  model: string | null;
  serial_no: string | null;
  range_min: string | null;
  range_max: string | null;
  resolution: string | null;
  unit: string | null;
  calibration_date: string | null;
  certificate_no: string | null;
  calibration_due_date: string | null;
  result: CalibrationResult;
  data_hash: string | null;
  traceability_standard: string | null;
  snapshot_data: Record<string, unknown>;
  created_at: string | null;
}

export interface CalibrationRecord {
  id: number;
  equipment_id: number;
  equipment_no: string | null;
  equipment_name: string | null;
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
  reference_standard_no: string | null;
  reference_standard_due_date: string | null;
  template_version_id: number;
  data_level: 'detailed' | 'summary_legacy';
  row_version: number;
  template_snapshot: Record<string, unknown>;
  environment_conditions: Record<string, unknown>;
  calculation_summary: Record<string, unknown>;
  calculation_version: string | null;
  data_hash: string | null;
  procedure_code: string;
  procedure_name: string;
  calibration_location: string | null;
  started_at: string | null;
  completed_at: string | null;
  reference_standard_equipment_id: number | null;
  submitted_by: number | null;
  submitted_at: string | null;
  rejection_reason: string | null;
  void_reason: string | null;
  successor_id: number | null;
  predecessor_id: number | null;
  certificate_attachment_id: number | null;
  status: CalibrationWorkflowStatus;
  created_by: number;
  created_at: string | null;
  approved_by: number | null;
  approved_at: string | null;
  points?: EquipmentCalibrationPoint[];
  reference_snapshots?: CalibrationReferenceSnapshot[];
}

export interface CalibrationListParams {
  page: number;
  page_size: number;
  status?: CalibrationWorkflowStatus;
  calibration_type?: CalibrationType;
  equipment_id?: number;
  search?: string;
  sort?: 'calibration_date' | 'created_at' | 'next_due_date';
  direction?: 'asc' | 'desc';
}

export interface CreateCalibrationInput {
  equipment_id: number;
  template_version_id: number;
  calibration_type: CalibrationType;
  calibration_date: string;
  reference_standard_equipment_id?: number | null;
  calibration_provider?: string | null;
  certificate_no?: string | null;
  traceability_standard?: string | null;
  uncertainty_statement?: string | null;
  calibration_location?: string | null;
  environment_conditions?: Record<string, unknown>;
}

export interface UpdateCalibrationInput {
  calibrationId: number;
  expected_version: number;
  calibration_date?: string;
  reference_standard_equipment_id?: number | null;
  calibration_provider?: string | null;
  certificate_no?: string | null;
  traceability_standard?: string | null;
  uncertainty_statement?: string | null;
  calibration_location?: string | null;
  environment_conditions?: Record<string, unknown>;
  certificate_attachment_id?: number | null;
}

export interface SaveCalibrationReadingsInput {
  calibrationId: number;
  expected_version: number;
  points: Array<{
    point_id: number;
    reference_value?: string | null;
    expanded_uncertainty?: string | null;
    coverage_factor?: string | null;
    remarks?: string | null;
    readings: Array<{
      trial_no: number;
      standard_reading?: string | null;
      indicated_value?: string | null;
      revision_reason?: string | null;
    }>;
  }>;
}

export interface CalibrationDecisionInput {
  calibrationId: number;
  expected_version: number;
  reason: string;
}

export interface CalibrationValidationResult {
  id: number;
  row_version: number;
  status: CalibrationWorkflowStatus;
  result: CalibrationResult;
  blockers: string[];
}
