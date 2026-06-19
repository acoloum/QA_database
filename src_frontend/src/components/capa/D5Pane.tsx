import { Button, Col, Form, Row, Spinner } from 'react-bootstrap';

export interface D5PaneProps {
    action: string;
    setAction: (v: string) => void;
    plannedDate: string;
    setPlannedDate: (v: string) => void;
    verifyPlan: string;
    setVerifyPlan: (v: string) => void;
    readonly?: boolean;
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

const D5Pane = ({
    action,
    setAction,
    plannedDate,
    setPlannedDate,
    verifyPlan,
    setVerifyPlan,
    readonly,
    onSave,
    saving,
}: D5PaneProps) => (
    <div>
        <Form.Group controlId="capa-d5-action" className="mb-3">
            <Form.Label className="fw-semibold">永久對策內容</Form.Label>
            <Form.Control
                as="textarea"
                rows={4}
                value={action}
                onChange={e => setAction(e.target.value)}
                disabled={readonly}
                placeholder="請描述永久對策…"
            />
        </Form.Group>
        <Row className="mb-3">
            <Col md={4}>
                <Form.Group controlId="capa-d5-planned-date">
                    <Form.Label className="fw-semibold">預計實施日</Form.Label>
                    <Form.Control
                        type="date"
                        value={plannedDate}
                        onChange={e => setPlannedDate(e.target.value)}
                        disabled={readonly}
                    />
                </Form.Group>
            </Col>
            <Col md={8}>
                <Form.Group controlId="capa-d5-verify-plan">
                    <Form.Label className="fw-semibold">驗證計畫</Form.Label>
                    <Form.Control
                        as="textarea"
                        rows={2}
                        value={verifyPlan}
                        onChange={e => setVerifyPlan(e.target.value)}
                        disabled={readonly}
                        placeholder="請描述驗證計畫…"
                    />
                </Form.Group>
            </Col>
        </Row>
        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

export default D5Pane;
