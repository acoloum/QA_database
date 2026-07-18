import { useState } from 'react';
import { Alert, Button, Col, Form, Offcanvas, Row } from 'react-bootstrap';
import type { SpcOcapInput } from '../../hooks/useSpcStudies';
import type { SpcOcapRecord } from '../../types';

interface SpcOcapOffcanvasProps {
  show: boolean;
  eventId: number;
  ocapId?: number;
  initialValue?: SpcOcapRecord | null;
  onHide: () => void;
  onSave: (input: SpcOcapInput) => void;
  pending?: boolean;
}

const SpcOcapOffcanvas = ({
  show, eventId, ocapId, initialValue, onHide, onSave, pending = false,
}: SpcOcapOffcanvasProps) => {
  const [investigation, setInvestigation] = useState(() => String(initialValue?.investigation_6m?.summary ?? ''));
  const [remeasurement, setRemeasurement] = useState(() => String(initialValue?.remeasurement?.result ?? ''));
  const [adjustment, setAdjustment] = useState(() => initialValue?.process_adjustment ?? '');
  const [disposition, setDisposition] = useState(() => initialValue?.product_disposition ?? '');
  const [ownerId, setOwnerId] = useState(() => initialValue?.owner_id == null ? '' : String(initialValue.owner_id));
  const [effectiveness, setEffectiveness] = useState(() => initialValue?.effectiveness ?? '');
  const [closed, setClosed] = useState(() => initialValue?.status === 'closed');

  const input: SpcOcapInput = {
    eventId,
    ocapId,
    payload: {
      investigation_6m: investigation
        ? { ...(initialValue?.investigation_6m ?? {}), summary: investigation }
        : initialValue?.investigation_6m ?? null,
      remeasurement: remeasurement
        ? { ...(initialValue?.remeasurement ?? {}), result: remeasurement }
        : initialValue?.remeasurement ?? null,
      process_adjustment: adjustment,
      product_disposition: disposition,
      owner_id: ownerId ? Number(ownerId) : null,
      effectiveness,
      status: closed ? 'closed' : 'open',
    },
  };

  const handleSave = () => {
    onSave(input);
  };

  return (
    <Offcanvas show={show} onHide={onHide} placement="end" className="spc-ocap-canvas">
      <Offcanvas.Header closeButton>
        <div>
          <div className="spc-eyebrow">失控反應計畫 · 事件 #{eventId}</div>
          <Offcanvas.Title>OCAP 調查與處置</Offcanvas.Title>
        </div>
      </Offcanvas.Header>
      <Offcanvas.Body>
        <Alert variant="warning" className="small">
          正式 OCAP 僅適用於使用已核准界限的持續監控事件；回溯研究的診斷點不會自動開案。
        </Alert>
        <Form>
          <Form.Group className="mb-3" controlId="ocap-6m">
            <Form.Label>6M 調查</Form.Label>
            <Form.Control as="textarea" rows={3} value={investigation} onChange={event => setInvestigation(event.target.value)} placeholder="人、機、料、法、環、測的查核結果" />
          </Form.Group>
          <Form.Group className="mb-3" controlId="ocap-remeasurement">
            <Form.Label>重新量測</Form.Label>
            <Form.Control as="textarea" rows={2} value={remeasurement} onChange={event => setRemeasurement(event.target.value)} placeholder="量具、樣本與重測結果" />
          </Form.Group>
          <Row>
            <Col md={6}>
              <Form.Group className="mb-3" controlId="ocap-adjustment">
                <Form.Label>製程調整</Form.Label>
                <Form.Control as="textarea" rows={3} value={adjustment} onChange={event => setAdjustment(event.target.value)} />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group className="mb-3" controlId="ocap-disposition">
                <Form.Label>產品處置</Form.Label>
                <Form.Control as="textarea" rows={3} value={disposition} onChange={event => setDisposition(event.target.value)} />
              </Form.Group>
            </Col>
          </Row>
          <Form.Group className="mb-3" controlId="ocap-owner">
            <Form.Label>責任人 ID</Form.Label>
            <Form.Control type="number" min={1} value={ownerId} onChange={event => setOwnerId(event.target.value)} />
          </Form.Group>
          <Form.Group className="mb-3" controlId="ocap-effectiveness">
            <Form.Label>有效性確認</Form.Label>
            <Form.Control as="textarea" rows={3} value={effectiveness} onChange={event => setEffectiveness(event.target.value)} placeholder="結案前說明追蹤期間與客觀證據" />
          </Form.Group>
          <Form.Check id="ocap-closed" className="mb-3" label="結案" checked={closed} onChange={event => setClosed(event.target.checked)} />
          <div className="d-flex justify-content-end gap-2">
            <Button variant="outline-secondary" onClick={onHide}>取消</Button>
            <Button variant="primary" disabled={pending || (closed && !effectiveness.trim())} onClick={handleSave}>
              {pending ? '儲存中…' : '儲存 OCAP'}
            </Button>
          </div>
        </Form>
      </Offcanvas.Body>
    </Offcanvas>
  );
};

export default SpcOcapOffcanvas;
