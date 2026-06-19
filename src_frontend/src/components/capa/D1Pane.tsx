import { Alert, Badge, Button, Col, Form, Row, Spinner } from 'react-bootstrap';

import { groupInspectors, inspectorLabel, type InspectorItem } from './capaInspectors';

export type { InspectorItem } from './capaInspectors';

export interface D1PaneProps {
    champion: number | '';
    setChampion: (v: number | '') => void;
    leader: number | '';
    setLeader: (v: number | '') => void;
    members: number[];
    setMembers: (v: number[]) => void;
    inspectors: InspectorItem[];
    readonly?: boolean;
    onSave: () => void;
    saving: boolean;
}

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

const D1Pane = ({
    champion,
    setChampion,
    leader,
    setLeader,
    members,
    setMembers,
    inspectors,
    readonly,
    onSave,
    saving,
}: D1PaneProps) => {
    const toggleMember = (id: number) => {
        setMembers(members.includes(id) ? members.filter(m => m !== id) : [...members, id]);
    };
    const grouped = groupInspectors(inspectors);

    return (
        <div>
            <Row className="mb-3">
                <Col md={6}>
                    <Form.Group controlId="capa-d1-champion">
                        <Form.Label className="fw-semibold">Champion（指導者）</Form.Label>
                        <Form.Select value={champion} onChange={e => setChampion(e.target.value ? Number(e.target.value) : '')} disabled={readonly}>
                            <option value="">請選擇</option>
                            {Object.entries(grouped).map(([grp, items]) => (
                                <optgroup key={grp} label={grp}>
                                    {items.map(i => <option key={i.id} value={i.id}>{inspectorLabel(i)}</option>)}
                                </optgroup>
                            ))}
                        </Form.Select>
                    </Form.Group>
                </Col>
                <Col md={6}>
                    <Form.Group controlId="capa-d1-leader">
                        <Form.Label className="fw-semibold">Team Leader（負責人）</Form.Label>
                        <Form.Select value={leader} onChange={e => setLeader(e.target.value ? Number(e.target.value) : '')} disabled={readonly}>
                            <option value="">請選擇</option>
                            {Object.entries(grouped).map(([grp, items]) => (
                                <optgroup key={grp} label={grp}>
                                    {items.map(i => <option key={i.id} value={i.id}>{inspectorLabel(i)}</option>)}
                                </optgroup>
                            ))}
                        </Form.Select>
                    </Form.Group>
                </Col>
            </Row>

            <Form.Group className="mb-3">
                <Form.Label className="fw-semibold">團隊成員（可複選）</Form.Label>
                <div>
                    {Object.entries(grouped).map(([grp, items]) => (
                        <div key={grp} className="mb-2">
                            <div className="text-muted small fw-semibold mb-1">{grp}</div>
                            <div className="d-flex flex-wrap gap-3 ps-2">
                                {items.map(i => (
                                    <Form.Check
                                        key={i.id}
                                        type="checkbox"
                                        id={`member-${i.id}`}
                                        label={inspectorLabel(i)}
                                        checked={members.includes(i.id)}
                                        onChange={() => toggleMember(i.id)}
                                        disabled={readonly}
                                    />
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
                {members.length > 0 && (
                    <div className="mt-2 d-flex flex-wrap gap-1">
                        {members.map(mid => {
                            const insp = inspectors.find(i => i.id === mid);
                            return insp ? <Badge key={mid} bg="secondary">{inspectorLabel(insp)}</Badge> : null;
                        })}
                    </div>
                )}
            </Form.Group>

            <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
        </div>
    );
};

export default D1Pane;
