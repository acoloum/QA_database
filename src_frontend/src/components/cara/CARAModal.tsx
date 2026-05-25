import { useState, useEffect } from 'react';
import {
    Modal, Button, Form, Nav, Tab, Row, Col,
    Alert, Badge, ProgressBar, Spinner, Table,
} from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import {
    useCARADetail,
    useUpdateCARAStep,
    useCloseCARA,
    CARA_STEP_LABELS,
} from '../../hooks/useCARA';

// CARA 簡化 5D 步驟
const CARA_STEPS = [2, 3, 4, 6, 8];

interface CARAModalProps {
    show: boolean;
    caraId: number | null;
    onHide: () => void;
}

// Hook：取得檢驗員清單
const useInspectors = () =>
    useQuery({
        queryKey: ['inspectors'],
        queryFn: async () => {
            const res = await api.get('/auth/inspectors');
            return res.data as { id: number; name: string }[];
        },
        staleTime: 10 * 60 * 1000,
    });

// 儲存按鈕列
const SaveBar = ({
    onSave, saving, readonly,
}: { onSave: () => void; saving: boolean; readonly?: boolean }) => {
    if (readonly) {
        return (
            <Alert variant="secondary" className="mt-3 py-2 small">
                此 CARA 已結案，無法編輯。
            </Alert>
        );
    }
    return (
        <div className="d-flex justify-content-end mt-3">
            <Button variant="primary" size="sm" onClick={onSave} disabled={saving}>
                {saving
                    ? <Spinner size="sm" animation="border" className="me-1" />
                    : <i className="bi bi-save me-1" />}
                儲存此步驟
            </Button>
        </div>
    );
};

// 5Why 編輯器（與 CAPAModal 設計一致）
interface FiveWhyRow { why: string; answer: string }
const FiveWhyEditor = ({
    value, onChange, readonly,
}: { value: FiveWhyRow[]; onChange: (rows: FiveWhyRow[]) => void; readonly?: boolean }) => {
    const rows = value?.length >= 3
        ? value
        : Array.from({ length: 3 }, (_, i) => value?.[i] ?? { why: '', answer: '' });

    const update = (idx: number, field: keyof FiveWhyRow, val: string) =>
        onChange(rows.map((r, i) => i === idx ? { ...r, [field]: val } : r));

    return (
        <div>
            <Table size="sm" bordered className="mb-2">
                <thead className="table-light">
                    <tr>
                        <th style={{ width: '60px' }}>#</th>
                        <th>為什麼（Why）</th>
                        <th>原因（Answer）</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r, i) => (
                        <tr key={i}>
                            <td className="text-center fw-bold text-primary">Why {i + 1}</td>
                            <td>
                                <Form.Control size="sm" value={r.why}
                                    onChange={e => update(i, 'why', e.target.value)}
                                    disabled={readonly} placeholder="請輸入為什麼…" />
                            </td>
                            <td>
                                <Form.Control size="sm" value={r.answer}
                                    onChange={e => update(i, 'answer', e.target.value)}
                                    disabled={readonly} placeholder="請輸入原因…" />
                            </td>
                        </tr>
                    ))}
                </tbody>
            </Table>
            {!readonly && (
                <div className="d-flex gap-2">
                    <Button size="sm" variant="outline-secondary"
                        onClick={() => onChange(rows.slice(0, -1))}
                        disabled={rows.length <= 3}>
                        <i className="bi bi-dash" /> 移除一層
                    </Button>
                    <Button size="sm" variant="outline-primary"
                        onClick={() => onChange([...rows, { why: '', answer: '' }])}
                        disabled={rows.length >= 7}>
                        <i className="bi bi-plus" /> 增加一層（最多 7）
                    </Button>
                </div>
            )}
        </div>
    );
};

// 魚骨圖 6M 編輯器
const SIX_M = ['man', 'machine', 'material', 'method', 'measurement', 'environment'];
const SIX_M_LABELS: Record<string, string> = {
    man:         '人員（Man）',
    machine:     '機器（Machine）',
    material:    '材料（Material）',
    method:      '方法（Method）',
    measurement: '量測（Measurement）',
    environment: '環境（Environment）',
};

const FishboneEditor = ({
    value, onChange, readonly,
}: { value: Record<string, string[]>; onChange: (v: Record<string, string[]>) => void; readonly?: boolean }) => {
    const data = value ?? {};
    const updateItem = (m: string, idx: number, val: string) => {
        const arr = [...(data[m] ?? [])];
        arr[idx] = val;
        onChange({ ...data, [m]: arr });
    };
    const addItem = (m: string) => onChange({ ...data, [m]: [...(data[m] ?? []), ''] });
    const removeItem = (m: string, idx: number) =>
        onChange({ ...data, [m]: (data[m] ?? []).filter((_, i) => i !== idx) });

    return (
        <Row className="g-3">
            {SIX_M.map(m => (
                <Col md={4} key={m}>
                    <div className="border rounded p-2">
                        <div className="fw-semibold small mb-2 text-primary">{SIX_M_LABELS[m]}</div>
                        {(data[m] ?? []).map((item, idx) => (
                            <div key={idx} className="d-flex gap-1 mb-1">
                                <Form.Control size="sm" value={item}
                                    onChange={e => updateItem(m, idx, e.target.value)}
                                    placeholder="原因…" disabled={readonly} />
                                {!readonly && (
                                    <Button size="sm" variant="outline-danger"
                                        onClick={() => removeItem(m, idx)}>
                                        <i className="bi bi-x" />
                                    </Button>
                                )}
                            </div>
                        ))}
                        {!readonly && (
                            <Button size="sm" variant="outline-secondary" className="w-100 mt-1"
                                onClick={() => addItem(m)}>
                                <i className="bi bi-plus" /> 新增
                            </Button>
                        )}
                    </div>
                </Col>
            ))}
        </Row>
    );
};

// ── 主元件：CARAModal ────────────────────────────────────────
const CARAModal = ({ show, caraId, onHide }: CARAModalProps) => {
    const { data: cara, isLoading } = useCARADetail(caraId);
    const { data: inspectors = [] }  = useInspectors();
    const updateStep = useUpdateCARAStep();
    const closeMut   = useCloseCARA();

    const [activeTab, setActiveTab] = useState('d2');

    // D1 負責人（儲存在 D2 步驟一起送出）
    const [d1Leader, setD1Leader]   = useState<number | ''>('');
    // D2 5W2H
    const [d2What,    setD2What]    = useState('');
    const [d2Where,   setD2Where]   = useState('');
    const [d2When,    setD2When]    = useState('');
    const [d2Who,     setD2Who]     = useState('');
    const [d2Why,     setD2Why]     = useState('');
    const [d2How,     setD2How]     = useState('');
    const [d2HowMany, setD2HowMany] = useState('');
    // D3
    const [d3Action,  setD3Action]  = useState('');
    const [d3EffDate, setD3EffDate] = useState('');
    const [d3Verif,   setD3Verif]   = useState('');
    // D4
    const [d4Tool,      setD4Tool]      = useState('5why');
    const [d4FiveWhy,   setD4FiveWhy]   = useState<FiveWhyRow[]>([]);
    const [d4Fishbone,  setD4Fishbone]  = useState<Record<string, string[]>>({});
    const [d4RootCause, setD4RootCause] = useState('');
    // D6
    const [d6ImplDate, setD6ImplDate] = useState('');
    const [d6Result,   setD6Result]   = useState('');
    const [d6Verified, setD6Verified] = useState(false);
    // D8
    const [d8Confirm, setD8Confirm] = useState('');

    const isClosed = cara?.status === '已結案';

    useEffect(() => {
        if (!cara) return;
        setD1Leader(cara.D1_leader_id ?? '');
        setD2What(cara.D2_what ?? '');
        setD2Where(cara.D2_where ?? '');
        setD2When(cara.D2_when ?? '');
        setD2Who(cara.D2_who ?? '');
        setD2Why(cara.D2_why ?? '');
        setD2How(cara.D2_how ?? '');
        setD2HowMany(cara.D2_how_many ?? '');
        setD3Action(cara.D3_action ?? '');
        setD3EffDate(cara.D3_effective_date ?? '');
        setD3Verif(cara.D3_verification ?? '');
        setD4Tool(cara.D4_tool ?? '5why');
        setD4FiveWhy((cara.D4_five_why ?? []) as FiveWhyRow[]);
        setD4Fishbone((cara.D4_fishbone ?? {}) as Record<string, string[]>);
        setD4RootCause(cara.D4_root_cause ?? '');
        setD6ImplDate(cara.D6_implement_date ?? '');
        setD6Result(cara.D6_result ?? '');
        setD6Verified(cara.D6_verified ?? false);
        setD8Confirm(cara.D8_confirmation ?? '');
        setActiveTab('d2');
    }, [cara?.id]);

    const saveStep = (stepKey: string, payload: Record<string, unknown>) => {
        if (!caraId) return;
        updateStep.mutate({ id: caraId, data: { step: stepKey, ...payload } });
    };

    const stepDone = (n: number) =>
        cara?.progress?.step_status?.[`D${n}`] === true;

    if (!show) return null;

    return (
        <Modal show={show} onHide={onHide} size="xl" backdrop="static" scrollable>
            <Modal.Header closeButton>
                <Modal.Title>
                    <i className="bi bi-clipboard-check me-2 text-warning" />
                    CARA {cara?.no ?? '—'}
                    {isClosed && (
                        <Badge bg="success" className="ms-2 fs-6">已結案</Badge>
                    )}
                </Modal.Title>
            </Modal.Header>

            <Modal.Body>
                {isLoading ? (
                    <div className="text-center py-5">
                        <Spinner animation="border" />
                        <div className="mt-2 text-muted small">載入中…</div>
                    </div>
                ) : !cara ? (
                    <Alert variant="warning">找不到 CARA 資料</Alert>
                ) : (
                    <>
                        {/* 整體進度條 */}
                        <div className="mb-3">
                            <div className="d-flex justify-content-between align-items-center mb-1">
                                <span className="small fw-semibold">整體進度</span>
                                <span className="small text-muted">
                                    {cara.progress.completed_steps}/{cara.progress.total_steps} 步驟完成
                                </span>
                            </div>
                            <ProgressBar
                                now={cara.progress.percent}
                                variant={
                                    cara.progress.percent >= 100 ? 'success' :
                                    cara.progress.percent >= 50  ? 'primary' : 'warning'
                                }
                                label={`${cara.progress.percent}%`}
                                style={{ height: '12px' }}
                            />
                        </div>

                        {/* 來源 NCMR 資訊 */}
                        {cara.ncmr_info && Object.keys(cara.ncmr_info).length > 0 && (
                            <Alert variant="light" className="border mb-3 py-2">
                                <Row className="small g-2 align-items-center">
                                    <Col xs="auto">
                                        <Badge bg="warning" text="dark">NCMR</Badge>
                                        <span className="ms-1 fw-semibold">#{cara.ncmr_id}</span>
                                    </Col>
                                    {Object.entries(cara.ncmr_info).slice(0, 4).map(([k, v]) => (
                                        <Col xs="auto" key={k}>
                                            <span className="text-muted">{k}：</span>
                                            <span>{v ?? '—'}</span>
                                        </Col>
                                    ))}
                                </Row>
                            </Alert>
                        )}

                        {/* 步驟 Tab */}
                        <Tab.Container activeKey={activeTab} onSelect={k => k && setActiveTab(k)}>
                            <Nav variant="pills" className="mb-3 flex-wrap gap-1">
                                {CARA_STEPS.map(n => (
                                    <Nav.Item key={n}>
                                        <Nav.Link eventKey={`d${n}`} className="py-1 px-2 small">
                                            {stepDone(n)
                                                ? <i className="bi bi-check-circle-fill text-success me-1" />
                                                : <i className="bi bi-circle me-1 text-muted" />}
                                            {CARA_STEP_LABELS[n]}
                                        </Nav.Link>
                                    </Nav.Item>
                                ))}
                            </Nav>

                            <Tab.Content>
                                {/* ── D2 問題描述（含 D1 負責人）────────── */}
                                <Tab.Pane eventKey="d2">
                                    <div>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">負責人</Form.Label>
                                            <Form.Select
                                                value={d1Leader}
                                                onChange={e => setD1Leader(e.target.value ? Number(e.target.value) : '')}
                                                disabled={isClosed}
                                            >
                                                <option value="">請選擇</option>
                                                {inspectors.map(i => (
                                                    <option key={i.id} value={i.id}>{i.name}</option>
                                                ))}
                                            </Form.Select>
                                        </Form.Group>
                                        <hr className="my-2" />
                                        <Row className="g-3 mb-3">
                                            {[
                                                { label: 'What（是什麼）',   val: d2What,    set: setD2What },
                                                { label: 'Where（在哪裡）',  val: d2Where,   set: setD2Where },
                                                { label: 'When（何時）',     val: d2When,    set: setD2When },
                                                { label: 'Who（誰）',        val: d2Who,     set: setD2Who },
                                                { label: 'Why（為何出現）',  val: d2Why,     set: setD2Why },
                                                { label: 'How（如何發現）',  val: d2How,     set: setD2How },
                                                { label: 'How Many（數量）', val: d2HowMany, set: setD2HowMany },
                                            ].map(f => (
                                                <Col md={6} key={f.label}>
                                                    <Form.Group>
                                                        <Form.Label className="fw-semibold small">{f.label}</Form.Label>
                                                        <Form.Control
                                                            as="textarea" rows={2}
                                                            value={f.val}
                                                            onChange={e => f.set(e.target.value)}
                                                            disabled={isClosed}
                                                        />
                                                    </Form.Group>
                                                </Col>
                                            ))}
                                        </Row>
                                        <SaveBar
                                            onSave={() => saveStep('D2', {
                                                D1_leader_id: d1Leader || null,
                                                D2_what: d2What, D2_where: d2Where,
                                                D2_when: d2When, D2_who: d2Who,
                                                D2_why: d2Why,   D2_how: d2How,
                                                D2_how_many: d2HowMany,
                                            })}
                                            saving={updateStep.isPending}
                                            readonly={isClosed}
                                        />
                                    </div>
                                </Tab.Pane>

                                {/* ── D3 暫時對策 ───────────────────────── */}
                                <Tab.Pane eventKey="d3">
                                    <div>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">暫時對策內容</Form.Label>
                                            <Form.Control
                                                as="textarea" rows={4}
                                                value={d3Action}
                                                onChange={e => setD3Action(e.target.value)}
                                                disabled={isClosed}
                                                placeholder="請描述暫時對策…"
                                            />
                                        </Form.Group>
                                        <Row className="mb-3">
                                            <Col md={4}>
                                                <Form.Label className="fw-semibold">生效日期</Form.Label>
                                                <Form.Control type="date" value={d3EffDate}
                                                    onChange={e => setD3EffDate(e.target.value)}
                                                    disabled={isClosed} />
                                            </Col>
                                            <Col md={8}>
                                                <Form.Label className="fw-semibold">有效性驗證</Form.Label>
                                                <Form.Control as="textarea" rows={2} value={d3Verif}
                                                    onChange={e => setD3Verif(e.target.value)}
                                                    disabled={isClosed}
                                                    placeholder="請描述如何驗證暫時對策有效…" />
                                            </Col>
                                        </Row>
                                        <SaveBar
                                            onSave={() => saveStep('D3', {
                                                D3_action: d3Action,
                                                D3_effective_date: d3EffDate || null,
                                                D3_verification: d3Verif,
                                            })}
                                            saving={updateStep.isPending}
                                            readonly={isClosed}
                                        />
                                    </div>
                                </Tab.Pane>

                                {/* ── D4 根本原因 ───────────────────────── */}
                                <Tab.Pane eventKey="d4">
                                    <div>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">分析工具</Form.Label>
                                            <div className="d-flex gap-3">
                                                <Form.Check type="radio" id="cara-tool-5why" label="5 Why" value="5why"
                                                    checked={d4Tool === '5why'} onChange={() => setD4Tool('5why')}
                                                    disabled={isClosed} />
                                                <Form.Check type="radio" id="cara-tool-fishbone" label="魚骨圖（6M）" value="fishbone"
                                                    checked={d4Tool === 'fishbone'} onChange={() => setD4Tool('fishbone')}
                                                    disabled={isClosed} />
                                            </div>
                                        </Form.Group>
                                        {d4Tool === '5why' ? (
                                            <FiveWhyEditor value={d4FiveWhy} onChange={setD4FiveWhy} readonly={isClosed} />
                                        ) : (
                                            <FishboneEditor value={d4Fishbone} onChange={setD4Fishbone} readonly={isClosed} />
                                        )}
                                        <Form.Group className="mt-3">
                                            <Form.Label className="fw-semibold">根本原因（彙整）</Form.Label>
                                            <Form.Control as="textarea" rows={3} value={d4RootCause}
                                                onChange={e => setD4RootCause(e.target.value)}
                                                disabled={isClosed}
                                                placeholder="請彙整根本原因…" />
                                        </Form.Group>
                                        <SaveBar
                                            onSave={() => saveStep('D4', {
                                                D4_tool: d4Tool,
                                                D4_five_why:  d4Tool === '5why'      ? d4FiveWhy  : null,
                                                D4_fishbone:  d4Tool === 'fishbone'  ? d4Fishbone : null,
                                                D4_root_cause: d4RootCause,
                                            })}
                                            saving={updateStep.isPending}
                                            readonly={isClosed}
                                        />
                                    </div>
                                </Tab.Pane>

                                {/* ── D6 實施與驗證 ─────────────────────── */}
                                <Tab.Pane eventKey="d6">
                                    <div>
                                        <Row className="mb-3">
                                            <Col md={4}>
                                                <Form.Label className="fw-semibold">實施日期</Form.Label>
                                                <Form.Control type="date" value={d6ImplDate}
                                                    onChange={e => setD6ImplDate(e.target.value)}
                                                    disabled={isClosed} />
                                            </Col>
                                        </Row>
                                        <Form.Group className="mb-3">
                                            <Form.Label className="fw-semibold">驗證結果</Form.Label>
                                            <Form.Control as="textarea" rows={4} value={d6Result}
                                                onChange={e => setD6Result(e.target.value)}
                                                disabled={isClosed}
                                                placeholder="請描述驗證結果…" />
                                        </Form.Group>
                                        <Form.Check
                                            type="switch" id="cara-d6-verified"
                                            label={<span className="fw-semibold text-success">✓ 確認驗證通過（開放 D8 結案）</span>}
                                            checked={d6Verified}
                                            onChange={e => setD6Verified(e.target.checked)}
                                            disabled={isClosed}
                                            className="mb-3"
                                        />
                                        {d6Verified && (
                                            <Alert variant="success" className="py-2 small">
                                                <i className="bi bi-check-circle-fill me-2" />
                                                D6 驗證已通過，可進行 D8 結案。
                                            </Alert>
                                        )}
                                        <SaveBar
                                            onSave={() => saveStep('D6', {
                                                D6_implement_date: d6ImplDate || null,
                                                D6_result:   d6Result,
                                                D6_verified: d6Verified,
                                            })}
                                            saving={updateStep.isPending}
                                            readonly={isClosed}
                                        />
                                    </div>
                                </Tab.Pane>

                                {/* ── D8 結案確認 ───────────────────────── */}
                                <Tab.Pane eventKey="d8">
                                    {isClosed ? (
                                        <Alert variant="success" className="mt-2">
                                            <i className="bi bi-check-circle-fill me-2" />
                                            此 CARA 已於 {cara.D8_close_date ?? '—'} 結案。
                                        </Alert>
                                    ) : (
                                        <div>
                                            {!d6Verified && (
                                                <Alert variant="warning" className="py-2 small">
                                                    <i className="bi bi-exclamation-triangle-fill me-2" />
                                                    D6 尚未勾選「驗證通過」，無法結案。
                                                </Alert>
                                            )}
                                            <Form.Group className="mb-3">
                                                <Form.Label className="fw-semibold">
                                                    結案確認聲明 <span className="text-danger">*</span>
                                                </Form.Label>
                                                <Form.Control
                                                    as="textarea" rows={4}
                                                    value={d8Confirm}
                                                    onChange={e => setD8Confirm(e.target.value)}
                                                    placeholder="請確認所有改善措施均已實施且有效…"
                                                />
                                            </Form.Group>
                                            <div className="d-flex justify-content-end">
                                                <Button
                                                    variant={d6Verified ? 'danger' : 'secondary'}
                                                    disabled={!d6Verified || !d8Confirm.trim() || closeMut.isPending}
                                                    onClick={() => caraId && closeMut.mutate({
                                                        id: caraId, D8_confirmation: d8Confirm,
                                                    })}
                                                >
                                                    {closeMut.isPending
                                                        ? <><Spinner size="sm" animation="border" className="me-1" />結案中…</>
                                                        : <><i className="bi bi-lock-fill me-1" />確認結案（不可逆）</>
                                                    }
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </Tab.Pane>
                            </Tab.Content>
                        </Tab.Container>
                    </>
                )}
            </Modal.Body>

            <Modal.Footer className="justify-content-between">
                <div className="small text-muted">
                    {cara && (
                        <Badge bg={cara.status === '已結案' ? 'success' : 'primary'}>
                            {cara.status}
                        </Badge>
                    )}
                </div>
                <Button variant="secondary" onClick={onHide}>關閉</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default CARAModal;
