import type {
  CalibrationRecord,
  CalibrationValidationResult,
} from '../../types/calibration';

interface CalibrationEvidenceReviewProps {
  record: CalibrationRecord;
  validation: CalibrationValidationResult | null;
  reason: string;
  onReasonChange: (reason: string) => void;
  onValidate: () => void;
  onSubmit: () => void;
  onNavigateBlocker: (blocker: string, pointCode?: string) => void;
  validating: boolean;
  submitting: boolean;
  dirty: boolean;
  readOnly: boolean;
}

interface CalibrationBlockerEntry {
  blocker: string;
  pointCode?: string;
}

const resultLabel = (result: CalibrationRecord['result']) => ({
  pending: '待判定',
  pass: '合格',
  fail: '不合格',
  limited_use: '限制使用',
}[result]);

export default function CalibrationEvidenceReview({
  record,
  validation,
  reason,
  onReasonChange,
  onValidate,
  onSubmit,
  onNavigateBlocker,
  validating,
  submitting,
  dirty,
  readOnly,
}: CalibrationEvidenceReviewProps) {
  const blockers = validation?.blockers ?? [];
  const calculationPoints = Array.isArray(record.calculation_summary.points)
    ? record.calculation_summary.points
    : [];
  const pointCodesForBlocker = (blocker: string) => {
    const explicit = blocker.split(':')[1];
    if (explicit) return [explicit];
    const summaryPoints = calculationPoints.filter((item) => (
      typeof item === 'object'
      && item !== null
      && Array.isArray((item as { blockers?: unknown }).blockers)
      && ((item as { blockers: unknown[] }).blockers).includes(blocker)
    )).map((item) => (
      typeof (item as { point_code?: unknown }).point_code === 'string'
        ? (item as { point_code: string }).point_code
        : null
    )).filter((pointCode): pointCode is string => pointCode !== null);
    if (summaryPoints.length > 0) return [...new Set(summaryPoints)];
    return [];
  };
  const blockerEntries = blockers.flatMap<CalibrationBlockerEntry>((blocker) => {
    const pointCodes = pointCodesForBlocker(blocker);
    return pointCodes.length > 0
      ? pointCodes.map((pointCode) => ({ blocker, pointCode }))
      : [{ blocker, pointCode: undefined }];
  });
  return (
    <section className="cal-evidence-review" aria-labelledby="evidence-title">
      <header>
        <p className="cal-kicker">Server calculation evidence</p>
        <h2 id="evidence-title">證據檢閱</h2>
      </header>
      <div className="cal-result-banner" data-result={record.result}>
        <strong>後端判定：{resultLabel(record.result)}</strong>
        <code>row version {record.row_version}</code>
      </div>
      <dl className="cal-evidence-layers">
        <div>
          <dt>模板程序</dt>
          <dd>{record.procedure_code} · {record.procedure_name}</dd>
        </div>
        <div>
          <dt>參考標準器</dt>
          <dd>{record.reference_standard_equipment_id
            ? `設備 #${record.reference_standard_equipment_id}`
            : '外校不適用'}</dd>
        </div>
        <div>
          <dt>證書附件</dt>
          <dd>{record.certificate_attachment_id
            ? `附件 #${record.certificate_attachment_id}`
            : '尚未綁定'}</dd>
        </div>
        <div>
          <dt>環境條件</dt>
          <dd>{Object.keys(record.environment_conditions).length} 項已保存</dd>
        </div>
        <div>
          <dt>資料雜湊</dt>
          <dd><code>{record.data_hash || '草稿尚未鎖定'}</code></dd>
        </div>
      </dl>
      <section className="cal-review-points" aria-label="校正點後端摘要">
        {(record.points ?? []).map((point) => (
          <article key={point.id}>
            <h3>{point.point_code} · {point.measurement_mode}</h3>
            <p>判定：{resultLabel(point.result)}</p>
            <p>
              完成 {point.completed_reading_count}/{point.required_repetitions} 筆
            </p>
            <p>平均器差 {point.mean_error ?? '—'} {point.unit}</p>
            <p>平均補正值 {point.mean_correction ?? '—'} {point.unit}</p>
            <p>器差範圍 {point.error_range ?? '—'} {point.unit}</p>
            <p>樣本標準差 {point.sample_stddev ?? '—'} {point.unit}</p>
          </article>
        ))}
      </section>
      <button
        className="cal-button cal-button--secondary"
        type="button"
        disabled={validating || submitting || dirty || readOnly}
        onClick={onValidate}
      >
        執行送審前驗證
      </button>
      {validation && blockers.length === 0 && (
        <p className="cal-state" role="status">送審前驗證通過。</p>
      )}
      {blockers.length > 0 && (
        <section className="cal-blockers" aria-label="送審阻擋原因">
          <h3>尚有阻擋原因</h3>
          <ul>
            {blockerEntries.map(({ blocker, pointCode }) => (
              <li key={`${blocker}:${pointCode ?? 'global'}`}>
                <code>
                  {blocker}
                  {pointCode ? ` · ${pointCode}` : ''}
                </code>
                <button
                  type="button"
                  onClick={() => onNavigateBlocker(blocker, pointCode)}
                >
                  {blocker.includes('ENVIRONMENT')
                    ? '返回環境條件'
                    : (
                      blocker.includes('ATTACHMENT')
                      || blocker.includes('CERTIFICATE')
                    )
                      ? '返回證書附件'
                      : `返回 ${pointCode || '原始'} 讀值`}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <label>
        送審理由
        <textarea
          rows={3}
          value={reason}
          disabled={submitting || readOnly}
          onChange={(event) => onReasonChange(event.target.value)}
        />
      </label>
      <button
        className="cal-button cal-button--primary"
        type="button"
        disabled={
          submitting
          || validating
          || readOnly
          || dirty
          || !validation
          || blockers.length > 0
          || !reason.trim()
        }
        onClick={onSubmit}
      >
        送審校正紀錄
      </button>
    </section>
  );
}
