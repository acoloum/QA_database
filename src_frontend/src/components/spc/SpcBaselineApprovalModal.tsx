import { useMemo, useState } from 'react';
import { Badge, Button, Col, Form, Modal, Row, Table } from 'react-bootstrap';
import type { SpcStudyResult } from '../../types';

export type SpcWorkflowAction = 'time-model' | 'submit' | 'approve' | 'reject' | 'retire';

interface SpcBaselineApprovalModalProps {
  show: boolean;
  action: SpcWorkflowAction;
  source: 'shipping' | 'patrol';
  filters: Record<string, unknown>;
  version: SpcStudyResult;
  onHide: () => void;
  onConfirm: (reason: string, model?: 'A1' | 'A2') => void;
  pending?: boolean;
}

const ACTION_COPY: Record<SpcWorkflowAction, { title: string; reason: string; button: string; variant: string }> = {
  'time-model': { title: '確認時間模型', reason: '確認理由', button: '確認時間模型', variant: 'primary' },
  submit: { title: '送審 SPC 研究候選', reason: '送審理由', button: '送審', variant: 'primary' },
  approve: { title: '核准 SPC 基準', reason: '核准理由', button: '核准並生效', variant: 'success' },
  reject: { title: '退回 SPC 研究候選', reason: '退回理由', button: '退回修正', variant: 'danger' },
  retire: { title: '停用 SPC 正式基準', reason: '停用理由', button: '停用基準', variant: 'danger' },
};

const formatValue = (value: unknown) => {
  if (value == null || value === '') return '—';
  if (typeof value === 'boolean') return value ? '是' : '否';
  return String(value);
};

const firstLimit = (values: number[] | undefined) =>
  values?.[0] == null ? '—' : values[0].toFixed(3);

const SpcBaselineApprovalModal = ({
  show, action, source, filters, version, onHide, onConfirm, pending = false,
}: SpcBaselineApprovalModalProps) => {
  const candidate = version.time_model.candidate;
  const [reason, setReason] = useState('');
  const [model, setModel] = useState<'A1' | 'A2'>(candidate === 'A2' ? 'A2' : 'A1');
  const copy = ACTION_COPY[action];

  const evidence = useMemo(() => {
    const samples = version.samples ?? [];
    const recordIds = [...new Set(samples.flatMap(sample => sample.record_ids))];
    const timestamps = samples.map(sample => sample.timestamp).filter((value): value is string => Boolean(value));
    const measurementCount = samples.reduce((total, sample) => total + sample.values.length, 0);
    return {
      recordIds,
      timeRange: timestamps.length > 0 ? `${timestamps[0]} ～ ${timestamps[timestamps.length - 1]}` : '—',
      sampleSummary: `${samples.length} 組／${measurementCount} 筆量測`,
    };
  }, [version.samples]);

  const chart = version.charts;
  const modelAllowed = action !== 'time-model' || candidate === 'A1' || candidate === 'A2';

  return (
    <Modal show={show} onHide={onHide} size="xl" centered>
      <Modal.Header closeButton className="spc-approval-header">
        <div>
          <div className="spc-eyebrow">基準生命週期 · 研究 v{version.version_no}</div>
          <Modal.Title>{copy.title}</Modal.Title>
        </div>
        <Badge bg={source === 'shipping' ? 'primary' : 'secondary'}>
          {source === 'shipping' ? '出貨檢驗' : '巡檢'}
        </Badge>
      </Modal.Header>
      <Modal.Body>
        <Row className="g-4">
          <Col lg={7}>
            <h6 className="spc-section-label">研究證據</h6>
            <Table responsive size="sm" className="spc-evidence-table">
              <tbody>
                {Object.entries(filters).map(([key, value]) => (
                  <tr key={key}><th>{key}</th><td>{formatValue(value)}</td></tr>
                ))}
                <tr><th>來源記錄 ID</th><td>{evidence.recordIds.join('、') || '—'}</td></tr>
                <tr><th>資料時間範圍</th><td>{evidence.timeRange}</td></tr>
                <tr><th>樣本規模</th><td>{evidence.sampleSummary}</td></tr>
                <tr><th>圖表選型</th><td>{chart?.chart_type.toUpperCase().replace('_', '–') ?? '不適用'}</td></tr>
                <tr><th>資料雜湊</th><td><code className="spc-hash">{version.data_hash}</code></td></tr>
              </tbody>
            </Table>
          </Col>
          <Col lg={5}>
            <h6 className="spc-section-label">保存界限快照</h6>
            <div className="spc-limit-grid">
              <div><span>位置 UCL</span><strong>{firstLimit(chart?.location.ucl)}</strong></div>
              <div><span>位置 CL</span><strong>{firstLimit(chart?.location.cl)}</strong></div>
              <div><span>位置 LCL</span><strong>{firstLimit(chart?.location.lcl)}</strong></div>
              <div><span>變異 UCL</span><strong>{firstLimit(chart?.variation.ucl)}</strong></div>
              <div><span>變異 CL</span><strong>{firstLimit(chart?.variation.cl)}</strong></div>
              <div><span>變異 LCL</span><strong>{firstLimit(chart?.variation.lcl)}</strong></div>
            </div>
            {action === 'time-model' && (
              <Form.Group className="mt-3" controlId="spc-time-model">
                <Form.Label>時間模型</Form.Label>
                <Form.Select value={model} onChange={event => setModel(event.target.value as 'A1' | 'A2')}>
                  <option value="A1">A1 — 穩定且單一分布</option>
                  <option value="A2">A2 — 穩定、分層但可受控</option>
                </Form.Select>
                {!modelAllowed && <div className="text-danger small mt-1">系統候選為 {candidate ?? '未判定'}，不可確認 A1/A2。</div>}
              </Form.Group>
            )}
            <Form.Group className="mt-3" controlId="spc-action-reason">
              <Form.Label>{copy.reason}</Form.Label>
              <Form.Control
                as="textarea"
                rows={3}
                value={reason}
                onChange={event => setReason(event.target.value)}
                placeholder="說明檢查內容、判斷依據與變更原因"
              />
            </Form.Group>
          </Col>
        </Row>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="outline-secondary" onClick={onHide}>取消</Button>
        <Button
          variant={copy.variant}
          disabled={pending || !reason.trim() || !modelAllowed}
          onClick={() => {
            if (action === 'time-model') onConfirm(reason.trim(), model);
            else onConfirm(reason.trim());
          }}
        >
          {pending ? '處理中…' : copy.button}
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default SpcBaselineApprovalModal;
