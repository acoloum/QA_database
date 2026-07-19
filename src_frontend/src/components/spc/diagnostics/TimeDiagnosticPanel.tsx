import { useState } from 'react';
import { Alert, Badge, Button, Card, Col, Form, Row } from 'react-bootstrap';
import type { SpcStudyResult, SpcTimeModelCode } from '../../../types';

const TIME_MODELS: SpcTimeModelCode[] = ['A1', 'A2', 'B', 'C1', 'C2', 'C3', 'C4', 'D'];
const MIN_REASON_LENGTH = 2;
const MAX_REASON_LENGTH = 500;

interface TimeDiagnosticPanelProps {
  version: SpcStudyResult;
  canApprove: boolean;
  pending?: boolean;
  error?: string | null;
  onConfirm: (model: SpcTimeModelCode, reason: string) => void;
}

const yesNo = (value: boolean | null | undefined, positive = '是', negative = '否') => (
  value == null ? '無法判定' : value ? positive : negative
);

const valueText = (value: number | null | undefined) => (
  value == null ? '—' : Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(5)))
);

const TimeDiagnosticPanelContent = ({
  version, canApprove, pending = false, error = null, onConfirm,
}: TimeDiagnosticPanelProps) => {
  const diagnostic = version.time_model;
  const evidence = diagnostic.evidence;
  const systemCandidate = diagnostic.system_candidate ?? diagnostic.candidate;
  const [model, setModel] = useState<SpcTimeModelCode>(systemCandidate ?? 'A1');
  const [reason, setReason] = useState('');

  const reasonLength = reason.trim().length;
  const diagnosticAvailable = Boolean(
    systemCandidate && !diagnostic.reason_code
      && (diagnostic.candidate_options ?? TIME_MODELS).includes(systemCandidate),
  );
  const canSubmit = canApprove && diagnosticAvailable && version.status === 'draft'
    && !diagnostic.confirmed && reasonLength >= MIN_REASON_LENGTH
    && reasonLength <= MAX_REASON_LENGTH && !pending;
  const modality = evidence?.aggregate_modality;
  const aggregateNormality = evidence?.aggregate_normality;
  const instantaneous = evidence?.instantaneous_distribution;
  const formal = evidence?.formal_stability;
  const multipleFamilies = evidence?.multiple_testing?.families ?? {};
  const multipleComparisonCount = Object.values(multipleFamilies)
    .reduce((total, rows) => total + rows.length, 0);

  return <Card className="mb-3">
    <Card.Header className="d-flex align-items-center justify-content-between gap-2 flex-wrap">
      <div><strong>時間模型診斷</strong><div className="small text-muted">A1／A2／B／C1–C4／D · 診斷 {diagnostic.diagnostic_version ?? version.method_version}</div></div>
      <Badge bg={diagnostic.confirmed ? 'success' : diagnosticAvailable ? 'primary' : 'secondary'}>
        {diagnostic.confirmed ? '已人工確認' : diagnosticAvailable ? '待人工確認' : '目前不可確認'}
      </Badge>
    </Card.Header>
    <Card.Body>
      <div className="d-flex gap-2 flex-wrap mb-3">
        <Badge bg="dark">系統候選：{systemCandidate ?? '無'}</Badge>
        <Badge bg={diagnostic.statistically_controlled ? 'success' : 'warning'} text={diagnostic.statistically_controlled ? undefined : 'dark'}>
          {diagnostic.statistically_controlled ? '統計受控' : '不得視為統計受控'}
        </Badge>
      </div>

      {diagnostic.reason_code && <Alert variant="warning" role="status">
        診斷目前不可用：<code>{diagnostic.reason_code}</code>
        {evidence?.subgroup_count != null && <div>有效子組 {evidence.subgroup_count}；最低需求 {evidence.minimum_subgroups ?? 25}。</div>}
      </Alert>}

      {evidence && <Row className="g-2 mb-3" aria-label="時間模型診斷證據">
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>趨勢：{yesNo(evidence.trend?.detected, '已偵測', '未偵測')}</strong><div className="small text-muted">{evidence.trend?.method ?? '未提供方法'}；τ {valueText(evidence.trend?.tau)}；斜率 {valueText(evidence.trend?.slope)}</div></div></Col>
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>變點：{yesNo(evidence.change_points?.detected, '已偵測', '未偵測')}</strong><div className="small text-muted">索引 {evidence.change_points?.change_points.join('、') || '無'}；最小區段 {valueText(evidence.change_points?.min_segment)}；通過視窗 {evidence.change_points?.windows.length ?? 0}</div></div></Col>
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>變異變化：{yesNo(evidence.variance_change?.detected, '已偵測', '未偵測')}</strong><div className="small text-muted">索引 {evidence.variance_change?.change_indexes.join('、') || '無'}；最小區段 {valueText(evidence.variance_change?.min_segment)}；通過視窗 {evidence.variance_change?.windows.length ?? 0}</div></div></Col>
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>隨機位置效應：{yesNo(evidence.random_location?.reject, '顯著', '不顯著')}</strong><div className="small text-muted">ω² {valueText(evidence.random_location?.omega_squared)}；原始 p {valueText(evidence.random_location?.raw_p_value)}；Holm p {valueText(evidence.random_location?.adjusted_p_value)}；門檻 {valueText(evidence.random_location?.threshold)}</div></div></Col>
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>瞬時分布：{instantaneous?.normal == null ? '無法判定' : instantaneous.normal ? '常態' : '非常態'}</strong><div className="small text-muted">{instantaneous?.accepted ? '已接受' : '未接受'}；AD p {valueText(instantaneous?.p_value)}；Holm p {valueText(instantaneous?.adjusted_p_value)}；門檻 {valueText(instantaneous?.threshold)}</div></div></Col>
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>合成分布：{modality?.unimodal == null ? '無法判定' : modality.unimodal ? '單峰' : '多峰'}</strong><div className="small text-muted">{aggregateNormality?.normal == null ? '常態性無法判定' : aggregateNormality.normal ? '常態' : '非常態'}；峰數 {valueText(modality?.peak_count)}；頻寬 {valueText(modality?.bandwidth)}；p {valueText(aggregateNormality?.p_value)}</div></div></Col>
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>多重檢定：{evidence.multiple_testing?.method ?? '未提供'}</strong><div className="small text-muted">檢定族別 {Object.keys(multipleFamilies).length}；比較 {multipleComparisonCount} 項</div></div></Col>
        <Col sm={6} xl={3}><div className="border rounded p-2 h-100"><strong>正式穩定性：{formal?.stable == null ? '無法判定' : formal.stable ? '穩定' : '不穩定'}</strong><div className="small text-muted">位置 {yesNo(formal?.location.stable, '穩定', '不穩定')}（異常 {formal?.location.violations.length ?? 0}）；變異 {yesNo(formal?.variation.stable, '穩定', '不穩定')}（異常 {formal?.variation.violations.length ?? 0}）</div></div></Col>
      </Row>}

      {diagnostic.confirmed ? <div className="border rounded p-3" aria-label="時間模型確認證據">
        <div className="d-flex gap-2 flex-wrap"><strong>確認模型：{diagnostic.model ?? systemCandidate}</strong>{diagnostic.overridden && <Badge bg="warning" text="dark">人工改判</Badge>}</div>
        <div className="small text-muted mt-1">確認者：{diagnostic.confirmed_by ?? '—'}；確認時間：{diagnostic.confirmed_at ?? '—'}</div>
        <div className="mt-2">{diagnostic.confirmation_reason ?? '未保存確認理由'}</div>
      </div> : diagnosticAvailable && <Form onSubmit={event => {
        event.preventDefault();
        if (canSubmit) onConfirm(model, reason.trim());
      }}>
        <Row className="g-3 align-items-end">
          <Col md={3}><Form.Group controlId={`time-model-${version.id}`}><Form.Label>確認模型</Form.Label><Form.Select aria-label="確認模型" value={model} onChange={event => setModel(event.target.value as SpcTimeModelCode)} disabled={!canApprove || pending}>{TIME_MODELS.map(code => <option key={code} value={code}>{code}</option>)}</Form.Select></Form.Group></Col>
          <Col md={7}><Form.Group controlId={`time-reason-${version.id}`}><Form.Label>確認理由</Form.Label><Form.Control aria-label="確認理由" as="textarea" rows={2} maxLength={MAX_REASON_LENGTH} value={reason} onChange={event => setReason(event.target.value)} disabled={!canApprove || pending} aria-describedby={`time-reason-help-${version.id}`} /><Form.Text id={`time-reason-help-${version.id}`}>必填 2–500 字；目前 {reasonLength} 字。</Form.Text></Form.Group></Col>
          <Col md={2}><Button type="submit" className="w-100" disabled={!canSubmit}>{pending ? '確認中…' : '確認模型'}</Button></Col>
        </Row>
        {!canApprove && <Alert variant="warning" className="mt-3 mb-0">需要 SPC 核准權限（spc.approve）才能確認或改判。</Alert>}
      </Form>}
      {error && <Alert variant="danger" className="mt-3 mb-0" role="alert" aria-live="assertive">{error}</Alert>}
    </Card.Body>
  </Card>;
};

/** 版本 id 是不可變後繼版本的身分；key 可安全清除上一版本尚未送出的決定。 */
const TimeDiagnosticPanel = (props: TimeDiagnosticPanelProps) => (
  <TimeDiagnosticPanelContent key={props.version.id} {...props} />
);

export default TimeDiagnosticPanel;
