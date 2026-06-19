import { Button, Col, Form, Row, Spinner } from 'react-bootstrap';

import AttachmentList from '../common/AttachmentList';
import AttachmentUploader from '../common/AttachmentUploader';

export interface D2PaneProps {
    what: string;
    setWhat: (v: string) => void;
    where: string;
    setWhere: (v: string) => void;
    when: string;
    setWhen: (v: string) => void;
    who: string;
    setWho: (v: string) => void;
    why: string;
    setWhy: (v: string) => void;
    how: string;
    setHow: (v: string) => void;
    howMany: string;
    setHowMany: (v: string) => void;
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

const D2Pane = ({
    what,
    setWhat,
    where,
    setWhere,
    when,
    setWhen,
    who,
    setWho,
    why,
    setWhy,
    how,
    setHow,
    howMany,
    setHowMany,
    readonly,
    capaId,
    onSave,
    saving,
}: D2PaneProps) => {
    const fields = [
        { id: 'capa-d2-what', label: 'What（是什麼）', value: what, set: setWhat },
        { id: 'capa-d2-where', label: 'Where（在哪裡）', value: where, set: setWhere },
        { id: 'capa-d2-when', label: 'When（何時）', value: when, set: setWhen },
        { id: 'capa-d2-who', label: 'Who（誰）', value: who, set: setWho },
        { id: 'capa-d2-why', label: 'Why（為何出現）', value: why, set: setWhy },
        { id: 'capa-d2-how', label: 'How（如何發現）', value: how, set: setHow },
        { id: 'capa-d2-how-many', label: 'How Many（數量）', value: howMany, set: setHowMany },
    ];

    return (
        <div>
            <Row className="g-3 mb-3">
                {fields.map(f => (
                    <Col md={6} key={f.label}>
                        <Form.Group controlId={f.id}>
                            <Form.Label className="fw-semibold small">{f.label}</Form.Label>
                            <Form.Control
                                as="textarea"
                                rows={2}
                                value={f.value}
                                onChange={e => f.set(e.target.value)}
                                disabled={readonly}
                                placeholder={f.label}
                            />
                        </Form.Group>
                    </Col>
                ))}
            </Row>

            <hr className="my-3" />
            <h6 className="mb-2 text-muted small">D2 相關附件</h6>
            <AttachmentList entityType="capa" entityId={capaId} dStep="D2" />
            {!readonly && <AttachmentUploader entityType="capa" entityId={capaId} dStep="D2" />}

            <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
        </div>
    );
};

export default D2Pane;
