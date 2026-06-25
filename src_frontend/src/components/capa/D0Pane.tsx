import { Alert, Button, Col, Form, Row, Spinner } from 'react-bootstrap';

import AttachmentList from '../common/AttachmentList';
import AttachmentUploader from '../common/AttachmentUploader';
import type { CAPASeverity } from '../../types';

export interface D0PaneProps {
    symptom: string;
    setSymptom: (v: string) => void;
    criteria: string[];
    setCriteria: (v: string[]) => void;
    severity: CAPASeverity | '';
    setSeverity: (v: CAPASeverity | '') => void;
    rigor: string;
    setRigor: (v: string) => void;
    deadline: string;
    setDeadline: (v: string) => void;
    readonly?: boolean;
    capaId: number;
    onSave: () => void;
    saving: boolean;
}

const CRITERIA_OPTIONS = [
    '客戶端發現',
    '流出至市場',
    '產線停工',
    '安全疑慮',
    '法規要求',
    '保固索賠',
    '重複異常',
    '批量不良',
];

const SaveBar = ({ onSave, saving, readonly }: { onSave: () => void; saving: boolean; readonly?: boolean }) => {
    if (readonly) return <Alert variant="secondary" className="mt-3 py-2 small">此 CAPA 已結案，無法編輯。</Alert>;
    return (
        <div className="d-flex justify-content-end mt-3">
            <Button variant="primary" size="sm" onClick={onSave} disabled={saving}>
                {saving ? <Spinner size="sm" animation="border" className="me-1" /> : <i className="bi bi-save me-1" />}
                儲存此步驟
            </Button>
        </div>
    );
};

const D0Pane = ({
    symptom,
    setSymptom,
    criteria,
    setCriteria,
    severity,
    setSeverity,
    rigor,
    setRigor,
    deadline,
    setDeadline,
    readonly,
    capaId,
    onSave,
    saving,
}: D0PaneProps) => {
    const toggleCriteria = (val: string) => {
        setCriteria(criteria.includes(val) ? criteria.filter(c => c !== val) : [...criteria, val]);
    };

    return (
        <div>
            <Form.Group controlId="capa-d0-symptom" className="mb-3">
                <Form.Label className="fw-semibold">症狀描述</Form.Label>
                <Form.Control
                    as="textarea"
                    rows={3}
                    value={symptom}
                    onChange={e => setSymptom(e.target.value)}
                    placeholder="請描述異常症狀…"
                    disabled={readonly}
                />
            </Form.Group>

            <Form.Group className="mb-3">
                <Form.Label className="fw-semibold">判斷準則（可複選）</Form.Label>
                <div className="d-flex flex-wrap gap-2">
                    {CRITERIA_OPTIONS.map(opt => (
                        <Form.Check
                            key={opt}
                            type="checkbox"
                            id={`criteria-${opt}`}
                            label={opt}
                            checked={criteria.includes(opt)}
                            onChange={() => toggleCriteria(opt)}
                            disabled={readonly}
                        />
                    ))}
                </div>
            </Form.Group>

            <Row className="mb-3">
                <Col md={4}>
                    <Form.Group controlId="capa-d0-severity">
                        <Form.Label className="fw-semibold">嚴重度</Form.Label>
                        <Form.Select value={severity} onChange={e => setSeverity(e.target.value as CAPASeverity | '')} disabled={readonly}>
                            <option value="">請選擇</option>
                            <option value="Critical">Critical（緊急）</option>
                            <option value="Major">Major（重要）</option>
                            <option value="Minor">Minor（輕微）</option>
                        </Form.Select>
                    </Form.Group>
                </Col>
                <Col md={4}>
                    <Form.Group controlId="capa-d0-rigor">
                        <Form.Label className="fw-semibold">嚴格度（可 Override）</Form.Label>
                        <Form.Select value={rigor} onChange={e => setRigor(e.target.value)} disabled={readonly}>
                            <option value="完整8D">完整 8D（D0-D8）</option>
                            <option value="簡化5D">簡化 5D（D2,D3,D4,D6,D8）</option>
                        </Form.Select>
                    </Form.Group>
                </Col>
                <Col md={4}>
                    <Form.Group controlId="capa-d0-deadline">
                        <Form.Label className="fw-semibold">客戶要求結案日</Form.Label>
                        <Form.Control type="date" value={deadline} onChange={e => setDeadline(e.target.value)} disabled={readonly} />
                    </Form.Group>
                </Col>
            </Row>

            <hr className="my-3" />
            <h6 className="mb-2 text-muted small">D0 相關附件</h6>
            <AttachmentList entityType="capa" entityId={capaId} dStep="D0" canDelete={!readonly} />
            {!readonly && <AttachmentUploader entityType="capa" entityId={capaId} dStep="D0" />}

            <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
        </div>
    );
};

export default D0Pane;
