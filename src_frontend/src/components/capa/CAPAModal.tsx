import {
    Modal, Button, Nav, Tab, Alert,
    Badge, ProgressBar, Spinner,
} from 'react-bootstrap';
import toast from 'react-hot-toast';
import {
    useCapaDetail,
    useUpdateCapaStep,
    useCapaCloseGate,
    useCloseCapa,
    download8DReport,
    CAPA_SEVERITY_VARIANT,
    D_STEP_LABELS,
} from '../../hooks/useCapa';
import { useInspectors } from '../../hooks/useInspectors';
import D0Pane from './D0Pane';
import D1Pane from './D1Pane';
import D2Pane from './D2Pane';
import D3Pane from './D3Pane';
import D4Pane from './D4Pane';
import D5Pane from './D5Pane';
import D6Pane from './D6Pane';
import D7Pane from './D7Pane';
import D8Pane from './D8Pane';
import SourceInfoBanner from './SourceInfoBanner';
import { useCapaDraft } from './useCapaDraft';

// ── 介面 Props ────────────────────────────────────────────────
interface CAPAModalProps {
    show: boolean;
    capaId: number | null;
    onHide: () => void;
}

// ══════════════════════════════════════════════════════════════
// 主元件：CAPAModal
// ══════════════════════════════════════════════════════════════
const CAPAModal = ({ show, capaId, onHide }: CAPAModalProps) => {
    const { data: capa, isLoading } = useCapaDetail(capaId);
    const { data: inspectors = [] }  = useInspectors({ enabled: show });
    const updateStep  = useUpdateCapaStep();
    const closeGate   = useCapaCloseGate(capaId);
    const closeMut    = useCloseCapa();

    // 唯讀模式（已結案）
    const isClosed = capa?.status === '已結案';

    const draft = useCapaDraft({
        capa,
        capaId,
        isClosed,
        onUpdateStep: (id, data) => updateStep.mutate({ id, data }),
        onCloseCapa: data => closeMut.mutate(data),
    });
    const {
        activeTab, setActiveTab, steps, stepDone, handleSeverityChange,
        d0Symptom, setD0Symptom, d0Criteria, setD0Criteria, d0Severity, d0Rigor, setD0Rigor, d0Deadline, setD0Deadline,
        d1Champion, setD1Champion, d1Leader, setD1Leader, d1Members, setD1Members,
        d2What, setD2What, d2Where, setD2Where, d2When, setD2When, d2Who, setD2Who, d2Why, setD2Why, d2How, setD2How, d2HowMany, setD2HowMany,
        d3Action, setD3Action, d3EffDate, setD3EffDate, d3Verif, setD3Verif,
        d4Tool, setD4Tool, d4FiveWhy, setD4FiveWhy, d4Fishbone, setD4Fishbone, d4RootCause, setD4RootCause,
        d5Action, setD5Action, d5PlannedDate, setD5PlannedDate, d5VerifyPlan, setD5VerifyPlan,
        d6ImplDate, setD6ImplDate, d6Result, setD6Result, d6Verified, setD6Verified,
        d7Actions, toggleD7, updateD7Field,
        d8Confirm, setD8Confirm, d8Recog, setD8Recog, handleClose8D,
        saveD0, saveD1, saveD2, saveD3, saveD4, saveD5, saveD6, saveD7,
    } = draft;

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
                                        onSave={saveD0}
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
                                        onSave={saveD1}
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
                                        onSave={saveD2}
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
                                        onSave={saveD3}
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
                                        onSave={saveD4}
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
                                        onSave={saveD5}
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
                                        onSave={saveD6}
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
                                        onSave={saveD7}
                                        saving={updateStep.isPending}
                                    />
                                </Tab.Pane>

                                {/* ── D8 結案確認 ──────────────────────────── */}
                                <Tab.Pane eventKey="d8">
                                    <D8Pane
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

export default CAPAModal;
