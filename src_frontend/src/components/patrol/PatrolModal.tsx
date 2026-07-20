
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Modal, Button, Form, Row, Col, Alert } from 'react-bootstrap';
import toast from 'react-hot-toast';
import {
    usePatrolOptions,
    usePatrolDetail,
    useCreatePatrol,
    useUpdatePatrol,
    usePatrolLiveLimits,
    type PatrolLiveLimits,
} from '../../hooks/usePatrol';
import { useExtrusionToleranceCheck } from '../../hooks/useExtrusionTolerance';
import { useAnalyzeSpcStudy, useSaveSpcOcap, useSpcAssignees } from '../../hooks/useSpcStudies';
import { parseSpec } from '../../utils/parseSpec';
import {
    buildPatrolPayload,
    buildPatrolUpdatePayload,
    buildLiveGroupSeries,
    evaluatePatrolLiveStability,
    getValidPatrolDetails,
    type PatrolDetailInput,
    type PatrolLiveViolation,
} from './patrolFormUtils';
import { formatLocalDate } from '../../utils/dateUtils';
import { ToleranceBadgeList } from '../common/toleranceDisplay';
import PatrolMeasurementTable from './PatrolMeasurementTable';
import SpcOcapOffcanvas from '../spc/SpcOcapOffcanvas';
import type { SpcEventSummary } from '../../types/spc';

interface PatrolModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

const PatrolModal = ({ show, handleClose, onSuccess, editId }: PatrolModalProps) => {
    // Hooks
    const { data: optionsData } = usePatrolOptions();
    const machines = optionsData?.machines || [];
    const operators = optionsData?.operators || [];
    const inspectors = optionsData?.inspectors || [];
    const customers = optionsData?.customers || [];

    const { data: detailData, isLoading: isLoadingDetail } = usePatrolDetail(editId);

    const createMutation = useCreatePatrol();
    const updateMutation = useUpdatePatrol();
    const analyzeOngoing = useAnalyzeSpcStudy();
    const saveOcap = useSaveSpcOcap();
    const [openEvents, setOpenEvents] = useState<SpcEventSummary[]>([]);
    const [selectedEvent, setSelectedEvent] = useState<SpcEventSummary | null>(null);
    const assignees = useSpcAssignees(Boolean(selectedEvent));

    const handleSelectEvent = (event: SpcEventSummary) => {
        saveOcap.reset();
        setSelectedEvent(event);
    };

    const handleOcapHide = () => {
        if (saveOcap.isPending) return;
        saveOcap.reset();
        setSelectedEvent(null);
    };

    // Form State
    const [date, setDate] = useState(formatLocalDate());
    const [machine, setMachine] = useState('');
    const [operator, setOperator] = useState('');
    const [inspector, setInspector] = useState('');
    const [customer, setCustomer] = useState('');
    const [material, setMaterial] = useState('');
    const [batch, setBatch] = useState('');
    const [spec, setSpec] = useState('');

    // Details State
    const [groupCount, setGroupCount] = useState(1);
    const [details, setDetails] = useState<PatrolDetailInput[]>([]);
    const [showInner, setShowInner] = useState(false);

    // 即時模式 State
    const [liveMode, setLiveMode] = useState(false);
    const [liveLimitsCache, setLiveLimitsCache] = useState<Record<string, PatrolLiveLimits>>({});
    const [liveTouchedKey, setLiveTouchedKey] = useState<string | null>(null);

    // 切換機台/材質/規格/客戶時清空即時界限快取並重新抓取，
    // 避免沿用已快取但已不對應目前製程流（process_stream_key）的判定結果，
    // 造成該 item/position 組合在表單剩餘時間內永遠不再查詢的靜默失效
    useEffect(() => {
        setLiveLimitsCache({});
        setLiveTouchedKey(null);
    }, [machine, material, spec, customer]);

    const resetForm = useCallback(() => {
        setDate(formatLocalDate());
        setMachine('');
        setOperator('');
        setInspector('');
        setCustomer('');
        setMaterial('');
        setBatch('');
        setSpec('');
        setGroupCount(1);
        setDetails([]);
        setShowInner(false);
        setLiveMode(false);
        setLiveLimitsCache({});
        setLiveTouchedKey(null);
        setOpenEvents([]);
        setSelectedEvent(null);
    }, []);

    // Populate form when detailData loads or when modal opens
    useEffect(() => {
        let cancelled = false;

        if (show) {
            setOpenEvents([]);
            setSelectedEvent(null);
            if (editId && detailData) {
                const d = detailData;
                queueMicrotask(() => {
                    if (cancelled) return;
                    setDate(d.main.檢驗日期);
                    setMachine(d.main.機台);
                    setOperator(d.main.主機手);
                    setInspector(d.main.檢驗人員);
                    setCustomer(d.main.客戶名稱);
                    setMaterial(d.main.材質);
                    setBatch(d.main.原料批號);
                    setSpec(d.main.擠壓規格);

                    // Parse details to state
                    const newDetails: PatrolDetailInput[] = d.details.map((item: Record<string, unknown>) => ({
                        group: item.group,
                        item: item.item,
                        pos: item.pos,
                        min: item.min?.toString() || '',
                        max: item.max?.toString() || ''
                    }));
                    setDetails(newDetails);

                    // Determine group count
                    const groups = new Set(newDetails.map(d => d.group));
                    setGroupCount(groups.size || 1);
                });
            } else if (!editId) {
                queueMicrotask(() => {
                    if (!cancelled) resetForm();
                });
            }
        }
        return () => {
            cancelled = true;
        };
    }, [show, editId, detailData, resetForm]);

    const handleDetailChange = (group: string, pos: string, item: string, type: 'min' | 'max', value: string) => {
        setDetails(prev => {
            const existingIndex = prev.findIndex(d => d.group === group && d.pos === pos && d.item === item);
            if (existingIndex >= 0) {
                const newDetails = [...prev];
                newDetails[existingIndex] = { ...newDetails[existingIndex], [type]: value };
                return newDetails;
            } else {
                return [...prev, {
                    group, item, pos, min: type === 'min' ? value : '', max: type === 'max' ? value : ''
                }];
            }
        });
    };

    const handleDetailBlur = (pos: string, item: string) => {
        if (!liveMode) return;
        setLiveTouchedKey(`${pos}|${item}`);
    };

    const liveLimitsKey = liveTouchedKey ? liveTouchedKey.split('|') as [string, string] : null;
    const [liveLimitsPos, liveLimitsItem] = liveLimitsKey ?? ['', ''];
    const liveLimitsQuery = usePatrolLiveLimits(
        {
            m_id: machine, op_id: operator, cust_id: customer,
            mat: material, spec, item: liveLimitsItem, pos: liveLimitsPos,
            exclude_main_id: editId ?? undefined,
        },
        liveMode && !!liveTouchedKey && !(liveTouchedKey in liveLimitsCache),
    );

    useEffect(() => {
        if (liveTouchedKey && liveLimitsQuery.data && !(liveTouchedKey in liveLimitsCache)) {
            setLiveLimitsCache(prev => ({ ...prev, [liveTouchedKey]: liveLimitsQuery.data! }));
        }
    }, [liveTouchedKey, liveLimitsQuery.data, liveLimitsCache]);

    const liveViolations = useMemo(() => {
        if (!liveMode) return {};
        const violations: Record<string, PatrolLiveViolation> = {};
        for (const pos of ['前段', '中段', '後段']) {
            for (const item of ['外徑', '內徑', '厚度']) {
                const cached = liveLimitsCache[`${pos}|${item}`];
                if (!cached?.found) continue;
                for (let g = 1; g <= groupCount; g += 1) {
                    const group = `第${g}組`;
                    const { means, ranges } = buildLiveGroupSeries({
                        recentValues: cached.recent_values ?? [],
                        details, pos, item, groupCount: g,
                    });
                    if (means.length === 0) continue;
                    const violation = evaluatePatrolLiveStability({
                        means, ranges,
                        xCl: cached.x_cl!, xUcl: cached.x_ucl!, xLcl: cached.x_lcl!,
                        rCl: cached.r_cl!, rUcl: cached.r_ucl!, rLcl: cached.r_lcl!,
                    });
                    if (violation) {
                        violations[`${pos}|${item}|${group}`] = violation;
                    }
                }
            }
        }
        return violations;
    }, [liveMode, liveLimitsCache, details, groupCount]);

    const triggerOngoingAnalysisForTouchedStreams = async () => {
        const touchedStreams = new Set(
            Object.keys(liveViolations).map(key => key.split('|').slice(0, 2).join('|')),
        );
        const newEvents: SpcEventSummary[] = [];
        let failureCount = 0;
        for (const streamKey of touchedStreams) {
            const [pos, item] = streamKey.split('|');
            try {
                const result = await analyzeOngoing.mutateAsync({
                    source: 'patrol',
                    filters: { m_id: machine, op_id: operator, cust_id: customer, mat: material, spec, item, pos },
                    study_type: 'ongoing',
                });
                const activeLimit = result.monitoring_limit
                    ?? result.limit_versions?.find(limit => limit.status === 'active');
                for (const event of activeLimit?.events ?? []) {
                    if (event.status === 'open') newEvents.push(event);
                }
            } catch (error) {
                failureCount += 1;
                console.error(`巡檢正式 SPC 判定失敗（${item}/${pos}）`, error);
            }
        }
        if (newEvents.length > 0) {
            setOpenEvents(newEvents);
            toast(`本次觸發 ${newEvents.length} 項製程異常，可查看建議處置`, { icon: '⚠️' });
        } else if (failureCount > 0 && failureCount === touchedStreams.size) {
            toast.error('巡檢已存檔，但即時提示的正式判定執行失敗，請至 SPC 研究頁面確認製程狀態');
        }
    };

    const handleSubmit = async () => {
        // Client-side required field validation
        const missingFields: string[] = [];
        if (!date) missingFields.push('日期');
        if (!machine) missingFields.push('機台');
        if (!operator) missingFields.push('主機手');
        if (!inspector) missingFields.push('檢驗員');

        if (missingFields.length > 0) {
            toast.error(`請填寫以下必填欄位：${missingFields.join('、')}`);
            return;
        }

        const validDetails = getValidPatrolDetails(details);

        if (validDetails.length === 0) {
            toast.error('請至少輸入一組測量數值');
            return;
        }

        const payloadValues = {
            editId,
            date,
            machine,
            operator,
            inspector,
            customer,
            material,
            batch,
            spec,
            details,
        };

        try {
            if (editId) {
                await updateMutation.mutateAsync({ id: editId, data: buildPatrolUpdatePayload({ ...payloadValues, editId }) });
            } else {
                await createMutation.mutateAsync(buildPatrolPayload(payloadValues));
            }
            if (liveMode && Object.keys(liveViolations).length > 0) {
                await triggerOngoingAnalysisForTouchedStreams();
            }
            onSuccess();
            handleClose();
        } catch (error) {
            console.error(error);
        }
    };

    // 取得擠壓公差（有 material 就查，spec 空字串表示通用）
    // 傳入 vendorId（customer）以優先查詢廠商公差
    const { data: toleranceResult } = useExtrusionToleranceCheck(material, spec, customer ? parseInt(customer) : undefined);
    const tolerances = toleranceResult?.found ? (toleranceResult.tolerances ?? []) : [];

    // 從擠壓規格字串解析各量測項目的標準值
    // 例：「85*2.8」→ { 外徑: 85, 厚度: 2.8 }
    const specStdValues = useMemo(() => parseSpec(spec), [spec]);

    const isSaving = createMutation.isPending || updateMutation.isPending;

    return (
        <>
        <Modal show={show} onHide={handleClose} dialogClassName="modal-patrol-wide" backdrop="static">
            <div className="modal-dialog" style={{ maxWidth: '1600px', width: '99%', overflowX: 'auto' }}>
                <div className="modal-content" style={{ overflowX: 'auto' }}>
                    <Modal.Header closeButton>
                        <Modal.Title>{editId ? '編輯巡檢紀錄' : '新增巡檢紀錄'}</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        {editId && isLoadingDetail ? (
                            <div className="text-center py-5">
                                <div className="spinner-border text-primary" role="status">
                                    <span className="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        ) : (
                            <div>
                                <Form>
                                    <Row className="g-3 mb-4">
                                        <Col md={3}><Form.Label>日期</Form.Label><Form.Control type="date" value={date} onChange={e => setDate(e.target.value)} /></Col>
                                        <Col md={3}>
                                            <Form.Label>機台</Form.Label>
                                            <Form.Select value={machine} onChange={e => setMachine(e.target.value)}>
                                                <option value="">請選擇</option>
                                                {machines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={3}>
                                            <Form.Label>主機手</Form.Label>
                                            <Form.Select value={operator} onChange={e => setOperator(e.target.value)}>
                                                <option value="">請選擇</option>
                                                {operators.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={3}>
                                            <Form.Label>檢驗員</Form.Label>
                                            <Form.Select value={inspector} onChange={e => setInspector(e.target.value)}>
                                                <option value="">請選擇</option>
                                                {inspectors.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={4}>
                                            <Form.Label>客戶名稱</Form.Label>
                                            <Form.Select value={customer} onChange={e => setCustomer(e.target.value)} style={{ minWidth: '100%' }}>
                                                <option value="">請選擇</option>
                                                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={4}><Form.Label>材質</Form.Label><Form.Control value={material} onChange={e => setMaterial(e.target.value)} style={{ width: '100%' }} /></Col>
                                        <Col md={4}><Form.Label>原料批號</Form.Label><Form.Control value={batch} onChange={e => setBatch(e.target.value)} style={{ width: '100%' }} /></Col>
                                        <Col md={12}><Form.Label>擠壓規格</Form.Label><Form.Control value={spec} onChange={e => setSpec(e.target.value)} style={{ width: '100%' }} /></Col>
                                    </Row>

                                    {/* 公差標準顯示區塊 */}
                                    {tolerances.length > 0 && (
                                        <Alert variant="info" className="mb-4">
                                            <h6 className="alert-heading">📐 公差標準已載入</h6>
                                            <div className="d-flex flex-wrap gap-3">
                                                <ToleranceBadgeList tolerances={tolerances} />
                                            </div>
                                        </Alert>
                                    )}

                                    <Form.Check
                                        type="switch"
                                        id="patrol-live-mode"
                                        label="即時模式"
                                        checked={liveMode}
                                        onChange={e => setLiveMode(e.target.checked)}
                                        className="mb-2"
                                    />

                                    <PatrolMeasurementTable
                                        groupCount={groupCount}
                                        showInner={showInner}
                                        details={details}
                                        tolerances={tolerances}
                                        specStdValues={specStdValues}
                                        onDetailChange={handleDetailChange}
                                        liveViolations={liveViolations}
                                        onCellBlur={handleDetailBlur}
                                    />

                                    <div className="d-flex gap-2 mt-3">
                                        <Button variant="outline-primary" onClick={() => setGroupCount(c => c + 1)}>
                                            <i className="bi bi-plus-lg"></i> 新增組別
                                        </Button>
                                        <Button variant="outline-danger" onClick={() => setGroupCount(c => Math.max(1, c - 1))}>
                                            <i className="bi bi-dash-lg"></i> 刪除組別
                                        </Button>
                                        <Button variant={showInner ? "info" : "outline-info"} onClick={() => setShowInner(!showInner)}>
                                            <i className={`bi bi-arrows-${showInner ? 'collapse' : 'expand'}`}></i> {showInner ? '隱藏內徑' : '展開內徑'}
                                        </Button>
                                    </div>

                                </Form>
                            </div>
                        )}
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={handleClose}>取消</Button>
                        <Button variant="success" onClick={handleSubmit} disabled={isSaving} type="button">
                            {isSaving ? '儲存中...' : '儲存'}
                        </Button>
                    </Modal.Footer>
                </div>
            </div>
        </Modal>
        {openEvents.length > 0 && (
            <div className="position-fixed bottom-0 end-0 m-3 p-2 bg-white border rounded shadow" style={{ zIndex: 1060 }}>
                <div className="small fw-bold mb-1">本次觸發的製程異常</div>
                {openEvents.map(event => (
                    <Button key={event.id} size="sm" variant="outline-danger" className="d-block mb-1" onClick={() => handleSelectEvent(event)}>
                        事件 #{event.id} · {event.chart_kind === 'location' ? '位置圖' : '變異圖'} · 查看建議
                    </Button>
                ))}
            </div>
        )}
        {selectedEvent && (
            <SpcOcapOffcanvas
                key={selectedEvent.id}
                show
                eventId={selectedEvent.id}
                ocapId={selectedEvent.ocap?.id}
                initialValue={selectedEvent.ocap}
                onHide={handleOcapHide}
                onSave={input => {
                    saveOcap.mutate(input, {
                        onSuccess: () => setSelectedEvent(null),
                    });
                }}
                pending={saveOcap.isPending}
                saveError={saveOcap.isError}
                assignees={assignees.data ?? []}
                assigneesLoading={assignees.isLoading}
                assigneesError={assignees.isError}
            />
        )}
        </>
    );
};

export default PatrolModal;
