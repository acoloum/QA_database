import { useState } from 'react';
import { Alert, Badge, Button, Card, Col, Form, Row, Table } from 'react-bootstrap';
import type { SpcDistributionAssessment, SpcStudyResult, SpcTransformationCandidate, SpcTransformationModel } from '../../../types';
import { isMachinePerformanceResult, isSpcDistributionAssessment, isSpcTransformationCandidate } from '../../../types/spc';

const MIN_REASON_LENGTH = 2;
const MAX_REASON_LENGTH = 500;

interface TransformationPanelProps {
  version: SpcStudyResult;
  canApprove: boolean;
  pending?: boolean;
  error?: string | null;
  onConfirm: (model: SpcTransformationModel, reason: string) => void;
}

const numberText = (value: number | null | undefined) => value == null ? '—' : String(Number(value.toPrecision(6)));
const parameterText = (candidate: SpcTransformationCandidate) => Object.entries(candidate.params)
  .map(([name, value]) => `${name}=${numberText(value)}`).join('；') || '無可用參數';

const CandidateEvidence = ({ candidate }: { candidate: SpcTransformationCandidate }) => <div className="small mt-2">
  <div>參數：{parameterText(candidate)}</div>
  <div>epsilon：{numberText(candidate.epsilon)}；AD 統計量：{numberText(candidate.ad_statistic)}；AD p：{numberText(candidate.ad_p_value)}</div>
  <div>尾端分位數：{candidate.tail_quantiles.map(numberText).join('／') || '—'}</div>
  <div>嚴格單調：{candidate.monotonic ? '是' : '否'}；往返誤差：{numberText(candidate.roundtrip_relative_error)}</div>
  <div>配適方法：{candidate.fit_method ?? '不可用'}；理由碼：{candidate.reason_code ?? '無'}</div>
  {candidate.fit_error && <div>配適錯誤：{candidate.fit_error}</div>}
</div>;

const EMPTY_DISTRIBUTION: SpcDistributionAssessment = {
  model: null, label: '舊版未提供', params: [], accepted: false, normal_ok: false,
  unimodal: false, reason_code: 'LEGACY_DISTRIBUTION_UNAVAILABLE', candidates: [],
  fit_method: null, alpha: 0.05,
};

const TransformationPanelContent = ({
  version, canApprove, pending = false, error = null, onConfirm,
}: TransformationPanelProps) => {
  const validDistribution = isSpcDistributionAssessment(version.distribution);
  const distribution = validDistribution ? version.distribution : EMPTY_DISTRIBUTION;
  const legacyReadOnly = version.method_version !== '2026.2';
  const candidates = (distribution.transformation_candidates ?? [])
    .filter(isSpcTransformationCandidate);
  const accepted = candidates.filter(candidate => candidate.accepted);
  const decision = distribution.transformation_decision;
  const transformed = distribution.scale === 'transformed' && decision?.confirmed === true;
  const originalScale = isMachinePerformanceResult(version.capability)
    ? undefined : version.capability.original_scale;
  const [model, setModel] = useState<SpcTransformationModel | ''>(
    distribution.transformation_recommendation?.model
      ?? (distribution.accepted ? '' : accepted[0]?.model ?? ''),
  );
  const [reason, setReason] = useState('');

  const reasonLength = reason.trim().length;
  const selected = accepted.find(candidate => candidate.model === model);
  const canSubmit = !legacyReadOnly && validDistribution && canApprove
    && version.status === 'draft' && Boolean(selected)
    && reasonLength >= MIN_REASON_LENGTH && reasonLength <= MAX_REASON_LENGTH && !pending;

  return <Card className="mb-3">
    <Card.Header className="d-flex align-items-center justify-content-between gap-2 flex-wrap">
      <div><strong>分布轉換候選</strong><div className="small text-muted">Box-Cox／Johnson SU、SB、SL；只可確認已通過候選。</div></div>
      <Badge bg={transformed ? 'success' : distribution.accepted ? 'secondary' : accepted.length ? 'primary' : 'warning'} text={!transformed && !distribution.accepted && !accepted.length ? 'dark' : undefined}>
        {transformed ? '已確認轉換' : distribution.accepted ? '保留原始尺度' : accepted.length ? '待人工確認' : '無可用候選'}
      </Badge>
    </Card.Header>
    <Card.Body>
      <div className="mb-3"><strong>目前尺度：{transformed ? '轉換尺度' : '原始尺度'}</strong>{transformed && <span>；原始模型：{distribution.original_model ?? '未確認'}</span>}</div>

      {legacyReadOnly && <Alert variant="warning" role="alert">
        舊版方法 {version.method_version} 僅供唯讀；請以 2026.2 重建候選後再確認分布轉換。
      </Alert>}
      {!legacyReadOnly && !validDistribution && <Alert variant="warning" role="alert">
        2026.2 分布轉換資料格式不完整，請重新建立候選。
      </Alert>}

      {!legacyReadOnly && transformed && decision ? <div className="border rounded p-3" aria-label="轉換確認證據">
        <div><strong>採用轉換：{decision.label}</strong></div>
        <CandidateEvidence candidate={decision} />
        {originalScale && <div className="small mt-2 border-top pt-2">
          <div>原始尺度分位數：{originalScale.quantiles.map(numberText).join('／') || '—'}</div>
          <div>原始尺度 PPM：上側 {numberText(originalScale.ppm.upper)}；下側 {numberText(originalScale.ppm.lower)}；合計 {numberText(originalScale.ppm.total)}</div>
        </div>}
        <div className="small text-muted mt-2">確認者：{decision.confirmed_by}；確認時間：{decision.confirmed_at}</div>
        <div className="mt-2">{decision.confirmation_reason}</div>
      </div> : <>
        {distribution.accepted && <Alert variant="success">
          原始分布已通過（{distribution.label}），系統依 <code>{distribution.transformation_reason_code ?? 'ORIGINAL_DISTRIBUTION_ACCEPTED'}</code> 抑制自動轉換建議；具核准權限者仍可逐項複核候選並填寫理由。
        </Alert>}
        {distribution.transformation_evidence && <Alert variant={distribution.transformation_evidence.available ? 'info' : 'warning'}>
          樣本數 {distribution.transformation_evidence.n}；最低 {distribution.transformation_evidence.minimum_sample_size}；α={distribution.transformation_evidence.alpha}。{distribution.transformation_evidence.fit_bias_note}
        </Alert>}
        {!legacyReadOnly && <Table responsive bordered hover className="align-middle">
          <thead><tr><th scope="col">選擇／候選</th><th scope="col">證據</th></tr></thead>
          <tbody>{candidates.map(candidate => <tr key={candidate.model} className={candidate.accepted ? '' : 'table-light'}>
            <td style={{ minWidth: 190 }}><Form.Check type="radio" name={`transformation-${version.id}`} id={`transformation-${version.id}-${candidate.model}`} label={`${candidate.label}${candidate.rank ? `（排序 ${candidate.rank}）` : ''}`} checked={candidate.accepted && model === candidate.model} onChange={() => { if (candidate.accepted) setModel(candidate.model); }} disabled={!candidate.accepted || !canApprove || pending} />{!candidate.accepted && <Badge bg="secondary" className="ms-4">不可確認</Badge>}</td>
            <td><CandidateEvidence candidate={candidate} /></td>
          </tr>)}</tbody>
        </Table>}
        {!legacyReadOnly && candidates.length === 0 && <Alert variant="warning">未提供轉換候選：<code>{distribution.transformation_reason_code ?? distribution.reason_code ?? 'TRANSFORMATION_UNAVAILABLE'}</code></Alert>}
        {!legacyReadOnly && accepted.length > 0 && <Form onSubmit={event => {
          event.preventDefault();
          if (canSubmit && selected) onConfirm(selected.model, reason.trim());
        }}>
          <Row className="g-3 align-items-end">
            <Col md={10}><Form.Group controlId={`transformation-reason-${version.id}`}><Form.Label>轉換確認理由</Form.Label><Form.Control aria-label="轉換確認理由" as="textarea" rows={2} maxLength={MAX_REASON_LENGTH} value={reason} onChange={event => setReason(event.target.value)} disabled={!canApprove || pending} aria-describedby={`transformation-help-${version.id}`} /><Form.Text id={`transformation-help-${version.id}`}>必填 2–500 字；目前 {reasonLength} 字。</Form.Text></Form.Group></Col>
            <Col md={2}><Button type="submit" className="w-100" disabled={!canSubmit}>{pending ? '確認中…' : '確認轉換'}</Button></Col>
          </Row>
          {!canApprove && <Alert variant="warning" className="mt-3 mb-0">需要 SPC 核准權限（spc.approve）才能確認轉換。</Alert>}
        </Form>}
      </>}
      {error && <Alert variant="danger" className="mt-3 mb-0" role="alert" aria-live="assertive">{error}</Alert>}
    </Card.Body>
  </Card>;
};

/** 不可變版本切換時重新建立表單，避免沿用已 superseded 版本的候選與理由。 */
const TransformationPanel = (props: TransformationPanelProps) => (
  <TransformationPanelContent key={props.version.id} {...props} />
);

export default TransformationPanel;
