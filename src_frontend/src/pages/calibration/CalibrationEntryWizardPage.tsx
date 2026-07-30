import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from 'react';
import { Link, useParams } from 'react-router';

import CalibrationConditionForm, {
  type EnvironmentValue,
} from '../../components/calibration/CalibrationConditionForm';
import CalibrationEvidenceReview from '../../components/calibration/CalibrationEvidenceReview';
import CalibrationReadingMatrix, {
  type CalibrationMatrixPoint,
  type CalibrationMatrixValues,
} from '../../components/calibration/CalibrationReadingMatrix';
import CalibrationStepper from '../../components/calibration/CalibrationStepper';
import {
  useCalibration,
  useCreateCalibration,
  useSaveCalibrationReadings,
  useSubmitCalibration,
  useUpdateCalibration,
  useValidateCalibration,
} from '../../hooks/useCalibrations';
import {
  useCalibrationTemplate,
  useCalibrationTemplates,
} from '../../hooks/useCalibrationTemplates';
import { useUploadAttachment } from '../../hooks/useAttachment';
import {
  useMsaEquipment,
  useMsaEquipmentDetail,
} from '../../hooks/useMsaEquipment';
import type {
  CalibrationRecord,
  CalibrationValidationResult,
  EquipmentCalibrationPoint,
} from '../../types/calibration';
import { ApiError, apiErrorMessage } from '../../services/apiError';
import './calibration.css';

const today = () => new Date().toISOString().slice(0, 10);

const pointValue = (
  values: CalibrationMatrixValues,
  pointCode: string,
  trialNo: number,
  field: 'standard' | 'indicated',
) => values[`${pointCode}:${trialNo}:${field}`]?.trim() || null;

export default function CalibrationEntryWizardPage() {
  const { equipmentId: routeEquipmentId } = useParams();
  const [equipmentId, setEquipmentId] = useState(
    /^\d+$/.test(routeEquipmentId ?? '') ? routeEquipmentId! : '',
  );
  const [equipmentSearch, setEquipmentSearch] = useState('');
  const [templateSearch, setTemplateSearch] = useState('');
  const [standardSearch, setStandardSearch] = useState('');
  const equipment = useMsaEquipment({
    page: 1,
    page_size: 100,
    sort: 'equipment_no',
    order: 'asc',
    q: equipmentSearch.trim() || undefined,
  });
  const routeEquipment = useMsaEquipmentDetail(
    equipmentId ? Number(equipmentId) : null,
  );
  const selectedEquipment = equipment.data?.items.find(
    (item) => item.id === Number(equipmentId),
  ) ?? routeEquipment.data;
  const equipmentOptions = selectedEquipment && !equipment.data?.items.some(
    (item) => item.id === selectedEquipment.id,
  )
    ? [selectedEquipment, ...(equipment.data?.items ?? [])]
    : (equipment.data?.items ?? []);
  const templates = useCalibrationTemplates({
    page: 1,
    page_size: 100,
    status: 'active',
    equipment_type: selectedEquipment?.equipment_type ?? undefined,
    search: templateSearch.trim() || undefined,
  });
  const standardEquipment = useMsaEquipment({
    page: 1,
    page_size: 100,
    sort: 'equipment_no',
    order: 'asc',
    status: 'active',
    calibration_status: 'valid',
    q: standardSearch.trim() || undefined,
  });
  const createCalibration = useCreateCalibration();
  const updateCalibration = useUpdateCalibration();
  const saveReadings = useSaveCalibrationReadings();
  const validateCalibration = useValidateCalibration();
  const submitCalibration = useSubmitCalibration();
  const uploadAttachment = useUploadAttachment();
  const [step, setStep] = useState(1);
  const [enabledThrough, setEnabledThrough] = useState(1);
  const [templateId, setTemplateId] = useState('');
  const [calibrationType, setCalibrationType] = useState<'internal' | 'external'>(
    'internal',
  );
  const [calibrationDate, setCalibrationDate] = useState(today());
  const [referenceId, setReferenceId] = useState('');
  const [provider, setProvider] = useState('');
  const [certificateNo, setCertificateNo] = useState('');
  const [location, setLocation] = useState('');
  const [record, setRecord] = useState<CalibrationRecord | null>(null);
  const recordDetail = useCalibration(record?.id ?? null);
  const [conditions, setConditions] = useState<
    Record<string, EnvironmentValue>
  >({});
  const [matrixValues, setMatrixValues] = useState<CalibrationMatrixValues>({});
  const [validation, setValidation] = useState<CalibrationValidationResult | null>(
    null,
  );
  const [submitReason, setSubmitReason] = useState('');
  const [dirty, setDirty] = useState(false);
  const [serverDirty, setServerDirty] = useState(false);
  const [pendingCertificateId, setPendingCertificateId] = useState<number | null>(
    null,
  );
  const certificateDirtyBaseline = useRef({
    dirty: false,
    serverDirty: false,
  });
  const [error, setError] = useState<string | null>(null);
  const selectedTemplate = useCalibrationTemplate(
    templateId ? Number(templateId) : null,
  );
  const approvedVersion = useMemo(() => {
    const approvedId = templates.data?.items.find(
      (item) => item.id === Number(templateId),
    )?.current_approved_version_id;
    return selectedTemplate.data?.versions?.find(
      (version) => version.id === approvedId && version.status === 'approved',
    ) ?? null;
  }, [selectedTemplate.data?.versions, templateId, templates.data?.items]);
  const availableTemplates = (templates.data?.items ?? []).filter(
    (template) => (
      !selectedEquipment
      || template.equipment_type === selectedEquipment.equipment_type
    ),
  );
  const standards = (standardEquipment.data?.items ?? []).filter(
    (item) => (
      item.is_reference_standard
      && item.status === 'active'
      && item.id !== Number(equipmentId)
    ),
  );
  const recordLocked = record != null && ![
    'draft',
    'in_progress',
    'ready_for_submission',
  ].includes(record.status);
  const hasPendingRequest = createCalibration.isPending
    || updateCalibration.isPending
    || saveReadings.isPending
    || validateCalibration.isPending
    || submitCalibration.isPending
    || uploadAttachment.isPending;
  const shouldWarnOnLeave = (
    dirty
    || pendingCertificateId != null
    || hasPendingRequest
  );
  const workflowInteractionLocked = (
    recordLocked
    || hasPendingRequest
    || pendingCertificateId != null
  );

  useEffect(() => {
    if (!shouldWarnOnLeave) return undefined;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    const warnHistory = () => {
      if (!window.confirm('尚有未保存變更，確定要離開嗎？')) {
        window.history.forward();
      }
    };
    const warnInternalLink = (event: MouseEvent) => {
      if (
        event.defaultPrevented
        || event.button !== 0
        || event.metaKey
        || event.ctrlKey
        || event.shiftKey
        || event.altKey
      ) return;
      const target = event.target;
      const anchor = target instanceof Element
        ? target.closest<HTMLAnchorElement>('a[href]')
        : null;
      const navigationAction = target instanceof Element
        ? target.closest<HTMLElement>('[data-navigation-action]')
        : null;
      if (navigationAction) {
        if (!window.confirm('尚有未保存變更，確定要離開嗎？')) {
          event.preventDefault();
          event.stopPropagation();
        }
        return;
      }
      if (
        !anchor
        || anchor.target === '_blank'
        || anchor.hasAttribute('download')
        || anchor.origin !== window.location.origin
      ) return;
      if (!window.confirm('尚有未保存變更，確定要離開嗎？')) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener('beforeunload', warn);
    window.addEventListener('popstate', warnHistory);
    document.addEventListener('click', warnInternalLink, true);
    return () => {
      window.removeEventListener('beforeunload', warn);
      window.removeEventListener('popstate', warnHistory);
      document.removeEventListener('click', warnInternalLink, true);
    };
  }, [shouldWarnOnLeave]);

  const mark = <T,>(setter: (value: T) => void) => (value: T) => {
    setter(value);
    setDirty(true);
    setError(null);
  };

  const createDraft = async () => {
    setError(null);
    if (!equipmentId || !templateId || !approvedVersion || !calibrationDate) {
      setError('受校設備、核准模板版本與校正日期為必填');
      return;
    }
    if (calibrationType === 'internal' && !referenceId) {
      setError('內校必須選擇參考標準器');
      return;
    }
    if (
      calibrationType === 'external'
      && (!provider.trim() || !certificateNo.trim())
    ) {
      setError('外校機構與證書編號為必填');
      return;
    }
    try {
      const created = await createCalibration.mutateAsync({
        equipment_id: Number(equipmentId),
        template_version_id: approvedVersion.id,
        calibration_type: calibrationType,
        calibration_date: calibrationDate,
        reference_standard_equipment_id: calibrationType === 'internal'
          ? Number(referenceId)
          : null,
        calibration_provider: provider.trim() || null,
        certificate_no: certificateNo.trim() || null,
        calibration_location: location.trim() || null,
        environment_conditions: {},
      });
      setRecord(created);
      setDirty(false);
      setServerDirty(false);
      setStep(2);
      setEnabledThrough(2);
    } catch (found) {
      setError(apiErrorMessage(found, '校正草稿未建立'));
    }
  };

  const saveConditions = async () => {
    if (!record || !approvedVersion) return;
    const requirements = approvedVersion.environment_requirements;
    for (const [key, rawRule] of Object.entries(requirements)) {
      const rule = (
        typeof rawRule === 'object' && rawRule !== null ? rawRule : {}
      ) as { required?: boolean };
      if (rule.required && !conditions[key]?.value.trim()) {
        setError(`必要環境條件 ${key} 尚未登錄`);
        return;
      }
    }
    try {
      const updated = await updateCalibration.mutateAsync({
        calibrationId: record.id,
        expected_version: record.row_version,
        calibration_location: location.trim() || null,
        environment_conditions: conditions,
      });
      setRecord(updated);
      setDirty(false);
      setServerDirty(false);
      setStep(3);
      setEnabledThrough(Math.max(enabledThrough, 3));
    } catch (found) {
      setError(apiErrorMessage(found, '環境條件未儲存'));
    }
  };

  const uploadCertificate = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !record) return;
    certificateDirtyBaseline.current = { dirty, serverDirty };
    setValidation(null);
    setDirty(true);
    setServerDirty(true);
    setError(null);
    let attachmentUploaded = false;
    try {
      const attachment = await uploadAttachment.mutateAsync({
        file,
        entity_type: 'equipment_calibration',
        entity_id: record.id,
        purpose: 'cert',
      });
      attachmentUploaded = true;
      setPendingCertificateId(attachment.id);
      const updated = await updateCalibration.mutateAsync({
        calibrationId: record.id,
        expected_version: record.row_version,
        certificate_attachment_id: attachment.id,
      });
      setRecord(updated);
      setPendingCertificateId(null);
      setDirty(certificateDirtyBaseline.current.dirty);
      setServerDirty(certificateDirtyBaseline.current.serverDirty);
    } catch (found) {
      if (!attachmentUploaded) {
        setDirty(certificateDirtyBaseline.current.dirty);
        setServerDirty(certificateDirtyBaseline.current.serverDirty);
      }
      setError(apiErrorMessage(found, '證書附件未綁定'));
    } finally {
      event.target.value = '';
    }
  };

  const retryCertificateBinding = async () => {
    if (!record || pendingCertificateId == null) return;
    setValidation(null);
    setDirty(true);
    setServerDirty(true);
    try {
      const refreshed = await recordDetail.refetch();
      const latest = refreshed.data ?? record;
      setRecord(latest);
      const updated = await updateCalibration.mutateAsync({
        calibrationId: latest.id,
        expected_version: latest.row_version,
        certificate_attachment_id: pendingCertificateId,
      });
      setRecord(updated);
      setPendingCertificateId(null);
      setDirty(certificateDirtyBaseline.current.dirty);
      setServerDirty(certificateDirtyBaseline.current.serverDirty);
      setError(null);
    } catch (found) {
      setError(apiErrorMessage(found, '證書附件重新綁定失敗'));
    }
  };

  const templatePointMap = new Map(
    (approvedVersion?.points ?? []).map((point) => [point.point_code, point]),
  );
  const matrixPoints: CalibrationMatrixPoint[] = (record?.points ?? []).map(
    (point) => {
      const rule = templatePointMap.get(point.point_code);
      return {
        id: point.id,
        point_code: point.point_code,
        measurement_mode: point.measurement_mode,
        unit: point.unit,
        reference_input_mode: rule?.reference_input_mode
          ?? point.reference_input_mode
          ?? 'certified_value',
        required_repetitions: point.required_repetitions,
        reference_value: point.reference_value,
        uncertainty_required: rule?.uncertainty_required
          ?? point.uncertainty_required,
      };
    },
  );

  const saveMatrix = async () => {
    if (!record) return;
    try {
      const updated = await saveReadings.mutateAsync({
        calibrationId: record.id,
        expected_version: record.row_version,
        points: (record.points ?? []).map((point: EquipmentCalibrationPoint) => {
          const mode = matrixPoints.find(
            (candidate) => candidate.id === point.id,
          )?.reference_input_mode;
          const referenceKey = `${point.point_code}:reference`;
          const confirmedReference = Object.prototype.hasOwnProperty.call(
            matrixValues,
            referenceKey,
          )
            ? matrixValues[referenceKey].trim() || null
            : point.reference_value;
          return {
            point_id: point.id,
            reference_value: mode === 'certified_value'
              ? (
                matrixValues[`${point.point_code}:reference-confirmed`] === 'true'
                  ? confirmedReference
                  : null
              )
              : point.reference_value,
            expanded_uncertainty:
              matrixValues[`${point.point_code}:uncertainty`]?.trim() || null,
            coverage_factor:
              matrixValues[`${point.point_code}:coverage`]?.trim() || null,
            readings: Array.from(
              { length: point.required_repetitions },
              (_, index) => {
                const trialNo = index + 1;
                const reading: {
                  trial_no: number;
                  standard_reading?: string | null;
                  indicated_value: string | null;
                } = {
                  trial_no: trialNo,
                  indicated_value: pointValue(
                    matrixValues,
                    point.point_code,
                    trialNo,
                    'indicated',
                  ),
                };
                if (mode === 'paired_reading') {
                  reading.standard_reading = pointValue(
                    matrixValues,
                    point.point_code,
                    trialNo,
                    'standard',
                  );
                }
                return reading;
              },
            ),
          };
        }),
      });
      setRecord(updated);
      setDirty(false);
      setServerDirty(false);
      setValidation(null);
      setStep(4);
      setEnabledThrough(4);
    } catch (found) {
      setError(apiErrorMessage(found, '原始讀值未儲存'));
    }
  };

  const validate = async () => {
    if (!record) return;
      if (
      record.calibration_type === 'external'
      && record.certificate_attachment_id == null
    ) {
      setValidation({
        result: 'pending',
        blockers: ['CALIBRATION_CERTIFICATE_REQUIRED'],
        passed_scope_codes: [],
        failed_scope_codes: [],
        row_version: record.row_version,
      });
      return;
    }
    try {
      const result = await validateCalibration.mutateAsync({
        calibrationId: record.id,
        expected_version: record.row_version,
      });
      setValidation(result);
      setRecord((current) => current ? {
        ...current,
        row_version: result.row_version,
        result: result.result,
      } : current);
    } catch (found) {
      setError(apiErrorMessage(found, '送審前驗證未完成'));
      if (found instanceof ApiError) {
        const detailStep = found.details?.step;
        const detailField = found.details?.field;
        if (
          detailStep === 'environment'
          || detailField === 'certificate_attachment_id'
        ) {
          setStep(2);
          const requirement = typeof found.details?.requirement === 'string'
            ? found.details.requirement
            : null;
          requestAnimationFrame(() => {
            if (requirement) {
              document.getElementById(`environment-${requirement}`)?.focus();
            } else {
              document.getElementById('calibration-certificate-file')?.focus();
            }
          });
        } else if (detailStep === 'readings') {
          setStep(3);
          const pointCode = typeof found.details?.point_code === 'string'
            ? found.details.point_code
            : null;
          requestAnimationFrame(() => {
            const inputs = document.querySelectorAll<HTMLInputElement>(
              '[data-point-code]',
            );
            [...inputs].find(
              (input) => input.dataset.pointCode === pointCode,
            )?.focus();
          });
        }
      }
    }
  };

  const submit = async () => {
    if (!record || !submitReason.trim()) return;
    try {
      const submitted = await submitCalibration.mutateAsync({
        calibrationId: record.id,
        expected_version: record.row_version,
        reason: submitReason.trim(),
      });
      setRecord(submitted);
      setDirty(false);
      setServerDirty(false);
      setStep(4);
    } catch (found) {
      setError(apiErrorMessage(found, '校正紀錄未送審'));
    }
  };

  return (
    <main className="cal-page" aria-labelledby="cal-entry-title">
      <header className="cal-page-header">
        <div>
          <Link
            className="cal-back-link"
            to="/measurement-equipment"
          >
            ← 返回量測設備
          </Link>
          <p className="cal-kicker">Detailed calibration evidence</p>
          <h1 id="cal-entry-title">校正詳細數據登錄</h1>
          <p>四步保存設備、條件、原始讀值與送審證據。</p>
        </div>
        {record && <code>草稿 #{record.id} · r{record.row_version}</code>}
      </header>
      <CalibrationStepper
        currentStep={step}
        enabledThrough={enabledThrough}
        minimumStep={record ? 2 : 1}
        locked={workflowInteractionLocked}
        onSelect={(nextStep) => {
          if (!workflowInteractionLocked) setStep(nextStep);
        }}
      />
      {error && <p className="cal-inline-error" role="alert">{error}</p>}

      {step === 1 && (
        <section className="cal-wizard-panel" aria-labelledby="setup-title">
          <h2 id="setup-title">設備與程序</h2>
          <fieldset
            className="cal-form-grid"
            disabled={createCalibration.isPending}
          >
            <legend className="visually-hidden">草稿基本資料</legend>
            <label>
              搜尋受校設備
              <input
                type="search"
                value={equipmentSearch}
                onChange={(event) => setEquipmentSearch(event.target.value)}
              />
            </label>
            <label>
              受校設備
              <select
                value={equipmentId}
                onChange={(event) => {
                  mark(setEquipmentId)(event.target.value);
                  setTemplateId('');
                }}
              >
                <option value="">請選擇</option>
                {equipmentOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.equipment_no} · {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              搜尋校正模板
              <input
                type="search"
                value={templateSearch}
                onChange={(event) => setTemplateSearch(event.target.value)}
              />
            </label>
            <label>
              校正模板
              <select
                value={templateId}
                disabled={!equipmentId}
                onChange={(event) => mark(setTemplateId)(event.target.value)}
              >
                <option value="">請選擇</option>
                {availableTemplates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.template_code} · {template.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              校正類型
              <select
                value={calibrationType}
                onChange={(event) => mark(setCalibrationType)(
                  event.target.value as 'internal' | 'external',
                )}
              >
                <option value="internal">內校</option>
                <option value="external">外校</option>
              </select>
            </label>
            <label>
              校正日期
              <input
                type="date"
                value={calibrationDate}
                onChange={(event) => mark(setCalibrationDate)(event.target.value)}
              />
            </label>
            {calibrationType === 'internal' ? (
              <>
                <label>
                  搜尋參考標準器
                  <input
                    type="search"
                    value={standardSearch}
                    onChange={(event) => setStandardSearch(event.target.value)}
                  />
                </label>
                <label>
                  參考標準器
                  <select
                    value={referenceId}
                    onChange={(event) => mark(setReferenceId)(event.target.value)}
                  >
                    <option value="">請選擇</option>
                    {standards.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.equipment_no} · {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : (
              <>
                <label>
                  外校機構
                  <input
                    value={provider}
                    onChange={(event) => mark(setProvider)(event.target.value)}
                  />
                </label>
                <label>
                  證書編號
                  <input
                    value={certificateNo}
                    onChange={(event) => mark(setCertificateNo)(event.target.value)}
                  />
                </label>
              </>
            )}
            <label>
              校正地點
              <input
                value={location}
                onChange={(event) => mark(setLocation)(event.target.value)}
              />
            </label>
          </fieldset>
          {selectedEquipment && (
            <dl className="cal-equipment-evidence">
              <div><dt>設備</dt><dd>{selectedEquipment.equipment_no} · {selectedEquipment.name}</dd></div>
              <div><dt>序號</dt><dd>{selectedEquipment.serial_no || '—'}</dd></div>
              <div>
                <dt>量程</dt>
                <dd>
                  {selectedEquipment.range_min ?? '—'}–
                  {selectedEquipment.range_max ?? '—'} {selectedEquipment.unit || ''}
                </dd>
              </div>
              <div><dt>解析度</dt><dd>{selectedEquipment.resolution ?? '—'} {selectedEquipment.unit || ''}</dd></div>
              <div><dt>目前資格</dt><dd>{selectedEquipment.calibration_status}</dd></div>
            </dl>
          )}
          <div className="cal-action-row">
            <button
              className="cal-button cal-button--primary"
              type="button"
              disabled={createCalibration.isPending}
              onClick={() => void createDraft()}
            >
              建立草稿並繼續
            </button>
          </div>
        </section>
      )}

      {step === 2 && record && approvedVersion && (
        <section className="cal-wizard-panel" aria-labelledby="condition-title">
          <h2 id="condition-title">環境條件與證書</h2>
          <CalibrationConditionForm
            requirements={approvedVersion.environment_requirements}
            values={conditions}
            disabled={
              uploadAttachment.isPending
              || updateCalibration.isPending
              || pendingCertificateId != null
            }
            onChange={(next) => {
              setConditions(next);
              setDirty(true);
              setServerDirty(true);
              setValidation(null);
            }}
          />
          {record.calibration_type === 'external' && (
            <label className="cal-certificate-upload">
              證書附件
              <input
                id="calibration-certificate-file"
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                aria-label="證書附件"
                disabled={
                  uploadAttachment.isPending
                  || updateCalibration.isPending
                  || pendingCertificateId != null
                }
                onChange={(event) => void uploadCertificate(event)}
              />
              {record.certificate_attachment_id && (
                <small>已綁定附件 #{record.certificate_attachment_id}</small>
              )}
              {pendingCertificateId && (
                <button
                  type="button"
                  disabled={updateCalibration.isPending}
                  onClick={() => void retryCertificateBinding()}
                >
                  重新綁定已上傳附件 #{pendingCertificateId}
                </button>
              )}
            </label>
          )}
          <div className="cal-action-row">
            <button
              className="cal-button cal-button--primary"
              type="button"
              disabled={
                updateCalibration.isPending
                || uploadAttachment.isPending
                || pendingCertificateId != null
              }
              onClick={() => void saveConditions()}
            >
              儲存條件並繼續
            </button>
          </div>
        </section>
      )}

      {step === 3 && record && (
        <section className="cal-wizard-panel" aria-labelledby="readings-title">
          <h2 id="readings-title">原始讀值</h2>
          <CalibrationReadingMatrix
            points={matrixPoints}
            values={matrixValues}
            onChange={(next) => {
              setMatrixValues(next);
              setDirty(true);
              setServerDirty(true);
              setValidation(null);
            }}
            readOnly={saveReadings.isPending}
          />
          <div className="cal-action-row">
            <button type="button" onClick={() => setStep(2)}>上一步</button>
            <button
              className="cal-button cal-button--primary"
              type="button"
              disabled={saveReadings.isPending}
              onClick={() => void saveMatrix()}
            >
              儲存原始讀值
            </button>
          </div>
        </section>
      )}

      {step === 4 && record && (
        <CalibrationEvidenceReview
          record={record}
          validation={validation}
          reason={submitReason}
          onReasonChange={(next) => {
            setSubmitReason(next);
            setDirty(true);
          }}
          onValidate={() => void validate()}
          onSubmit={() => void submit()}
          onNavigateBlocker={(blocker, pointCode) => {
            if (
              blocker.includes('ENVIRONMENT')
              || blocker.includes('ATTACHMENT')
              || blocker.includes('CERTIFICATE')
            ) {
              setStep(2);
              return;
            }
            setStep(3);
            requestAnimationFrame(() => {
              const inputs = document.querySelectorAll<HTMLInputElement>(
                '[data-point-code]',
              );
              [...inputs].find(
                (input) => input.dataset.pointCode === pointCode,
              )?.focus();
            });
          }}
          validating={
            validateCalibration.isPending
            || uploadAttachment.isPending
            || updateCalibration.isPending
            || pendingCertificateId != null
          }
          submitting={
            submitCalibration.isPending
            || uploadAttachment.isPending
            || updateCalibration.isPending
            || pendingCertificateId != null
          }
          dirty={serverDirty || pendingCertificateId != null}
          readOnly={recordLocked}
        />
      )}
    </main>
  );
}
