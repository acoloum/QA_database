import { useState, useEffect, useMemo } from 'react';
import {
    Modal, Button, Form, Nav, Tab, Row, Col, Alert,
    Badge, ProgressBar, Spinner, Table,
} from 'react-bootstrap';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import toast from 'react-hot-toast';
import {
    useCapaDetail,
    useUpdateCapaStep,
    useCapaCloseGate,
    useCloseCapa,
    download8DReport,
    CAPA_SEVERITY_VARIANT,
    RIGOR_STEPS,
    D_STEP_LABELS,
} from '../../hooks/useCapa';
import AttachmentUploader from '../common/AttachmentUploader';
import AttachmentList from '../common/AttachmentList';
import type { CAPADetail, CAPASeverity, D7Action } from '../../types';

// ── 介面 Props ────────────────────────────────────────────────
interface CAPAModalProps {
    show: boolean;
    capaId: number | null;
    onHide: () => void;
}

// ── 嚴重度 → 嚴格度 預設聯動 ─────────────────────────────────
const SEVERITY_TO_RIGOR: Record<string, string> = {
    Critical: '完整8D',
    Major:    '完整8D',
    Minor:    '簡化5D',
};

// ── D7 橫展類型 ───────────────────────────────────────────────
const D7_TYPES = [
    { key: 'pfmea',           label: 'PFMEA 更新' },
    { key: 'control_plan',    label: '管制計畫更新' },
    { key: 'sop',             label: 'SOP / WI 更新' },
    { key: 'training',        label: '教育訓練' },
    { key: 'cross_part',      label: '跨料號水平展開' },
    { key: 'customer_notify', label: '客戶通知' },
    { key: 'other',           label: '其他' },
];

// ── 判斷準則選項 ──────────────────────────────────────────────
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

// ── Hook：取得檢驗員清單 ──────────────────────────────────────
const useInspectors = () =>
    useQuery({
        queryKey: ['inspectors'],
        queryFn: async () => {
            const res = await api.get('/inspectors');
            return res.data as { id: number; name: string }[];
        },
        staleTime: 10 * 60 * 1000,
    });

// ══════════════════════════════════════════════════════════════
// 子元件：5 Why 編輯器
// ══════════════════════════════════════════════════════════════
interface FiveWhyRow { why: string; answer: string }
interface FiveWhyEditorProps {
    value: FiveWhyRow[];
    onChange: (rows: FiveWhyRow[]) => void;
    readonly?: boolean;
}

const FiveWhyEditor = ({ value, onChange, readonly }: FiveWhyEditorProps) => {
    const rows: FiveWhyRow[] = value?.length >= 3 ? value : Array.from({ length: 3 }, (_, i) => value?.[i] ?? { why: '', answer: '' });

    const update = (idx: number, field: keyof FiveWhyRow, val: string) => {
        const next = rows.map((r, i) => i === idx ? { ...r, [field]: val } : r);
        onChange(next);
    };

    const addRow = () => {
        if (rows.length < 7) onChange([...rows, { why: '', answer: '' }]);
    };

    const removeRow = () => {
        if (rows.length > 3) onChange(rows.slice(0, -1));
    };

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
                                <Form.Control
                                    size="sm"
                                    value={r.why}
                                    onChange={e => update(i, 'why', e.target.value)}
                                    placeholder="請輸入為什麼…"
                                    disabled={readonly}
                                />
                            </td>
                            <td>
                                <Form.Control
                                    size="sm"
                                    value={r.answer}
                                    onChange={e => update(i, 'answer', e.target.value)}
                                    placeholder="請輸入原因…"
                                    disabled={readonly}
                                />
                            </td>
                        </tr>
                    ))}
                </tbody>
            </Table>
            {!readonly && (
                <div className="d-flex gap-2">
                    <Button size="sm" variant="outline-secondary" onClick={removeRow} disabled={rows.length <= 3}>
                        <i className="bi bi-dash" /> 移除一層
                    </Button>
                    <Button size="sm" variant="outline-primary" onClick={addRow} disabled={rows.length >= 7}>
                        <i className="bi bi-plus" /> 增加一層（最多 7）
                    </Button>
                </div>
            )}
        </div>
    );
};

// ══════════════════════════════════════════════════════════════
// 子元件：魚骨圖 6M 編輯器
// ══════════════════════════════════════════════════════════════
const SIX_M = [
    { key: 'man',         label: '人員（Man）' },
    { key: 'machine',     label: '機器（Machine）' },
    { key: 'material',    label: '材料（Material）' },
    { key: 'method',      label: '方法（Method）' },
    { key: 'measurement', label: '量測（Measurement）' },
    { key: 'environment', label: '環境（Environment）' },
];

interface FishboneEditorProps {
    value: Record<string, string[]>;
    onChange: (val: Record<string, string[]>) => void;
    readonly?: boolean;
}

const FishboneEditor = ({ value, onChange, readonly }: FishboneEditorProps) => {
    const data: Record<string, string[]> = value ?? {};

    const updateItem = (m: string, idx: number, val: string) => {
        const arr = [...(data[m] ?? [])];
        arr[idx] = val;
        onChange({ ...data, [m]: arr });
    };

    const addItem = (m: string) => {
        const arr = [...(data[m] ?? []), ''];
        onChange({ ...data, [m]: arr });
    };

    const removeItem = (m: string, idx: number) => {
        const arr = (data[m] ?? []).filter((_, i) => i !== idx);
        onChange({ ...data, [m]: arr });
    };

    return (
        <Row className="g-3">
            {SIX_M.map(({ key, label }) => (
                <Col md={4} key={key}>
                    <div className="border rounded p-2">
                        <div className="fw-semibold small mb-2 text-primary">{label}</div>
                        {(data[key] ?? []).map((item, idx) => (
                            <div key={idx} className="d-flex gap-1 mb-1">
                                <Form.Control
                                    size="sm"
                                    value={item}
                                    onChange={e => updateItem(key, idx, e.target.value)}
                                    placeholder="原因…"
                                    disabled={readonly}
                                />
                                {!readonly && (
                                    <Button size="sm" variant="outline-danger" onClick={() => removeItem(key, idx)}>
                                        <i className="bi bi-x" />
                                    </Button>
                                )}
                            </div>
                        ))}
                        {!readonly && (
                            <Button size="sm" variant="outline-secondary" className="w-100 mt-1" onClick={() => addItem(key)}>
                                <i className="bi bi-plus" /> 新增
                            </Button>
                        )}
                    </div>
                </Col>
            ))}
        </Row>
    );
};

// ══════════════════════════════════════════════════════════════
// 主元件：CAPAModal
// ══════════════════════════════════════════════════════════════
const CAPAModal = ({ show, capaId, onHide }: CAPAModalProps) => {
    const { data: capa, isLoading } = useCapaDetail(capaId);
    const { data: inspectors = [] }  = useInspectors();
    const updateStep  = useUpdateCapaStep();
    const closeGate   = useCapaCloseGate(capaId);
    const closeMut    = useCloseCapa();

    // 目前顯示的 Tab
    const [activeTab, setActiveTab] = useState('d0');

    // 各步驟草稿狀態
    const [d0Symptom,   setD0Symptom]   = useState('');
    const [d0Criteria,  setD0Criteria]  = useState<string[]>([]);
    const [d0Severity,  setD0Severity]  = useState<CAPASeverity | ''>('');
    const [d0Rigor,     setD0Rigor]     = useState('完整8D');
    const [d0Deadline,  setD0Deadline]  = useState('');

    const [d1Champion,  setD1Champion]  = useState<number | ''>('');
    const [d1Leader,    setD1Leader]    = useState<number | ''>('');
    const [d1Members,   setD1Members]   = useState<number[]>([]);

    const [d2What,      setD2What]      = useState('');
    const [d2Where,     setD2Where]     = useState('');
    const [d2When,      setD2When]      = useState('');
    const [d2Who,       setD2Who]       = useState('');
    const [d2Why,       setD2Why]       = useState('');
    const [d2How,       setD2How]       = useState('');
    const [d2HowMany,   setD2HowMany]   = useState('');

    const [d3Action,    setD3Action]    = useState('');
    const [d3EffDate,   setD3EffDate]   = useState('');
    const [d3Verif,     setD3Verif]     = useState('');

    const [d4Tool,      setD4Tool]      = useState('5why');
    const [d4FiveWhy,   setD4FiveWhy]   = useState<{ why: string; answer: string }[]>([]);
    const [d4Fishbone,  setD4Fishbone]  = useState<Record<string, string[]>>({});
    const [d4RootCause, setD4RootCause] = useState('');

    const [d5Action,    setD5Action]    = useState('');
    const [d5PlannedDate, setD5PlannedDate] = useState('');
    const [d5VerifyPlan, setD5VerifyPlan] = useState('');

    const [d6ImplDate,  setD6ImplDate]  = useState('');
    const [d6Result,    setD6Result]    = useState('');
    const [d6Verified,  setD6Verified]  = useState(false);

    const [d7Actions,   setD7Actions]   = useState<D7Action[]>([]);

    const [d8Confirm,   setD8Confirm]   = useState('');
    const [d8Recog,     setD8Recog]     = useState('');

    // 唯讀模式（已結案）
    const isClosed = capa?.status === '已結案';

    // 從伺服器資料初始化草稿
    useEffect(() => {
        if (!capa) return;
        setD0Symptom(capa.D0_symptom ?? '');
        setD0Criteria(capa.D0_criteria ?? []);
        setD0Severity((capa.D0_severity ?? '') as CAPASeverity | '');
        setD0Rigor(capa.rigor ?? '完整8D');
        setD0Deadline(capa.D0_deadline ?? '');

        setD1Champion(capa.D1_champion_id ?? '');
        setD1Leader(capa.D1_leader_id ?? '');
        setD1Members(capa.D1_members ?? []);

        // D2：優先用已儲存值；若欄位為 null（從未填寫）則從來源資訊帶入
        const si = (capa.source_info ?? {}) as Record<string, string | number | null>;
        const isNcmr = capa.source_type === 'ncmr';
        setD2What(    capa.D2_what     ?? ((si.defect        as string) ?? ''));
        setD2Where(   capa.D2_where    ?? (isNcmr ? (si.source        as string ?? '') : ''));
        setD2When(    capa.D2_when     ?? '');
        setD2Who(     capa.D2_who      ?? (isNcmr ? (si.vendor        as string ?? '') : ''));
        setD2Why(     capa.D2_why      ?? '');
        setD2How(     capa.D2_how      ?? (isNcmr ? (si.defect_detail as string ?? '') : ''));
        setD2HowMany( capa.D2_how_many ?? (isNcmr && si.defect_qty != null
            ? `${si.defect_qty} / ${si.total_qty ?? '?'} 支` : ''));

        setD3Action(capa.D3_action ?? '');
        setD3EffDate(capa.D3_effective_date ?? '');
        setD3Verif(capa.D3_verification ?? '');

        setD4Tool(capa.D4_tool ?? '5why');
        setD4FiveWhy((capa.D4_five_why ?? []) as { why: string; answer: string }[]);
        setD4Fishbone((capa.D4_fishbone ?? {}) as Record<string, string[]>);
        setD4RootCause(capa.D4_root_cause ?? '');

        setD5Action(capa.D5_action ?? '');
        setD5PlannedDate(capa.D5_planned_date ?? '');
        setD5VerifyPlan(capa.D5_verify_plan ?? '');

        setD6ImplDate(capa.D6_implement_date ?? '');
        setD6Result(capa.D6_result ?? '');
        setD6Verified(capa.D6_verified ?? false);

        // D7 Actions 初始化：從伺服器資料合併 D7_TYPES
        const serverActions = capa.D7_actions ?? [];
        const merged = D7_TYPES.map(t => {
            const found = serverActions.find(a => a.type === t.key);
            return found ?? { type: t.key, checked: false, assignee_id: null, due_date: null, description: '', part_nos: '' };
        });
        setD7Actions(merged);

        setD8Confirm(capa.D8_confirmation ?? '');
        setD8Recog(capa.D8_recognition ?? '');

        // 預設第一個有效 Tab
        const steps = RIGOR_STEPS[capa.rigor] ?? [0, 1, 2, 3, 4, 5, 6, 7, 8];
        setActiveTab(`d${steps[0]}`);
    }, [capa]);

    // 嚴重度聯動嚴格度（可手動 override）
    useEffect(() => {
        if (d0Severity && !isClosed) {
            setD0Rigor(SEVERITY_TO_RIGOR[d0Severity] ?? '完整8D');
        }
    }, [d0Severity, isClosed]);

    // 顯示的步驟清單
    const steps = useMemo(
        () => RIGOR_STEPS[d0Rigor] ?? [0, 1, 2, 3, 4, 5, 6, 7, 8],
        [d0Rigor]
    );

    // 步驟儲存
    const saveStep = (stepKey: string, payload: Record<string, unknown>) => {
        if (!capaId) return;
        updateStep.mutate({ id: capaId, data: { step: stepKey, ...payload } });
    };

    // 切換 D7 勾選
    const toggleD7 = (idx: number, checked: boolean) => {
        setD7Actions(prev => prev.map((a, i) => i === idx ? { ...a, checked } : a));
    };
    const updateD7Field = (idx: number, field: keyof D7Action, val: unknown) => {
        setD7Actions(prev => prev.map((a, i) => i === idx ? { ...a, [field]: val } : a));
    };

    // 結案
    const handleClose8D = () => {
        if (!capaId || !d8Confirm.trim()) return;
        closeMut.mutate({ id: capaId, D8_confirmation: d8Confirm, D8_recognition: d8Recog });
    };

    // 步驟完成度（用 server step_status）
    const stepDone = (n: number) =>
        capa?.progress?.step_status?.[`D${n}`] === true;

    if (!show) return null;

    return (
        <Modal show={show} onHide={onHide} size="xl" backdrop="static" scrollable>
            <Modal.Header closeButton>
                <Modal.Title>
                    <i className="bi bi-shield-check me-2 text-primary" />
                    CAPA {capa?.no ?? '—'}
                    {isClosed && <Badge bg="success" className="ms-2 fs-6">已結案</Badge>}
                </Modal.Title>
            </Modal.Header>

            <Modal.Body>
                {isLoading ? (
                    <div className="text-center py-5">
                        <Spinner animation="border" />
                        <div className="mt-2 text-muted small">載入中…</div>
                    </div>
                ) : !capa ? (
                    <Alert variant="warning">找不到 CAPA 資料</Alert>
                ) : (
                    <>
                        {/* 整體進度條 */}
                        <div className="mb-3">
                            <div className="d-flex justify-content-between align-items-center mb-1">
                                <span className="small fw-semibold">整體進度</span>
                                <span className="small text-muted">
                                    {capa.progress.completed_steps}/{capa.progress.total_steps} 步驟完成
                                </span>
                            </div>
                            <ProgressBar
                                now={capa.progress.percent}
                                variant={capa.progress.percent >= 100 ? 'success' : capa.progress.percent >= 50 ? 'primary' : 'warning'}
                                label={`${capa.progress.percent}%`}
                                style={{ height: '12px' }}
                            />
                        </div>

                        {/* 來源資訊 */}
                        <SourceInfoBanner capa={capa} />

                        {/* 步驟 Tab 列 */}
                        <Tab.Container activeKey={activeTab} onSelect={k => k && setActiveTab(k)}>
                            <Nav variant="pills" className="mb-3 flex-wrap gap-1">
                                {steps.map(n => (
                                    <Nav.Item key={n}>
                                        <Nav.Link eventKey={`d${n}`} className="py-1 px-2 small">
                                            {stepDone(n)
                                                ? <i className="bi bi-check-circle-fill text-success me-1" />
                                                : <i className="bi bi-circle me-1 text-muted" />
                                            }
                                            {D_STEP_LABELS[n]}
                                        </Nav.Link>
                                    </Nav.Item>
                                ))}
                            </Nav>

                            <Tab.Content>
                                {/* ── D0 緊急應對 ──────────────────────────── */}
                                <Tab.Pane eventKey="d0">
                                    <D0Pane
                                        symptom={d0Symptom} setSymptom={setD0Symptom}
                                        criteria={d0Criteria} setCriteria={setD0Criteria}
                                        severity={d0Severity} setSeverity={setD0Severity}
                                        rigor={d0Rigor} setRigor={setD0Rigor}
                                        deadline={d0Deadline} setDeadline={setD0Deadline}
                                        readonly={isClosed}
                                        capaId={capa.id}
                                        onSave={() => saveStep('D0', {
                                            D0_symptom: d0Symptom,
                                            D0_criteria: d0Criteria,
                                            D0_severity: d0Severity || null,
                                            D0_deadline: d0Deadline || null,
                                            rigor: d0Rigor,
                                        })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D1 成立團隊 ──────────────────────────── */}
                                <Tab.Pane eventKey="d1">
                                    <D1Pane
                                        champion={d1Champion} setChampion={setD1Champion}
                                        leader={d1Leader} setLeader={setD1Leader}
                                        members={d1Members} setMembers={setD1Members}
                                        inspectors={inspectors}
                                        readonly={isClosed}
                                        onSave={() => saveStep('D1', {
                                            D1_champion_id: d1Champion || null,
                                            D1_leader_id: d1Leader || null,
                                            D1_members: d1Members,
                                        })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D2 問題描述（5W2H）───────────────────── */}
                                <Tab.Pane eventKey="d2">
                                    <D2Pane
                                        what={d2What} setWhat={setD2What}
                                        where={d2Where} setWhere={setD2Where}
                                        when={d2When} setWhen={setD2When}
                                        who={d2Who} setWho={setD2Who}
                                        why={d2Why} setWhy={setD2Why}
                                        how={d2How} setHow={setD2How}
                                        howMany={d2HowMany} setHowMany={setD2HowMany}
                                        readonly={isClosed}
                                        capaId={capa.id}
                                        onSave={() => saveStep('D2', {
                                            D2_what: d2What, D2_where: d2Where,
                                            D2_when: d2When, D2_who: d2Who,
                                            D2_why: d2Why, D2_how: d2How,
                                            D2_how_many: d2HowMany,
                                        })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D3 暫時對策 ──────────────────────────── */}
                                <Tab.Pane eventKey="d3">
                                    <D3Pane
                                        action={d3Action} setAction={setD3Action}
                                        effectiveDate={d3EffDate} setEffectiveDate={setD3EffDate}
                                        verification={d3Verif} setVerification={setD3Verif}
                                        readonly={isClosed}
                                        capaId={capa.id}
                                        onSave={() => saveStep('D3', {
                                            D3_action: d3Action,
                                            D3_effective_date: d3EffDate || null,
                                            D3_verification: d3Verif,
                                        })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D4 根本原因 ──────────────────────────── */}
                                <Tab.Pane eventKey="d4">
                                    <D4Pane
                                        tool={d4Tool} setTool={setD4Tool}
                                        fiveWhy={d4FiveWhy} setFiveWhy={setD4FiveWhy}
                                        fishbone={d4Fishbone} setFishbone={setD4Fishbone}
                                        rootCause={d4RootCause} setRootCause={setD4RootCause}
                                        readonly={isClosed}
                                        onSave={() => saveStep('D4', {
                                            D4_tool: d4Tool,
                                            D4_five_why: d4Tool === '5why' ? d4FiveWhy : null,
                                            D4_fishbone: d4Tool === 'fishbone' ? d4Fishbone : null,
                                            D4_root_cause: d4RootCause,
                                        })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D5 永久對策 ──────────────────────────── */}
                                <Tab.Pane eventKey="d5">
                                    <D5Pane
                                        action={d5Action} setAction={setD5Action}
                                        plannedDate={d5PlannedDate} setPlannedDate={setD5PlannedDate}
                                        verifyPlan={d5VerifyPlan} setVerifyPlan={setD5VerifyPlan}
                                        readonly={isClosed}
                                        onSave={() => saveStep('D5', {
                                            D5_action: d5Action,
                                            D5_planned_date: d5PlannedDate || null,
                                            D5_verify_plan: d5VerifyPlan,
                                        })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D6 實施驗證 ──────────────────────────── */}
                                <Tab.Pane eventKey="d6">
                                    <D6Pane
                                        implDate={d6ImplDate} setImplDate={setD6ImplDate}
                                        result={d6Result} setResult={setD6Result}
                                        verified={d6Verified} setVerified={setD6Verified}
                                        readonly={isClosed}
                                        capaId={capa.id}
                                        onSave={() => saveStep('D6', {
                                            D6_implement_date: d6ImplDate || null,
                                            D6_result: d6Result,
                                            D6_verified: d6Verified,
                                        })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D7 橫向展開 ──────────────────────────── */}
                                <Tab.Pane eventKey="d7">
                                    <D7Pane
                                        actions={d7Actions}
                                        tasks={capa.tasks ?? []}
                                        inspectors={inspectors}
                                        readonly={isClosed}
                                        onToggle={toggleD7}
                                        onUpdateField={updateD7Field}
                                        onSave={() => saveStep('D7', { D7_actions: d7Actions })}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D8 結案確認 ──────────────────────────── */}
                                <Tab.Pane eventKey="d8">
                                    <D8Pane
                                        capaId={capa.id}
                                        confirmation={d8Confirm} setConfirmation={setD8Confirm}
                                        recognition={d8Recog} setRecognition={setD8Recog}
                                        closeGateData={closeGate.data}
                                        closeGateLoading={closeGate.isLoading}
                                        isClosed={isClosed}
                                        closeDate={capa.D8_close_date}
                                        onClose={handleClose8D}
                                        closing={closeMut.isPending}
                                    />
                                </Tab.Pane>
                            </Tab.Content>
                        </Tab.Container>
                    </>
                )}
            </Modal.Body>

            <Modal.Footer className="justify-content-between">
                <div className="small text-muted">
                    {capa && (
                        <>
                            <Badge bg={capa.rigor === '完整8D' ? 'primary' : 'info'} className="me-2">
                                {capa.rigor}
                            </Badge>
                            {capa.D0_severity && (
                                <Badge bg={CAPA_SEVERITY_VARIANT[capa.D0_severity] ?? 'secondary'}>
                                    {capa.D0_severity}
                                </Badge>
                            )}
                        </>
                    )}
                </div>
                <div className="d-flex gap-2">
                    {capa && !isLoading && (
                        <>
                            <Button
                                variant="outline-success"
                                size="sm"
                                onClick={async () => {
                                    try {
                                        await download8DReport(capa.id, 'excel');
                                    } catch {
                                        toast.error('Excel 匯出失敗');
                                    }
                                }}
                            >
                                <i className="bi bi-file-earmark-excel me-1" />
                                匯出 Excel
                            </Button>
                            <Button
                                variant="outline-danger"
                                size="sm"
                                onClick={async () => {
                                    try {
                                        await download8DReport(capa.id, 'pdf');
                                    } catch {
                                        toast.error('PDF 匯出失敗');
                                    }
                                }}
                            >
                                <i className="bi bi-file-earmark-pdf me-1" />
                                匯出 PDF
                            </Button>
                        </>
                    )}
                    <Button variant="secondary" onClick={onHide}>關閉</Button>
                </div>
            </Modal.Footer>
        </Modal>
    );
};

// ══════════════════════════════════════════════════════════════
// 子元件：來源資訊 Banner
// ══════════════════════════════════════════════════════════════
const SourceInfoBanner = ({ capa }: { capa: CAPADetail }) => {
    const info = capa.source_info ?? {};
    return (
        <Alert variant="light" className="border mb-3 py-2">
            <Row className="small g-2 align-items-center">
                <Col xs="auto">
                    <Badge bg={capa.source_type === 'ncmr' ? 'warning' : 'info'} text="dark">
                        {capa.source_type === 'ncmr' ? 'NCMR' : '客訴'}
                    </Badge>
                    <span className="ms-1 fw-semibold">#{capa.source_id}</span>
                </Col>
                {Object.entries(info).slice(0, 4).map(([k, v]) => (
                    <Col xs="auto" key={k}>
                        <span className="text-muted">{k}：</span>
                        <span>{v ?? '—'}</span>
                    </Col>
                ))}
            </Row>
        </Alert>
    );
};

// ══════════════════════════════════════════════════════════════
// 子元件：儲存按鈕列
// ══════════════════════════════════════════════════════════════
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

// ══════════════════════════════════════════════════════════════
// 子元件：D0 緊急應對
// ══════════════════════════════════════════════════════════════
interface D0Props {
    symptom: string; setSymptom: (v: string) => void;
    criteria: string[]; setCriteria: (v: string[]) => void;
    severity: CAPASeverity | ''; setSeverity: (v: CAPASeverity | '') => void;
    rigor: string; setRigor: (v: string) => void;
    deadline: string; setDeadline: (v: string) => void;
    readonly?: boolean; capaId: number;
    onSave: () => void; saving: boolean;
}

const D0Pane = ({ symptom, setSymptom, criteria, setCriteria, severity, setSeverity, rigor, setRigor, deadline, setDeadline, readonly, capaId, onSave, saving }: D0Props) => {
    const toggleCriteria = (val: string) => {
        setCriteria(criteria.includes(val) ? criteria.filter(c => c !== val) : [...criteria, val]);
    };

    return (
        <div>
            <Form.Group className="mb-3">
                <Form.Label className="fw-semibold">症狀描述</Form.Label>
                <Form.Control
                    as="textarea" rows={3}
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
                            key={opt} type="checkbox" id={`criteria-${opt}`}
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
                    <Form.Label className="fw-semibold">嚴重度</Form.Label>
                    <Form.Select value={severity} onChange={e => setSeverity(e.target.value as CAPASeverity | '')} disabled={readonly}>
                        <option value="">請選擇</option>
                        <option value="Critical">Critical（緊急）</option>
                        <option value="Major">Major（重要）</option>
                        <option value="Minor">Minor（輕微）</option>
                    </Form.Select>
                </Col>
                <Col md={4}>
                    <Form.Label className="fw-semibold">嚴格度（可 Override）</Form.Label>
                    <Form.Select value={rigor} onChange={e => setRigor(e.target.value)} disabled={readonly}>
                        <option value="完整8D">完整 8D（D0–D8）</option>
                        <option value="簡化5D">簡化 5D（D2,D3,D4,D6,D8）</option>
                    </Form.Select>
                </Col>
                <Col md={4}>
                    <Form.Label className="fw-semibold">客戶要求結案日</Form.Label>
                    <Form.Control type="date" value={deadline} onChange={e => setDeadline(e.target.value)} disabled={readonly} />
                </Col>
            </Row>

            <hr className="my-3" />
            <h6 className="mb-2 text-muted small">D0 相關附件</h6>
            <AttachmentList entityType="capa" entityId={capaId} dStep="D0" />
            {!readonly && <AttachmentUploader entityType="capa" entityId={capaId} dStep="D0" />}

            <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
        </div>
    );
};

// ══════════════════════════════════════════════════════════════
// 子元件：D1 成立團隊
// ══════════════════════════════════════════════════════════════
interface D1Props {
    champion: number | ''; setChampion: (v: number | '') => void;
    leader: number | ''; setLeader: (v: number | '') => void;
    members: number[]; setMembers: (v: number[]) => void;
    inspectors: { id: number; name: string }[];
    readonly?: boolean;
    onSave: () => void; saving: boolean;
}

const D1Pane = ({ champion, setChampion, leader, setLeader, members, setMembers, inspectors, readonly, onSave, saving }: D1Props) => {
    const toggleMember = (id: number) => {
        setMembers(members.includes(id) ? members.filter(m => m !== id) : [...members, id]);
    };

    return (
        <div>
            <Row className="mb-3">
                <Col md={6}>
                    <Form.Label className="fw-semibold">Champion（指導者）</Form.Label>
                    <Form.Select value={champion} onChange={e => setChampion(e.target.value ? Number(e.target.value) : '')} disabled={readonly}>
                        <option value="">請選擇</option>
                        {inspectors.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                    </Form.Select>
                </Col>
                <Col md={6}>
                    <Form.Label className="fw-semibold">Team Leader（負責人）</Form.Label>
                    <Form.Select value={leader} onChange={e => setLeader(e.target.value ? Number(e.target.value) : '')} disabled={readonly}>
                        <option value="">請選擇</option>
                        {inspectors.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                    </Form.Select>
                </Col>
            </Row>

            <Form.Group className="mb-3">
                <Form.Label className="fw-semibold">團隊成員（可複選）</Form.Label>
                <div className="d-flex flex-wrap gap-3">
                    {inspectors.map(i => (
                        <Form.Check
                            key={i.id} type="checkbox" id={`member-${i.id}`}
                            label={i.name}
                            checked={members.includes(i.id)}
                            onChange={() => toggleMember(i.id)}
                            disabled={readonly}
                        />
                    ))}
                </div>
                {members.length > 0 && (
                    <div className="mt-2 d-flex flex-wrap gap-1">
                        {members.map(mid => {
                            const insp = inspectors.find(i => i.id === mid);
                            return insp ? <Badge key={mid} bg="secondary">{insp.name}</Badge> : null;
                        })}
                    </div>
                )}
            </Form.Group>

            <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
        </div>
    );
};

// ══════════════════════════════════════════════════════════════
// 子元件：D2 問題描述（5W2H）
// ══════════════════════════════════════════════════════════════
interface D2Props {
    what: string; setWhat: (v: string) => void;
    where: string; setWhere: (v: string) => void;
    when: string; setWhen: (v: string) => void;
    who: string; setWho: (v: string) => void;
    why: string; setWhy: (v: string) => void;
    how: string; setHow: (v: string) => void;
    howMany: string; setHowMany: (v: string) => void;
    readonly?: boolean; capaId: number;
    onSave: () => void; saving: boolean;
}

const D2Pane = ({ what, setWhat, where, setWhere, when, setWhen, who, setWho, why, setWhy, how, setHow, howMany, setHowMany, readonly, capaId, onSave, saving }: D2Props) => {
    const fields = [
        { label: 'What（是什麼）',    value: what,    set: setWhat },
        { label: 'Where（在哪裡）',   value: where,   set: setWhere },
        { label: 'When（何時）',      value: when,    set: setWhen },
        { label: 'Who（誰）',         value: who,     set: setWho },
        { label: 'Why（為何出現）',   value: why,     set: setWhy },
        { label: 'How（如何發現）',   value: how,     set: setHow },
        { label: 'How Many（數量）',  value: howMany, set: setHowMany },
    ];

    return (
        <div>
            <Row className="g-3 mb-3">
                {fields.map(f => (
                    <Col md={6} key={f.label}>
                        <Form.Group>
                            <Form.Label className="fw-semibold small">{f.label}</Form.Label>
                            <Form.Control
                                as="textarea" rows={2}
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

// ══════════════════════════════════════════════════════════════
// 子元件：D3 暫時對策
// ══════════════════════════════════════════════════════════════
interface D3Props {
    action: string; setAction: (v: string) => void;
    effectiveDate: string; setEffectiveDate: (v: string) => void;
    verification: string; setVerification: (v: string) => void;
    readonly?: boolean; capaId: number;
    onSave: () => void; saving: boolean;
}

const D3Pane = ({ action, setAction, effectiveDate, setEffectiveDate, verification, setVerification, readonly, capaId, onSave, saving }: D3Props) => (
    <div>
        <Form.Group className="mb-3">
            <Form.Label className="fw-semibold">暫時對策內容</Form.Label>
            <Form.Control as="textarea" rows={4} value={action} onChange={e => setAction(e.target.value)} disabled={readonly} placeholder="請描述暫時對策…" />
        </Form.Group>
        <Row className="mb-3">
            <Col md={4}>
                <Form.Label className="fw-semibold">生效日期</Form.Label>
                <Form.Control type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} disabled={readonly} />
            </Col>
            <Col md={8}>
                <Form.Label className="fw-semibold">有效性驗證</Form.Label>
                <Form.Control as="textarea" rows={2} value={verification} onChange={e => setVerification(e.target.value)} disabled={readonly} placeholder="請描述如何驗證暫時對策有效…" />
            </Col>
        </Row>

        <hr className="my-3" />
        <h6 className="mb-2 text-muted small">D3 相關附件</h6>
        <AttachmentList entityType="capa" entityId={capaId} dStep="D3" />
        {!readonly && <AttachmentUploader entityType="capa" entityId={capaId} dStep="D3" />}

        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

// ══════════════════════════════════════════════════════════════
// 子元件：D4 根本原因分析
// ══════════════════════════════════════════════════════════════
interface D4Props {
    tool: string; setTool: (v: string) => void;
    fiveWhy: { why: string; answer: string }[]; setFiveWhy: (v: { why: string; answer: string }[]) => void;
    fishbone: Record<string, string[]>; setFishbone: (v: Record<string, string[]>) => void;
    rootCause: string; setRootCause: (v: string) => void;
    readonly?: boolean;
    onSave: () => void; saving: boolean;
}

const D4Pane = ({ tool, setTool, fiveWhy, setFiveWhy, fishbone, setFishbone, rootCause, setRootCause, readonly, onSave, saving }: D4Props) => (
    <div>
        <Form.Group className="mb-3">
            <Form.Label className="fw-semibold">分析工具</Form.Label>
            <div className="d-flex gap-3">
                <Form.Check type="radio" id="tool-5why" label="5 Why" value="5why"
                    checked={tool === '5why'} onChange={() => setTool('5why')} disabled={readonly} />
                <Form.Check type="radio" id="tool-fishbone" label="魚骨圖（6M）" value="fishbone"
                    checked={tool === 'fishbone'} onChange={() => setTool('fishbone')} disabled={readonly} />
            </div>
        </Form.Group>

        {tool === '5why' ? (
            <FiveWhyEditor value={fiveWhy} onChange={setFiveWhy} readonly={readonly} />
        ) : (
            <FishboneEditor value={fishbone} onChange={setFishbone} readonly={readonly} />
        )}

        <Form.Group className="mt-3">
            <Form.Label className="fw-semibold">根本原因（彙整）</Form.Label>
            <Form.Control as="textarea" rows={3} value={rootCause} onChange={e => setRootCause(e.target.value)} disabled={readonly} placeholder="請彙整根本原因…" />
        </Form.Group>

        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

// ══════════════════════════════════════════════════════════════
// 子元件：D5 永久對策
// ══════════════════════════════════════════════════════════════
interface D5Props {
    action: string; setAction: (v: string) => void;
    plannedDate: string; setPlannedDate: (v: string) => void;
    verifyPlan: string; setVerifyPlan: (v: string) => void;
    readonly?: boolean;
    onSave: () => void; saving: boolean;
}

const D5Pane = ({ action, setAction, plannedDate, setPlannedDate, verifyPlan, setVerifyPlan, readonly, onSave, saving }: D5Props) => (
    <div>
        <Form.Group className="mb-3">
            <Form.Label className="fw-semibold">永久對策內容</Form.Label>
            <Form.Control as="textarea" rows={4} value={action} onChange={e => setAction(e.target.value)} disabled={readonly} placeholder="請描述永久對策…" />
        </Form.Group>
        <Row className="mb-3">
            <Col md={4}>
                <Form.Label className="fw-semibold">預計實施日</Form.Label>
                <Form.Control type="date" value={plannedDate} onChange={e => setPlannedDate(e.target.value)} disabled={readonly} />
            </Col>
            <Col md={8}>
                <Form.Label className="fw-semibold">驗證計畫</Form.Label>
                <Form.Control as="textarea" rows={2} value={verifyPlan} onChange={e => setVerifyPlan(e.target.value)} disabled={readonly} placeholder="請描述驗證計畫…" />
            </Col>
        </Row>
        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

// ══════════════════════════════════════════════════════════════
// 子元件：D6 實施與驗證
// ══════════════════════════════════════════════════════════════
interface D6Props {
    implDate: string; setImplDate: (v: string) => void;
    result: string; setResult: (v: string) => void;
    verified: boolean; setVerified: (v: boolean) => void;
    readonly?: boolean; capaId: number;
    onSave: () => void; saving: boolean;
}

const D6Pane = ({ implDate, setImplDate, result, setResult, verified, setVerified, readonly, capaId, onSave, saving }: D6Props) => (
    <div>
        <Row className="mb-3">
            <Col md={4}>
                <Form.Label className="fw-semibold">實施日期</Form.Label>
                <Form.Control type="date" value={implDate} onChange={e => setImplDate(e.target.value)} disabled={readonly} />
            </Col>
        </Row>
        <Form.Group className="mb-3">
            <Form.Label className="fw-semibold">驗證結果</Form.Label>
            <Form.Control as="textarea" rows={4} value={result} onChange={e => setResult(e.target.value)} disabled={readonly} placeholder="請描述驗證結果…" />
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

// ══════════════════════════════════════════════════════════════
// 子元件：D7 橫向展開
// ══════════════════════════════════════════════════════════════
interface D7Props {
    actions: D7Action[];
    tasks: import('../../types').ActionTask[];
    inspectors: { id: number; name: string }[];
    readonly?: boolean;
    onToggle: (idx: number, checked: boolean) => void;
    onUpdateField: (idx: number, field: keyof D7Action, val: unknown) => void;
    onSave: () => void; saving: boolean;
}

const TASK_STATUS_BADGE: Record<string, string> = {
    pending: 'secondary', in_progress: 'primary', completed: 'success', waived: 'warning',
};
const TASK_STATUS_LABEL: Record<string, string> = {
    pending: '待處理', in_progress: '進行中', completed: '已完成', waived: '豁免',
};

const D7Pane = ({ actions, tasks, inspectors, readonly, onToggle, onUpdateField, onSave, saving }: D7Props) => (
    <div>
        <Alert variant="info" className="py-2 small">
            <i className="bi bi-info-circle me-1" />
            勾選需要橫展的項目，儲存後系統將自動產生對應任務（ActionTask）。
        </Alert>

        <Table size="sm" bordered>
            <thead className="table-light">
                <tr>
                    <th style={{ width: '30px' }}></th>
                    <th>橫展類型</th>
                    <th>指派人</th>
                    <th>期限</th>
                    <th>說明</th>
                    <th>任務狀態</th>
                </tr>
            </thead>
            <tbody>
                {actions.map((a, idx) => {
                    const typeLabel = D7_TYPES.find(t => t.key === a.type)?.label ?? a.type;
                    // 找對應的任務記錄
                    const relTask = tasks.find(t => t.category === a.type);
                    return (
                        <tr key={a.type} className={a.checked ? '' : 'text-muted'}>
                            <td className="text-center">
                                <Form.Check
                                    type="checkbox"
                                    checked={a.checked}
                                    onChange={e => onToggle(idx, e.target.checked)}
                                    disabled={readonly}
                                />
                            </td>
                            <td className="small fw-semibold">{typeLabel}</td>
                            <td>
                                {a.checked && (
                                    <Form.Select
                                        size="sm"
                                        value={a.assignee_id ?? ''}
                                        onChange={e => onUpdateField(idx, 'assignee_id', e.target.value ? Number(e.target.value) : null)}
                                        disabled={readonly}
                                    >
                                        <option value="">請選擇</option>
                                        {inspectors.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                                    </Form.Select>
                                )}
                            </td>
                            <td>
                                {a.checked && (
                                    <Form.Control
                                        type="date" size="sm"
                                        value={a.due_date ?? ''}
                                        onChange={e => onUpdateField(idx, 'due_date', e.target.value || null)}
                                        disabled={readonly}
                                    />
                                )}
                            </td>
                            <td>
                                {a.checked && (
                                    <Form.Control
                                        size="sm"
                                        value={a.description ?? ''}
                                        onChange={e => onUpdateField(idx, 'description', e.target.value)}
                                        disabled={readonly}
                                        placeholder="備註…"
                                    />
                                )}
                            </td>
                            <td>
                                {relTask ? (
                                    <Badge bg={TASK_STATUS_BADGE[relTask.status] ?? 'secondary'}>
                                        {TASK_STATUS_LABEL[relTask.status] ?? relTask.status}
                                    </Badge>
                                ) : a.checked ? (
                                    <span className="small text-muted">儲存後建立</span>
                                ) : null}
                            </td>
                        </tr>
                    );
                })}
            </tbody>
        </Table>

        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

// ══════════════════════════════════════════════════════════════
// 子元件：D8 結案確認
// ══════════════════════════════════════════════════════════════
interface D8Props {
    capaId: number;
    confirmation: string; setConfirmation: (v: string) => void;
    recognition: string; setRecognition: (v: string) => void;
    closeGateData?: { can_close: boolean; d6_passed: boolean; blocking_tasks: unknown[] } | null;
    closeGateLoading: boolean;
    isClosed: boolean; closeDate?: string | null;
    onClose: () => void; closing: boolean;
}

const D8Pane = ({ confirmation, setConfirmation, recognition, setRecognition, closeGateData, closeGateLoading, isClosed, closeDate, onClose, closing }: D8Props) => {
    const canClose = closeGateData?.can_close === true;
    const blockCount = closeGateData?.blocking_tasks?.length ?? 0;

    if (isClosed) {
        return (
            <Alert variant="success" className="mt-2">
                <i className="bi bi-check-circle-fill me-2" />
                此 CAPA 已於 {closeDate ?? '—'} 結案。
            </Alert>
        );
    }

    return (
        <div>
            {closeGateLoading ? (
                <div className="text-center py-3"><Spinner size="sm" animation="border" /> 檢查結案條件…</div>
            ) : (
                <>
                    {!closeGateData?.d6_passed && (
                        <Alert variant="warning" className="py-2 small">
                            <i className="bi bi-exclamation-triangle-fill me-2" />
                            D6 尚未勾選「驗證通過」，無法結案。
                        </Alert>
                    )}
                    {blockCount > 0 && (
                        <Alert variant="danger" className="py-2 small">
                            <i className="bi bi-x-circle-fill me-2" />
                            尚有 {blockCount} 個 D7 任務未完成或豁免，無法結案。
                        </Alert>
                    )}
                    {canClose && (
                        <Alert variant="success" className="py-2 small">
                            <i className="bi bi-check-circle-fill me-2" />
                            所有結案條件已滿足，可以結案。
                        </Alert>
                    )}
                </>
            )}

            <Form.Group className="mb-3">
                <Form.Label className="fw-semibold">結案確認聲明 <span className="text-danger">*</span></Form.Label>
                <Form.Control
                    as="textarea" rows={4}
                    value={confirmation}
                    onChange={e => setConfirmation(e.target.value)}
                    placeholder="請確認所有改善措施均已實施且有效…"
                />
            </Form.Group>

            <Form.Group className="mb-3">
                <Form.Label className="fw-semibold">團隊表揚與心得</Form.Label>
                <Form.Control
                    as="textarea" rows={3}
                    value={recognition}
                    onChange={e => setRecognition(e.target.value)}
                    placeholder="選填：紀錄團隊貢獻與心得…"
                />
            </Form.Group>

            <div className="d-flex justify-content-end">
                <Button
                    variant={canClose ? 'danger' : 'secondary'}
                    disabled={!canClose || !confirmation.trim() || closing}
                    onClick={onClose}
                >
                    {closing
                        ? <><Spinner size="sm" animation="border" className="me-1" />結案中…</>
                        : <><i className="bi bi-lock-fill me-1" />確認結案（不可逆）</>
                    }
                </Button>
            </div>
        </div>
    );
};

export default CAPAModal;
