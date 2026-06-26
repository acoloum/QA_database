
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Modal, Button, Form, Row, Col, Alert } from 'react-bootstrap';
import toast from 'react-hot-toast';
import {
    usePatrolOptions,
    usePatrolDetail,
    useCreatePatrol,
    useUpdatePatrol
} from '../../hooks/usePatrol';
import { useExtrusionToleranceCheck } from '../../hooks/useExtrusionTolerance';
import { parseSpec } from '../../utils/parseSpec';
import {
    buildPatrolPayload,
    buildPatrolUpdatePayload,
    getValidPatrolDetails,
    type PatrolDetailInput,
} from './patrolFormUtils';
import { formatLocalDate } from '../../utils/dateUtils';
import { ToleranceBadgeList } from '../common/toleranceDisplay';
import PatrolMeasurementTable from './PatrolMeasurementTable';

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
    }, []);

    // Populate form when detailData loads or when modal opens
    useEffect(() => {
        let cancelled = false;

        if (show) {
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

                                    <PatrolMeasurementTable
                                        groupCount={groupCount}
                                        showInner={showInner}
                                        details={details}
                                        tolerances={tolerances}
                                        specStdValues={specStdValues}
                                        onDetailChange={handleDetailChange}
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
    );
};

export default PatrolModal;
