import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import CalibrationPointSummary from '../../components/calibration/CalibrationPointSummary';
import CalibrationWorkflowBar from '../../components/calibration/CalibrationWorkflowBar';
import { useAuth } from '../../context/useAuth';
import {
  useApproveCalibration,
  useCalibration,
  useDownloadCalibrationCertificate,
  useRejectCalibration,
  useVoidCalibration,
} from '../../hooks/useCalibrations';
import { ApiError, apiErrorMessage } from '../../services/apiError';
import type { CalibrationDecisionInput, CalibrationRecord } from '../../types/calibration';
import './calibration.css';

const resultLabel = (result: CalibrationRecord['result']) => ({
  pending: '待判定', pass: '合格', fail: '不合格', limited_use: '限制使用',
}[result]);

const statusLabel = (status: CalibrationRecord['status']) => ({
  draft: '草稿', in_progress: '進行中', ready_for_submission: '待送審',
  submitted: '待核准', rejected: '已退回', approved: '已核准',
  superseded: '已取代', voided: '已作廢',
}[status]);

const calibrationCode = (record: CalibrationRecord) => {
  const year = record.calibration_date.slice(0, 4) || '0000';
  return `CAL-${year}-${String(record.id).padStart(4, '0')}`;
};

const detailEntries = (details?: Record<string, unknown>) => Object.entries(details ?? {})
  .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`);

export default function CalibrationDetailPage() {
  const { calibrationId } = useParams();
  const numericId = Number(calibrationId);
  const { hasPermission } = useAuth();
  const query = useCalibration(Number.isFinite(numericId) ? numericId : null);
  const approve = useApproveCalibration();
  const reject = useRejectCalibration();
  const voidRecord = useVoidCalibration();
  const downloadCertificate = useDownloadCalibrationCertificate();
  const [approvalReason, setApprovalReason] = useState('');
  const [actionReason, setActionReason] = useState('');
  const [confirmations, setConfirmations] = useState({
    raw_readings: false, calculations: false, reference_standard: false,
    attachments: false, template_version: false,
  });
  const [actionError, setActionError] = useState<{ message: string; details: string[] } | null>(null);

  if (query.isLoading) return <main className="cal-page"><p className="cal-state" role="status">正在讀取校正證據卷宗…</p></main>;
  if (query.isError || !query.data) return (
    <main className="cal-page"><section className="cal-state cal-state--error" role="alert"><p>校正紀錄載入失敗。</p><button type="button" onClick={() => void query.refetch()}>重新載入</button></section></main>
  );

  const calibration = query.data;
  const isDetailed = calibration.data_level === 'detailed';
  const canApprove = calibration.status === 'submitted' && hasPermission('calibration.approve');
  const canVoid = ['draft', 'in_progress', 'ready_for_submission'].includes(calibration.status)
    && hasPermission('calibration.manage');
  const allConfirmed = Object.values(confirmations).every(Boolean);
  const handleDecision = (
    operation: 'approve' | 'reject' | 'void',
    input: CalibrationDecisionInput,
  ) => {
    const mutation = operation === 'approve' ? approve : operation === 'reject' ? reject : voidRecord;
    setActionError(null);
    void mutation.mutateAsync(input).catch((error: unknown) => {
      setActionError({
        message: apiErrorMessage(error, '校正工作流操作失敗。'),
        details: error instanceof ApiError ? detailEntries(error.details) : [],
      });
    });
  };

  return (
    <main className="cal-page" aria-labelledby="calibration-detail-title">
      <Link className="cal-back-link" to="/calibrations">← 返回校正工作佇列</Link>
      <header className="cal-page-header">
        <div>
          <p className="cal-kicker">校正證據卷宗 / 受控證據封套</p>
          <h1 id="calibration-detail-title">校正紀錄 {calibrationCode(calibration)}</h1>
          <p>{calibration.equipment_no || '未編號設備'} · {calibration.equipment_name || '未命名量測設備'} · {calibration.procedure_code}</p>
        </div>
        <div className="cal-detail-status"><strong>{statusLabel(calibration.status)}</strong><span>{resultLabel(calibration.result)}</span></div>
      </header>
      <CalibrationWorkflowBar status={calibration.status} />
      {actionError && <section className="cal-inline-error" role="alert"><p>{actionError.message}</p>{actionError.details.map((detail) => <code key={detail}>{detail}</code>)}</section>}
      {!isDetailed && <section className="cal-state cal-state--error" role="alert"><p>舊版摘要資料未保存逐點原始讀值、標準器快照與計算明細；本頁僅可檢視摘要層。</p></section>}
      <section className="cal-evidence-envelope" aria-labelledby="result-summary-title">
        <h2 id="result-summary-title">判定摘要</h2>
        <dl className="cal-detail-facts"><div><dt>判定</dt><dd>{resultLabel(calibration.result)}</dd></div><div><dt>計算版本</dt><dd>{calibration.calculation_version || '未提供'}</dd></div><div><dt>資料雜湊</dt><dd><code>{calibration.data_hash || '未鎖定'}</code></dd></div><div><dt>完成時間</dt><dd>{calibration.completed_at || '未完成'}</dd></div></dl>
      </section>
      {isDetailed && <>
        <section className="cal-evidence-envelope" aria-labelledby="point-summary-title"><h2 id="point-summary-title">校正點摘要</h2><div className="cal-point-summary-grid">{(calibration.points ?? []).map((point) => <CalibrationPointSummary key={point.id} point={point} />)}</div></section>
        <section className="cal-evidence-envelope" aria-labelledby="raw-readings-title"><h2 id="raw-readings-title">原始讀值</h2><div className="cal-detail-readings">{(calibration.points ?? []).flatMap((point) => point.readings.map((reading) => <article className="cal-detail-reading-card" data-testid={`mobile-reading-${point.point_code}-${reading.trial_no}`} key={reading.id}><h3>{point.point_code} · 試驗 {reading.trial_no}</h3><dl><div><dt>標準器讀值</dt><dd>{reading.standard_reading ?? '—'}</dd></div><div><dt>受校件示值</dt><dd>{reading.indicated_value ?? '—'}</dd></div><div><dt>器差</dt><dd>{reading.error_value ?? '—'} {point.unit}</dd></div><div><dt>補正值</dt><dd>{reading.correction_value ?? '—'} {point.unit}</dd></div></dl></article>))}</div></section>
        <section className="cal-evidence-envelope" aria-labelledby="reference-snapshots-title"><h2 id="reference-snapshots-title">標準器快照</h2><div className="cal-snapshot-grid">{(calibration.reference_snapshots ?? []).map((snapshot) => <article key={snapshot.id}><code>{snapshot.equipment_no}</code><h3>{snapshot.name}</h3><p>證書：{snapshot.certificate_no || '未提供'} · 到期日：{snapshot.calibration_due_date || '未提供'}</p><p>追溯標準：{snapshot.traceability_standard || '未提供'}</p></article>)}</div></section>
        <section className="cal-evidence-envelope" aria-labelledby="certificate-title"><h2 id="certificate-title">證書附件</h2>{calibration.certificate_attachment_id ? <button type="button" className="cal-button cal-button--secondary" onClick={() => void downloadCertificate.mutateAsync({ attachmentId: calibration.certificate_attachment_id as number, filename: `${calibrationCode(calibration)}-certificate.pdf` })}>下載證書附件</button> : <p>尚未綁定證書附件。</p>}</section>
      </>}
      <section className="cal-evidence-envelope" aria-labelledby="signoff-title"><h2 id="signoff-title">簽核紀錄</h2><dl className="cal-detail-facts"><div><dt>建立人</dt><dd>#{calibration.created_by}</dd></div><div><dt>送審人</dt><dd>{calibration.submitted_by ? `#${calibration.submitted_by}` : '尚未送審'}</dd></div><div><dt>核准人</dt><dd>{calibration.approved_by ? `#${calibration.approved_by}` : '尚未核准'}</dd></div><div><dt>核准理由</dt><dd>{calibration.approval_reason || '尚未填寫'}</dd></div></dl></section>
      <section className="cal-evidence-envelope" aria-labelledby="template-snapshot-title"><h2 id="template-snapshot-title">模板版本快照</h2><pre>{JSON.stringify(calibration.template_snapshot, null, 2)}</pre></section>
      {(canApprove || canVoid) && <section className="cal-decision-panel" aria-labelledby="decision-title"><h2 id="decision-title">工作流操作</h2>{canApprove && <><label>核准理由<textarea value={approvalReason} onChange={(event) => setApprovalReason(event.target.value)} /></label><fieldset><legend>五層證據確認</legend>{([['raw_readings', '已核對原始讀值'], ['calculations', '已核對計算結果'], ['reference_standard', '已核對標準器資格'], ['attachments', '已核對證書附件'], ['template_version', '已核對模板版本']] as const).map(([key, label]) => <label className="cal-check" key={key}><input type="checkbox" checked={confirmations[key]} onChange={(event) => setConfirmations((current) => ({ ...current, [key]: event.target.checked }))} />{label}</label>)}</fieldset><div className="cal-action-row"><button type="button" className="cal-button cal-button--primary" disabled={!approvalReason.trim() || !allConfirmed || approve.isPending} onClick={() => handleDecision('approve', { calibrationId: calibration.id, expected_version: calibration.row_version, reason: approvalReason.trim(), confirmations })}>核准校正</button><button type="button" className="cal-button cal-button--danger" disabled={!actionReason.trim() || reject.isPending} onClick={() => handleDecision('reject', { calibrationId: calibration.id, expected_version: calibration.row_version, reason: actionReason.trim() })}>退回校正</button></div><label>退回／作廢理由<textarea value={actionReason} onChange={(event) => setActionReason(event.target.value)} /></label></>}{canVoid && <><label>退回／作廢理由<textarea value={actionReason} onChange={(event) => setActionReason(event.target.value)} /></label><button type="button" className="cal-button cal-button--danger" disabled={!actionReason.trim() || voidRecord.isPending} onClick={() => handleDecision('void', { calibrationId: calibration.id, expected_version: calibration.row_version, reason: actionReason.trim() })}>作廢校正</button></>}</section>}
    </main>
  );
}
