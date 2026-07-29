import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import CalibrationTemplatePointEditor from '../../components/calibration/CalibrationTemplatePointEditor';
import CalibrationTemplateVersionTimeline from '../../components/calibration/CalibrationTemplateVersionTimeline';
import {
  emptyTemplatePoint,
  pointDraftToInput,
  pointToDraft,
  validateTemplatePoints,
  type TemplatePointDraft,
} from '../../components/calibration/calibrationTemplateDraft';
import { useAuth } from '../../context/useAuth';
import {
  useApproveCalibrationTemplateVersion,
  useCalibrationTemplate,
  useCreateCalibrationTemplateVersion,
  useRejectCalibrationTemplateVersion,
  useSubmitCalibrationTemplateVersion,
  useUpdateCalibrationTemplateVersion,
} from '../../hooks/useCalibrationTemplates';
import { ApiError } from '../../services/apiError';
import type {
  CalibrationTemplateVersion,
  CalibrationTemplateVersionInput,
} from '../../types/calibration';
import './calibration.css';

const STATUS_LABELS: Record<CalibrationTemplateVersion['status'], string> = {
  draft: '草稿',
  submitted: '已送審',
  approved: '已核准',
  rejected: '已退回',
  superseded: '已被取代',
};

interface VersionEditorProps {
  templateId: number;
  version: CalibrationTemplateVersion;
  canManage: boolean;
  canApprove: boolean;
  refetch: () => Promise<unknown> | void;
}

interface EditorError {
  message: string;
  fieldPath: string | null;
  conflict: boolean;
}

const localError = (message: string, fieldPath: string | null = null): EditorError => ({
  message,
  fieldPath,
  conflict: false,
});

const mutationError = (error: unknown): EditorError => {
  const message = error instanceof Error ? error.message : '操作未完成。';
  if (!(error instanceof ApiError)) return localError(message);
  const detailField = typeof error.details?.field === 'string'
    ? error.details.field
    : error.field ?? null;
  const detailIndex = typeof error.details?.index === 'number'
    ? error.details.index
    : null;
  const fieldPath = detailField && detailIndex !== null
    ? `points[${detailIndex}].${detailField}`
    : detailField;
  const currentVersion = error.details?.current_version;
  const expectedVersion = error.details?.expected_version;
  const conflict = typeof currentVersion === 'number'
    && typeof expectedVersion === 'number';
  return {
    message: conflict
      ? `${message}（目前版本 r${currentVersion}；送出版本 r${expectedVersion}）`
      : message,
    fieldPath,
    conflict,
  };
};

const POINT_FIELD_IDS: Record<string, string> = {
  point_code: 'code',
  measurement_mode: 'mode',
  nominal_value: 'nominal',
  unit: 'unit',
  reference_input_mode: 'reference-mode',
  required_repetitions: 'repetitions',
  error_lower_limit: 'lower',
  error_upper_limit: 'upper',
  evaluation_basis: 'evaluation',
  repeatability_rule: 'repeat-rule',
  repeatability_limit: 'repeat-limit',
  qualification_scope_code: 'scope',
  qualification_range_start: 'range-start',
  qualification_range_end: 'range-end',
  instruction: 'instruction',
};

const fieldElementId = (fieldPath: string | null): string | null => {
  if (!fieldPath) return null;
  const pointMatch = /^points\[(\d+)]\.(.+)$/.exec(fieldPath);
  if (pointMatch) {
    const suffix = POINT_FIELD_IDS[pointMatch[2]];
    return suffix ? `template-point-${pointMatch[1]}-${suffix}` : null;
  }
  return `version-${fieldPath.replaceAll('_', '-')}`;
};

const versionPayload = (
  version: CalibrationTemplateVersion,
  revisionReason: string,
): CalibrationTemplateVersionInput => ({
  procedure_code: version.procedure_code,
  procedure_name: version.procedure_name,
  procedure_description: version.procedure_description,
  default_repetitions: version.default_repetitions,
  environment_requirements: version.environment_requirements,
  allow_limited_use: version.allow_limited_use,
  revision_reason: revisionReason,
  points: version.points.map((point) => pointDraftToInput(pointToDraft(point))),
});

const environmentSummary = (requirements: Record<string, unknown>) => {
  const temperature = requirements.temperature;
  if (typeof temperature !== 'object' || temperature === null) return null;
  const values = temperature as Record<string, unknown>;
  if (
    (typeof values.minimum !== 'string' && typeof values.minimum !== 'number')
    || (typeof values.maximum !== 'string' && typeof values.maximum !== 'number')
  ) return null;
  return `${values.minimum}–${values.maximum} ${
    typeof values.unit === 'string' ? values.unit : ''
  }`.trim();
};

function ServerVersionPreview({
  version,
}: {
  version: CalibrationTemplateVersion;
}) {
  const temperature = environmentSummary(version.environment_requirements);
  const repeatabilityLabels: Record<string, string> = {
    none: '不判定',
    range: '極差',
    stddev: '標準差',
  };
  const referenceLabels: Record<string, string> = {
    certified_value: '認證值',
    paired_reading: '成對讀值',
  };
  const evaluationLabels: Record<string, string> = {
    all_readings: '每筆讀值',
    mean_error: '平均誤差',
  };
  return (
    <details className="cal-server-preview">
      <summary>檢視完整已儲存版本</summary>
      <section aria-label="完整已儲存版本">
        <dl>
          <div><dt>程序代碼</dt><dd>{version.procedure_code}</dd></div>
          <div><dt>程序名稱</dt><dd>{version.procedure_name}</dd></div>
          <div>
            <dt>程序說明</dt>
            <dd>{version.procedure_description || '未填寫'}</dd>
          </div>
          <div>
            <dt>預設重複次數</dt>
            <dd>{version.default_repetitions}</dd>
          </div>
          <div>
            <dt>限制使用</dt>
            <dd>{version.allow_limited_use ? '允許' : '不允許'}</dd>
          </div>
          <div>
            <dt>修訂理由</dt>
            <dd>{version.revision_reason || '未填寫'}</dd>
          </div>
          <div>
            <dt>溫度條件</dt>
            <dd>{temperature || '未定義結構化溫度條件'}</dd>
          </div>
        </dl>
        <pre aria-label="環境條件原始 JSON">
          {JSON.stringify(version.environment_requirements, null, 2)}
        </pre>
        <div className="cal-server-preview__points">
          {version.points.map((point) => (
            <article key={point.id}>
              <h3>{point.point_code} · {point.measurement_mode}</h3>
              <p>
                名目值 {point.nominal_value ?? '—'} {point.unit}
                {' · '}重複 {point.required_repetitions} 次
              </p>
              <p>
                {point.error_lower_limit ?? '—'} ～ {point.error_upper_limit ?? '—'}
                {' '}{point.unit}
              </p>
              <p>
                {repeatabilityLabels[point.repeatability_rule]
                  ?? point.repeatability_rule}
                {point.repeatability_rule !== 'none' && (
                  <> ≤ {point.repeatability_limit ?? '—'} {point.unit}</>
                )}
              </p>
              <p>
                {referenceLabels[point.reference_input_mode]
                  ?? point.reference_input_mode}
                {' · '}
                {evaluationLabels[point.evaluation_basis]
                  ?? point.evaluation_basis}
              </p>
              <p>
                {point.required ? '必要點' : '選填點'}
                {' · '}
                {point.uncertainty_required ? '需不確定度' : '不需不確定度'}
              </p>
              <p>
                資格範圍 {point.qualification_scope_code || '未限制'}
                {' · '}{point.qualification_range_start ?? '—'}
                ～{point.qualification_range_end ?? '—'} {point.unit}
              </p>
              <p>{point.instruction || '未填寫操作指示'}</p>
            </article>
          ))}
        </div>
      </section>
    </details>
  );
}

function VersionEditor({
  templateId,
  version,
  canManage,
  canApprove,
  refetch,
}: VersionEditorProps) {
  const updateVersion = useUpdateCalibrationTemplateVersion();
  const createVersion = useCreateCalibrationTemplateVersion();
  const submitVersion = useSubmitCalibrationTemplateVersion();
  const approveVersion = useApproveCalibrationTemplateVersion();
  const rejectVersion = useRejectCalibrationTemplateVersion();
  const isDraftEditable = canManage && version.status === 'draft';
  const editingPending = updateVersion.isPending || submitVersion.isPending;
  const formDisabled = !isDraftEditable || editingPending;
  const [procedureCode, setProcedureCode] = useState(version.procedure_code);
  const [procedureName, setProcedureName] = useState(version.procedure_name);
  const [procedureDescription, setProcedureDescription] = useState(
    version.procedure_description ?? '',
  );
  const [defaultRepetitions, setDefaultRepetitions] = useState(
    String(version.default_repetitions),
  );
  const [environmentJson, setEnvironmentJson] = useState(
    JSON.stringify(version.environment_requirements, null, 2),
  );
  const [allowLimitedUse, setAllowLimitedUse] = useState(
    version.allow_limited_use,
  );
  const [revisionReason, setRevisionReason] = useState(
    version.revision_reason ?? '',
  );
  const [points, setPoints] = useState<TemplatePointDraft[]>(
    version.points.map(pointToDraft),
  );
  const [workflowReason, setWorkflowReason] = useState('');
  const [showSuccessor, setShowSuccessor] = useState(false);
  const [successorReason, setSuccessorReason] = useState('');
  const [error, setError] = useState<EditorError | null>(null);
  const serverDraftSnapshot = useMemo(() => JSON.stringify({
    procedureCode: version.procedure_code,
    procedureName: version.procedure_name,
    procedureDescription: version.procedure_description ?? '',
    defaultRepetitions: String(version.default_repetitions),
    environmentJson: JSON.stringify(version.environment_requirements, null, 2),
    allowLimitedUse: version.allow_limited_use,
    revisionReason: version.revision_reason ?? '',
    points: version.points.map(pointToDraft),
  }), [version]);
  const currentDraftSnapshot = JSON.stringify({
    procedureCode,
    procedureName,
    procedureDescription,
    defaultRepetitions,
    environmentJson,
    allowLimitedUse,
    revisionReason,
    points,
  });
  const isDirty = serverDraftSnapshot !== currentDraftSnapshot;

  const showMutationError = (found: unknown) => {
    const details = mutationError(found);
    setError(details);
    const elementId = fieldElementId(details.fieldPath);
    if (elementId) {
      requestAnimationFrame(() => document.getElementById(elementId)?.focus());
    }
  };

  const saveDraft = () => {
    setError(null);
    if (!procedureCode.trim() || !procedureName.trim()) {
      setError(localError('程序代碼與程序名稱為必填'));
      return;
    }
    if (!revisionReason.trim()) {
      setError(localError('修訂理由為必填', 'revision_reason'));
      return;
    }
    if (!/^[1-9]\d*$/.test(defaultRepetitions)) {
      setError(localError('預設重複次數必須是正整數', 'default_repetitions'));
      return;
    }
    const pointError = validateTemplatePoints(points);
    if (pointError) {
      setError(localError(pointError));
      return;
    }
    let environmentRequirements: Record<string, unknown>;
    try {
      const parsed: unknown = JSON.parse(environmentJson);
      if (
        typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)
      ) throw new Error('not-object');
      environmentRequirements = parsed as Record<string, unknown>;
    } catch {
      setError(localError('環境條件必須是 JSON 物件', 'environment_requirements'));
      return;
    }
    void updateVersion.mutateAsync({
      templateId,
      versionId: version.id,
      expected_version: version.row_version,
      procedure_code: procedureCode.trim(),
      procedure_name: procedureName.trim(),
      procedure_description: procedureDescription.trim() || null,
      default_repetitions: Number(defaultRepetitions),
      environment_requirements: environmentRequirements,
      allow_limited_use: allowLimitedUse,
      revision_reason: revisionReason.trim() || null,
      points: points.map(pointDraftToInput),
    }).then(() => refetch()).catch(showMutationError);
  };

  const decide = (
    action: 'submit' | 'approve' | 'reject',
  ) => {
    setError(null);
    if (action === 'submit' && isDirty) {
      setError(localError('有未儲存變更，請先儲存草稿。'));
      return;
    }
    if (!workflowReason.trim()) {
      setError(localError(
        action === 'submit' ? '送審理由為必填' : '決策理由為必填',
      ));
      return;
    }
    const mutation = action === 'submit'
      ? submitVersion
      : action === 'approve'
        ? approveVersion
        : rejectVersion;
    void mutation.mutateAsync({
      templateId,
      versionId: version.id,
      expected_version: version.row_version,
      reason: workflowReason.trim(),
    }).then(() => refetch()).catch(showMutationError);
  };

  return (
    <div className="cal-version-editor">
      <header className="cal-version-editor__header">
        <div>
          <p className="cal-kicker">目前檢視版本</p>
          <h2>V{version.version_no} · {version.procedure_name}</h2>
        </div>
        <span className="cal-workflow-status" data-status={version.status}>
          {STATUS_LABELS[version.status]}
        </span>
      </header>

      <section className="cal-procedure-panel" aria-labelledby="procedure-title">
        <div className="cal-section-heading">
          <div>
            <p className="cal-kicker">程序快照</p>
            <h2 id="procedure-title">版本資料</h2>
          </div>
          <code>row version {version.row_version}</code>
        </div>
        <div className="cal-form-grid">
          <label>
            程序代碼
            <input
              id="version-procedure-code"
              value={procedureCode}
              disabled={formDisabled}
              aria-invalid={error?.fieldPath === 'procedure_code' || undefined}
              aria-describedby={error ? 'template-editor-error' : undefined}
              onChange={(event) => setProcedureCode(event.target.value)}
            />
          </label>
          <label>
            程序名稱
            <input
              id="version-procedure-name"
              value={procedureName}
              disabled={formDisabled}
              aria-invalid={error?.fieldPath === 'procedure_name' || undefined}
              aria-describedby={error ? 'template-editor-error' : undefined}
              onChange={(event) => setProcedureName(event.target.value)}
            />
          </label>
          <label>
            預設重複次數
            <input
              id="version-default-repetitions"
              inputMode="numeric"
              value={defaultRepetitions}
              disabled={formDisabled}
              aria-invalid={error?.fieldPath === 'default_repetitions' || undefined}
              aria-describedby={error ? 'template-editor-error' : undefined}
              onChange={(event) => setDefaultRepetitions(event.target.value)}
            />
          </label>
          <label className="cal-check cal-check--panel">
            <input
              type="checkbox"
              checked={allowLimitedUse}
              disabled={formDisabled}
              onChange={(event) => setAllowLimitedUse(event.target.checked)}
            />
            允許依資格範圍判定限制使用
          </label>
          <label className="cal-form-grid__wide">
            程序說明
            <textarea
              id="version-procedure-description"
              rows={3}
              value={procedureDescription}
              disabled={formDisabled}
              aria-invalid={error?.fieldPath === 'procedure_description' || undefined}
              aria-describedby={error ? 'template-editor-error' : undefined}
              onChange={(event) => setProcedureDescription(event.target.value)}
            />
          </label>
          <label className="cal-form-grid__wide">
            修訂理由
            <textarea
              id="version-revision-reason"
              rows={2}
              value={revisionReason}
              disabled={formDisabled}
              aria-invalid={error?.fieldPath === 'revision_reason' || undefined}
              aria-describedby={error ? 'template-editor-error' : undefined}
              onChange={(event) => setRevisionReason(event.target.value)}
            />
          </label>
          <label className="cal-form-grid__wide">
            環境條件 JSON
            <textarea
              id="version-environment-requirements"
              className="cal-code-input"
              rows={5}
              value={environmentJson}
              disabled={formDisabled}
              aria-invalid={
                error?.fieldPath === 'environment_requirements' || undefined
              }
              aria-describedby={error ? 'template-editor-error' : undefined}
              onChange={(event) => setEnvironmentJson(event.target.value)}
            />
          </label>
        </div>
      </section>

      <CalibrationTemplatePointEditor
        versionNo={version.version_no}
        points={points}
        readOnly={!isDraftEditable}
        disabled={editingPending}
        invalidPath={error?.fieldPath}
        onChange={(index, point) => setPoints((current) => (
          current.map((item, itemIndex) => itemIndex === index ? point : item)
        ))}
        onAdd={() => setPoints((current) => [
          ...current,
          emptyTemplatePoint(
            Math.max(0, ...current.map((point) => point.point_order)) + 1,
          ),
        ])}
        onRemove={(index) => setPoints((current) => (
          current.filter((_, itemIndex) => itemIndex !== index)
        ))}
      />

      {error && (
        <div
          className="cal-inline-error"
          id="template-editor-error"
          role="alert"
        >
          <p>{error.message}</p>
          {error.fieldPath && <p>欄位：{error.fieldPath}</p>}
          {error.conflict && (
            <button type="button" onClick={() => void refetch()}>
              重新載入最新版本
            </button>
          )}
        </div>
      )}

      {isDraftEditable && (
        <section className="cal-workflow-panel" aria-labelledby="draft-actions-title">
          <div>
            <p className="cal-kicker">草稿控制</p>
            <h2 id="draft-actions-title">儲存與送審</h2>
          </div>
          <div className="cal-server-state" aria-label="已儲存版本狀態">
            <strong>已儲存版本預覽</strong>
            <span>
              r{version.row_version} · {version.points.length} 個校正點
              {' · '}{version.procedure_name}
            </span>
            <small>
              {isDirty
                ? '有未儲存變更，請先儲存草稿。'
                : '畫面與已儲存版本一致，可送審。'}
            </small>
          </div>
          <ServerVersionPreview version={version} />
          <label>
            送審理由
            <textarea
              rows={2}
              value={workflowReason}
              disabled={submitVersion.isPending}
              onChange={(event) => setWorkflowReason(event.target.value)}
            />
          </label>
          <div className="cal-action-row">
            <button
              className="cal-button cal-button--secondary"
              type="button"
              disabled={updateVersion.isPending || !isDirty}
              onClick={saveDraft}
            >
              儲存草稿
            </button>
            <button
              className="cal-button cal-button--primary"
              type="button"
              disabled={
                submitVersion.isPending || updateVersion.isPending || isDirty
              }
              onClick={() => decide('submit')}
            >
              送審版本
            </button>
          </div>
        </section>
      )}

      {canApprove && version.status === 'submitted' && (
        <section className="cal-workflow-panel" aria-labelledby="decision-title">
          <div>
            <p className="cal-kicker">獨立檢閱</p>
            <h2 id="decision-title">核准或退回</h2>
          </div>
          <label>
            核准或退回理由
            <textarea
              rows={3}
              value={workflowReason}
              onChange={(event) => setWorkflowReason(event.target.value)}
            />
          </label>
          <div className="cal-action-row">
            <button
              className="cal-button cal-button--danger"
              type="button"
              disabled={rejectVersion.isPending}
              onClick={() => decide('reject')}
            >
              退回版本
            </button>
            <button
              className="cal-button cal-button--primary"
              type="button"
              disabled={approveVersion.isPending}
              onClick={() => decide('approve')}
            >
              核准版本
            </button>
          </div>
        </section>
      )}

      {canManage && (
        version.status === 'approved' || version.status === 'rejected'
      ) && (
        <section className="cal-workflow-panel" aria-labelledby="successor-title">
          <div>
            <p className="cal-kicker">不可變版本</p>
            <h2 id="successor-title">建立後續版本</h2>
          </div>
          {!showSuccessor
            ? (
              <button
                className="cal-button cal-button--secondary"
                type="button"
                onClick={() => {
                  setError(null);
                  setShowSuccessor(true);
                }}
              >
                建立新版
              </button>
            )
            : (
              <>
                <label>
                  新版修訂理由
                  <textarea
                    autoFocus
                    rows={3}
                    value={successorReason}
                    onChange={(event) => setSuccessorReason(event.target.value)}
                  />
                </label>
                <button
                  className="cal-button cal-button--primary"
                  type="button"
                  disabled={createVersion.isPending}
                  onClick={() => {
                    setError(null);
                    if (!successorReason.trim()) {
                      setError(localError('修訂理由為必填'));
                      return;
                    }
                    void createVersion.mutateAsync({
                      templateId,
                      ...versionPayload(version, successorReason.trim()),
                    }).then(() => refetch()).catch(showMutationError);
                  }}
                >
                  建立草稿版本
                </button>
              </>
            )}
        </section>
      )}
    </div>
  );
}

function InitialVersionCreator({
  templateId,
  refetch,
}: {
  templateId: number;
  refetch: () => Promise<unknown> | void;
}) {
  const createVersion = useCreateCalibrationTemplateVersion();
  const [procedureCode, setProcedureCode] = useState('');
  const [procedureName, setProcedureName] = useState('');
  const [procedureDescription, setProcedureDescription] = useState('');
  const [defaultRepetitions, setDefaultRepetitions] = useState('3');
  const [environmentJson, setEnvironmentJson] = useState('{}');
  const [revisionReason, setRevisionReason] = useState('');
  const [allowLimitedUse, setAllowLimitedUse] = useState(false);
  const [points, setPoints] = useState<TemplatePointDraft[]>([]);
  const [error, setError] = useState<EditorError | null>(null);
  const showMutationError = (found: unknown) => {
    const details = mutationError(found);
    setError(details);
    const elementId = fieldElementId(details.fieldPath);
    if (elementId) {
      requestAnimationFrame(() => document.getElementById(elementId)?.focus());
    }
  };

  return (
    <section className="cal-procedure-panel" aria-labelledby="initial-version-title">
      <div className="cal-section-heading">
        <div>
          <p className="cal-kicker">第一個受控版本</p>
          <h2 id="initial-version-title">建立 V1 草稿</h2>
        </div>
      </div>
      <div className="cal-form-grid">
        <label>
          程序代碼
          <input
            id="version-procedure-code"
            value={procedureCode}
            aria-invalid={error?.fieldPath === 'procedure_code' || undefined}
            aria-describedby={error ? 'template-editor-error' : undefined}
            onChange={(event) => setProcedureCode(event.target.value)}
          />
        </label>
        <label>
          程序名稱
          <input
            id="version-procedure-name"
            value={procedureName}
            aria-invalid={error?.fieldPath === 'procedure_name' || undefined}
            aria-describedby={error ? 'template-editor-error' : undefined}
            onChange={(event) => setProcedureName(event.target.value)}
          />
        </label>
        <label>
          預設重複次數
          <input
            id="version-default-repetitions"
            inputMode="numeric"
            value={defaultRepetitions}
            aria-invalid={error?.fieldPath === 'default_repetitions' || undefined}
            aria-describedby={error ? 'template-editor-error' : undefined}
            onChange={(event) => setDefaultRepetitions(event.target.value)}
          />
        </label>
        <label className="cal-check cal-check--panel">
          <input
            type="checkbox"
            checked={allowLimitedUse}
            onChange={(event) => setAllowLimitedUse(event.target.checked)}
          />
          允許依資格範圍判定限制使用
        </label>
        <label className="cal-form-grid__wide">
          程序說明
          <textarea
            id="version-procedure-description"
            rows={3}
            value={procedureDescription}
            aria-invalid={error?.fieldPath === 'procedure_description' || undefined}
            aria-describedby={error ? 'template-editor-error' : undefined}
            onChange={(event) => setProcedureDescription(event.target.value)}
          />
        </label>
        <label className="cal-form-grid__wide">
          修訂理由
          <textarea
            id="version-revision-reason"
            rows={2}
            value={revisionReason}
            aria-invalid={error?.fieldPath === 'revision_reason' || undefined}
            aria-describedby={error ? 'template-editor-error' : undefined}
            onChange={(event) => setRevisionReason(event.target.value)}
          />
        </label>
        <label className="cal-form-grid__wide">
          環境條件 JSON
          <textarea
            id="version-environment-requirements"
            className="cal-code-input"
            rows={5}
            value={environmentJson}
            aria-invalid={
              error?.fieldPath === 'environment_requirements' || undefined
            }
            aria-describedby={error ? 'template-editor-error' : undefined}
            onChange={(event) => setEnvironmentJson(event.target.value)}
          />
        </label>
      </div>
      <CalibrationTemplatePointEditor
        versionNo={1}
        points={points}
        readOnly={false}
        invalidPath={error?.fieldPath}
        onChange={(index, point) => setPoints((current) => (
          current.map((item, itemIndex) => itemIndex === index ? point : item)
        ))}
        onAdd={() => setPoints((current) => [
          ...current,
          emptyTemplatePoint(current.length + 1),
        ])}
        onRemove={(index) => setPoints((current) => (
          current.filter((_, itemIndex) => itemIndex !== index)
        ))}
      />
      {error && (
        <div
          className="cal-inline-error"
          id="template-editor-error"
          role="alert"
        >
          <p>{error.message}</p>
          {error.fieldPath && <p>欄位：{error.fieldPath}</p>}
        </div>
      )}
      <div className="cal-action-row">
        <button
          className="cal-button cal-button--primary"
          type="button"
          disabled={createVersion.isPending}
          onClick={() => {
            setError(null);
            if (!procedureCode.trim() || !procedureName.trim()) {
              setError(localError('程序代碼與程序名稱為必填'));
              return;
            }
            if (!revisionReason.trim()) {
              setError(localError('修訂理由為必填'));
              return;
            }
            if (!/^[1-9]\d*$/.test(defaultRepetitions)) {
              setError(localError('預設重複次數必須是正整數'));
              return;
            }
            const pointError = validateTemplatePoints(points);
            if (pointError) {
              setError(localError(pointError));
              return;
            }
            let environmentRequirements: Record<string, unknown>;
            try {
              const parsed: unknown = JSON.parse(environmentJson);
              if (
                typeof parsed !== 'object'
                || parsed === null
                || Array.isArray(parsed)
              ) throw new Error('not-object');
              environmentRequirements = parsed as Record<string, unknown>;
            } catch {
              setError(localError('環境條件必須是 JSON 物件'));
              return;
            }
            void createVersion.mutateAsync({
              templateId,
              procedure_code: procedureCode.trim(),
              procedure_name: procedureName.trim(),
              procedure_description: procedureDescription.trim() || null,
              default_repetitions: Number(defaultRepetitions),
              environment_requirements: environmentRequirements,
              allow_limited_use: allowLimitedUse,
              revision_reason: revisionReason.trim(),
              points: points.map(pointDraftToInput),
            }).then(() => refetch()).catch(showMutationError);
          }}
        >
          建立第一版草稿
        </button>
      </div>
    </section>
  );
}

export default function CalibrationTemplateEditorPage() {
  const { templateId: rawTemplateId } = useParams();
  const templateId = Number(rawTemplateId);
  const template = useCalibrationTemplate(
    Number.isInteger(templateId) && templateId > 0 ? templateId : null,
  );
  const { hasPermission } = useAuth();
  const canManage = hasPermission('calibration.manage');
  const canApprove = hasPermission('calibration.approve');
  const versions = useMemo(() => (
    [...(template.data?.versions ?? [])].sort(
      (left, right) => right.version_no - left.version_no,
    )
  ), [template.data?.versions]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selectedVersion = versions.find((version) => version.id === selectedId)
    ?? versions[0];

  return (
    <main className="cal-page" aria-labelledby="cal-template-editor-title">
      <header className="cal-page-header">
        <div>
          <Link className="cal-back-link" to="/calibration/templates">
            ← 返回校正模板
          </Link>
          <p className="cal-kicker">程序版本 / 允差 / 重複性</p>
          <h1 id="cal-template-editor-title">
            {template.data?.name ?? '校正模板版本'}
          </h1>
          {template.data && (
            <p>
              <code>{template.data.template_code}</code>
              {' · '}{template.data.equipment_type}
              {' · '}{template.data.description || '未填寫說明'}
            </p>
          )}
        </div>
      </header>

      {template.isLoading && <p className="cal-state" role="status">正在讀取模板版本…</p>}
      {template.isError && (
        <div className="cal-state cal-state--error" role="alert">
          <p>模板版本載入失敗。</p>
          <button type="button" onClick={() => void template.refetch()}>重新載入</button>
        </div>
      )}
      {!template.isLoading && !template.isError && template.data && (
        versions.length > 0
          ? (
            <div className="cal-editor-layout">
              <CalibrationTemplateVersionTimeline
                versions={versions}
                selectedId={selectedVersion.id}
                onSelect={setSelectedId}
              />
              <VersionEditor
                key={`${selectedVersion.id}-${selectedVersion.row_version}`}
                templateId={template.data.id}
                version={selectedVersion}
                canManage={canManage}
                canApprove={canApprove}
                refetch={template.refetch}
              />
            </div>
          )
          : (
            canManage
              ? (
                <InitialVersionCreator
                  templateId={template.data.id}
                  refetch={template.refetch}
                />
              )
              : <p className="cal-state">此模板尚無受控版本。</p>
          )
      )}
    </main>
  );
}
