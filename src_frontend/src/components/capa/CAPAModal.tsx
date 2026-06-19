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
import { groupInspectors, inspectorLabel, type InspectorItem } from './capaInspectors';
import D0Pane from './D0Pane';
import D1Pane from './D1Pane';
import D2Pane from './D2Pane';
import D3Pane from './D3Pane';
import D4Pane from './D4Pane';
import D5Pane from './D5Pane';
import D6Pane from './D6Pane';
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

// ── Hook：取得檢驗員清單 ──────────────────────────────────────
const useInspectors = () =>
    useQuery({
        queryKey: ['inspectors'],
        queryFn: async () => {
            const res = await api.get('/inspectors');
            return res.data as InspectorItem[];
        },
        staleTime: 10 * 60 * 1000,
    });

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
        let cancelled = false;
        queueMicrotask(() => {
            if (cancelled) return;
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
        });
        return () => { cancelled = true; };
    }, [capa]);

    // 嚴重度聯動嚴格度（可手動 override）
    // 注意：僅在使用者「手動變更」嚴重度時套用預設嚴格度，
    // 絕不可放在 useEffect 內依賴 d0Severity，否則載入既有資料時
    // 嚴重度從空值帶入會誤觸發，把使用者存好的 rigor（如 簡化5D）覆蓋掉，
    // 造成「處理叫出資料時 5D 時有時無變成 8D」的問題。
    const handleSeverityChange = (val: CAPASeverity | '') => {
        setD0Severity(val);
        if (val && !isClosed) setD0Rigor(SEVERITY_TO_RIGOR[val] ?? '完整8D');
    };

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
                                        severity={d0Severity} setSeverity={handleSeverityChange}
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
// 子元件：D7 橫向展開
// ══════════════════════════════════════════════════════════════
interface D7Props {
    actions: D7Action[];
    tasks: import('../../types').ActionTask[];
    inspectors: InspectorItem[];
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
                                        {Object.entries(groupInspectors(inspectors)).map(([grp, items]) => (
                                            <optgroup key={grp} label={grp}>
                                                {items.map(i => <option key={i.id} value={i.id}>{inspectorLabel(i)}</option>)}
                                            </optgroup>
                                        ))}
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
    closeGateData?: { can_close: boolean; d6_passed: boolean; blocking_tasks: unknown[]; missing_steps?: string[] } | null;
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
                    {(closeGateData?.missing_steps?.length ?? 0) > 0 && (
                        <Alert variant="warning" className="py-2 small">
                            <i className="bi bi-exclamation-triangle-fill me-2" />
                            以下步驟尚未完成，無法結案：{closeGateData!.missing_steps!.join('、')}
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
