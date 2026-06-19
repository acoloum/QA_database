import { Alert, Button, Col, Form, Row, Spinner } from 'react-bootstrap';

import AttachmentList from '../common/AttachmentList';
import AttachmentUploader from '../common/AttachmentUploader';

export interface D6PaneProps {
    implDate: string;
    setImplDate: (v: string) => void;
    result: string;
    setResult: (v: string) => void;
    verified: boolean;
    setVerified: (v: boolean) => void;
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

const D6Pane = ({
    implDate,
    setImplDate,
    result,
    setResult,
    verified,
    setVerified,
    readonly,
    capaId,
    onSave,
    saving,
}: D6PaneProps) => (
    <div>
        <Row className="mb-3">
            <Col md={4}>
                <Form.Group controlId="capa-d6-implement-date">
                    <Form.Label className="fw-semibold">實施日期</Form.Label>
                    <Form.Control
                        type="date"
                        value={implDate}
                        onChange={e => setImplDate(e.target.value)}
                        disabled={readonly}
                    />
                </Form.Group>
            </Col>
        </Row>
        <Form.Group controlId="capa-d6-result" className="mb-3">
            <Form.Label className="fw-semibold">驗證結果</Form.Label>
            <Form.Control
                as="textarea"
                rows={4}
                value={result}
                onChange={e => setResult(e.target.value)}
                disabled={readonly}
                placeholder="請描述驗證結果…"
            />
        </Form.Group>
        <Form.Check
            type="switch"
            id="d6-verified"
            label={<span className="fw-semibold text-success">✓ 確認驗證通過（開放 D8 結案）</span>}
            checked={verified}
            onChange={e => setVerified(e.target.checked)}
            disabled={readonly}
            className="mb-3"
        />
        {verified && (
            <Alert variant="success" className="py-2 small">
                <i className="bi bi-check-circle-fill me-2" />
                D6 驗證已通過，可進行 D8 結案。
            </Alert>
        )}

        <hr className="my-3" />
        <h6 className="mb-2 text-muted small">D6 相關附件</h6>
        <AttachmentList entityType="capa" entityId={capaId} dStep="D6" />
        {!readonly && <AttachmentUploader entityType="capa" entityId={capaId} dStep="D6" />}

        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

export default D6Pane;
