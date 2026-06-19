import { Button, Col, Form, Row, Spinner } from 'react-bootstrap';

import AttachmentList from '../common/AttachmentList';
import AttachmentUploader from '../common/AttachmentUploader';

export interface D3PaneProps {
    action: string;
    setAction: (v: string) => void;
    effectiveDate: string;
    setEffectiveDate: (v: string) => void;
    verification: string;
    setVerification: (v: string) => void;
    readonly?: boolean;
    capaId: number;
    onSave: () => void;
    saving: boolean;
}

const SaveBar = ({ onSave, saving, readonly }: { onSave: () => void; saving: boolean; readonly?: boolean }) => {
    if (readonly) return null;
    return (
        <div className="d-flex justify-content-end mt-3">
            <Button variant="primary" onClick={onSave} disabled={saving}>
                {saving ? (
                    <>
                        <Spinner size="sm" className="me-2" />儲存中
                    </>
                ) : '儲存此步驟'}
            </Button>
        </div>
    );
};

const D3Pane = ({
    action,
    setAction,
    effectiveDate,
    setEffectiveDate,
    verification,
    setVerification,
    readonly,
    capaId,
    onSave,
    saving,
}: D3PaneProps) => (
    <div>
        <Form.Group controlId="capa-d3-action" className="mb-3">
            <Form.Label className="fw-semibold">暫時對策內容</Form.Label>
            <Form.Control
                as="textarea"
                rows={4}
                value={action}
                onChange={e => setAction(e.target.value)}
                disabled={readonly}
                placeholder="請描述暫時對策…"
            />
        </Form.Group>
        <Row className="mb-3">
            <Col md={4}>
                <Form.Group controlId="capa-d3-effective-date">
                    <Form.Label className="fw-semibold">生效日期</Form.Label>
                    <Form.Control
                        type="date"
                        value={effectiveDate}
                        onChange={e => setEffectiveDate(e.target.value)}
                        disabled={readonly}
                    />
                </Form.Group>
            </Col>
            <Col md={8}>
                <Form.Group controlId="capa-d3-verification">
                    <Form.Label className="fw-semibold">有效性驗證</Form.Label>
                    <Form.Control
                        as="textarea"
                        rows={2}
                        value={verification}
                        onChange={e => setVerification(e.target.value)}
                        disabled={readonly}
                        placeholder="請描述如何驗證暫時對策有效…"
                    />
                </Form.Group>
            </Col>
        </Row>

        <hr className="my-3" />
        <h6 className="mb-2 text-muted small">D3 相關附件</h6>
        <AttachmentList entityType="capa" entityId={capaId} dStep="D3" />
        {!readonly && <AttachmentUploader entityType="capa" entityId={capaId} dStep="D3" />}

        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

export default D3Pane;
