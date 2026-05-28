import { useState, useEffect } from 'react';
import {
    Modal, Button, Form, Row, Col, Alert, Badge
} from 'react-bootstrap';
import {
    useCreateComplaint,
    useUpdateComplaint,
    COMPLAINT_TYPE_LABELS,
} from '../../hooks/useComplaint';
import type { CustomerComplaint, ComplaintType } from '../../types';

interface ComplaintModalProps {
    show: boolean;
    onHide: () => void;
    editData?: CustomerComplaint | null;
    onSuccess?: () => void;
}

const SEVERITY_OPTIONS = ['Critical', 'Major', 'Minor'];
const DEFECT_CATEGORY_OPTIONS = [
    '外觀不良',
    '尺寸不良',
    '材質/機械性質不良',
    '加工性不良',
    '包裝不良',
    '混料/錯料',
    '數量不符',
    '其他',
];
const DEFAULT_REPLY_DAYS: Record<ComplaintType, number> = {
    quality:       14,
    warranty:      30,
    field_failure: 30,
};

const addDays = (base: string, days: number) => {
    const d = new Date(base);
    d.setDate(d.getDate() + days);
    return d.toISOString().split('T')[0];
};

const ComplaintModal = ({ show, onHide, editData, onSuccess }: ComplaintModalProps) => {
    const createMutation = useCreateComplaint();
    const updateMutation = useUpdateComplaint();

    const isEdit = !!editData;

    // 表單狀態
    const [customer,               setCustomer]               = useState('');
    const [complaintDate,          setComplaintDate]          = useState(new Date().toISOString().split('T')[0]);
    const [material,               setMaterial]               = useState('');
    const [spec,                   setSpec]                   = useState('');
    const [extrusionNos,           setExtrusionNos]           = useState<string[]>([]);
    const [extrusionInput,         setExtrusionInput]         = useState('');
    const [description,            setDescription]            = useState('');
    const [severity,               setSeverity]               = useState('Major');
    const [defectCategory,         setDefectCategory]         = useState('');
    const [complaintType,          setComplaintType]          = useState<ComplaintType>('quality');
    // Warranty / Field Failure
    const [deviceSerial,           setDeviceSerial]           = useState('');
    const [usageEnv,               setUsageEnv]               = useState('');
    const [failureHours,           setFailureHours]           = useState('');
    // 應答期限
    const [initialReplyDeadline,   setInitialReplyDeadline]   = useState('');
    const [finalReplyDeadline,     setFinalReplyDeadline]     = useState('');
    // 更新用
    const [status,                 setStatus]                 = useState('待處理');
    const [initialReply,           setInitialReply]           = useState('');
    const [finalReply,             setFinalReply]             = useState('');
    // 重複客訴警示
    const [repeatWarning,          setRepeatWarning]          = useState(false);

    // 自動帶入期限
    useEffect(() => {
        if (!isEdit && complaintDate && complaintType) {
            const days = DEFAULT_REPLY_DAYS[complaintType];
            let cancelled = false;
            queueMicrotask(() => {
                if (cancelled) return;
                setInitialReplyDeadline(addDays(complaintDate, 3));
                setFinalReplyDeadline(addDays(complaintDate, days));
            });
            return () => { cancelled = true; };
        }
    }, [complaintDate, complaintType, isEdit]);

    // 填入編輯資料
    useEffect(() => {
        let cancelled = false;
        const applyFormState = () => {
            if (cancelled) return;

            if (editData) {
                setCustomer(editData.customer ?? '');
                setComplaintDate(editData.complaint_date ?? '');
                setMaterial(editData.material ?? '');
                setSpec(editData.spec ?? '');
                setExtrusionNos(editData.extrusion_nos ?? []);
                setDescription(editData.description ?? '');
                setSeverity(editData.severity ?? 'Major');
                setDefectCategory(editData.defect_category ?? '');
                setComplaintType(editData.complaint_type ?? 'quality');
                setDeviceSerial(editData.device_serial ?? '');
                setUsageEnv(editData.usage_env ?? '');
                setFailureHours(editData.failure_hours != null ? String(editData.failure_hours) : '');
                setInitialReplyDeadline(editData.initial_reply_deadline ?? '');
                setFinalReplyDeadline(editData.final_reply_deadline ?? '');
                setStatus(editData.status ?? '待處理');
                setInitialReply(editData.initial_reply ?? '');
                setFinalReply(editData.final_reply ?? '');
                setRepeatWarning(editData.is_repeat);
            } else {
                setCustomer('');
                setComplaintDate(new Date().toISOString().split('T')[0]);
                setMaterial('');
                setSpec('');
                setExtrusionNos([]);
                setExtrusionInput('');
                setDescription('');
                setSeverity('Major');
                setDefectCategory('');
                setComplaintType('quality');
                setDeviceSerial('');
                setUsageEnv('');
                setFailureHours('');
                setInitialReplyDeadline('');
                setFinalReplyDeadline('');
                setStatus('待處理');
                setInitialReply('');
                setFinalReply('');
                setRepeatWarning(false);
            }
        };

        queueMicrotask(applyFormState);
        return () => { cancelled = true; };
    }, [editData, show]);

    const addExtrusionNo = () => {
        const val = extrusionInput.trim();
        if (val && !extrusionNos.includes(val)) {
            setExtrusionNos(prev => [...prev, val]);
        }
        setExtrusionInput('');
    };

    const removeExtrusionNo = (no: string) => {
        setExtrusionNos(prev => prev.filter(n => n !== no));
    };

    const buildPayload = () => ({
        customer:                customer.trim(),
        complaint_date:          complaintDate,
        material:                material.trim() || undefined,
        spec:                    spec.trim() || undefined,
        extrusion_nos:           extrusionNos,
        description:             description.trim(),
        severity:                severity || undefined,
        defect_category:         defectCategory || undefined,
        complaint_type:          complaintType,
        device_serial:           deviceSerial.trim() || undefined,
        usage_env:               usageEnv.trim() || undefined,
        failure_hours:           failureHours ? Number(failureHours) : undefined,
        initial_reply_deadline:  initialReplyDeadline || undefined,
        final_reply_deadline:    finalReplyDeadline || undefined,
        status:                  isEdit ? (status as import('../../types').ComplaintStatus) : undefined,
        initial_reply:           isEdit ? (initialReply.trim() || undefined) : undefined,
        final_reply:             isEdit ? (finalReply.trim() || undefined) : undefined,
    });

    const handleSubmit = async () => {
        const payload = buildPayload();
        if (isEdit && editData) {
            await updateMutation.mutateAsync({ id: editData.id, data: payload });
        } else {
            await createMutation.mutateAsync(payload);
        }
        onSuccess?.();
        onHide();
    };

    const isPending = createMutation.isPending || updateMutation.isPending;
    const isWarrantyType = complaintType === 'warranty' || complaintType === 'field_failure';

    return (
        <Modal show={show} onHide={onHide} size="xl">
            <Modal.Header closeButton>
                <Modal.Title>{isEdit ? '編輯客訴' : '新增客訴'}</Modal.Title>
            </Modal.Header>

            <Modal.Body>
                {/* 重複客訴警示 */}
                {repeatWarning && isEdit && (
                    <Alert variant="warning" className="py-2 mb-3">
                        <i className="bi bi-exclamation-triangle-fill me-2" />
                        <strong>重複客訴警示：</strong>
                        此為 12 個月內相同客戶 + 材質 + 規格 + 不良類別的重複客訴。
                        {(editData?.repeat_refs?.length ?? 0) > 0 && (
                            <span className="ms-1">
                                關聯單號：
                                {editData?.repeat_refs.map(r => (
                                    <Badge bg="warning" text="dark" key={r} className="me-1">{r}</Badge>
                                ))}
                            </span>
                        )}
                    </Alert>
                )}

                {/* ─ 基本資訊 ─ */}
                <h6 className="text-muted mb-3">基本資訊</h6>
                <Row className="g-3 mb-3">
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>客戶 <span className="text-danger">*</span></Form.Label>
                            <Form.Control
                                value={customer}
                                onChange={e => setCustomer(e.target.value)}
                                placeholder="客戶名稱"
                            />
                        </Form.Group>
                    </Col>
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>客訴日期 <span className="text-danger">*</span></Form.Label>
                            <Form.Control
                                type="date"
                                value={complaintDate}
                                onChange={e => setComplaintDate(e.target.value)}
                            />
                        </Form.Group>
                    </Col>
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>客訴類型</Form.Label>
                            <Form.Select
                                value={complaintType}
                                onChange={e => setComplaintType(e.target.value as ComplaintType)}
                            >
                                {Object.entries(COMPLAINT_TYPE_LABELS).map(([k, v]) => (
                                    <option key={k} value={k}>{v}</option>
                                ))}
                            </Form.Select>
                        </Form.Group>
                    </Col>
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>材質</Form.Label>
                            <Form.Control
                                value={material}
                                onChange={e => setMaterial(e.target.value)}
                                placeholder="如：6061、6063…"
                            />
                        </Form.Group>
                    </Col>
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>規格</Form.Label>
                            <Form.Control
                                value={spec}
                                onChange={e => setSpec(e.target.value)}
                                placeholder="如：T5、T6…"
                            />
                        </Form.Group>
                    </Col>
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>擠製編號</Form.Label>
                            <div className="d-flex gap-1">
                                <Form.Control
                                    value={extrusionInput}
                                    onChange={e => setExtrusionInput(e.target.value)}
                                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addExtrusionNo(); } }}
                                    placeholder="輸入後按 Enter 或 +"
                                />
                                <Button variant="outline-secondary" onClick={addExtrusionNo}>+</Button>
                            </div>
                            {extrusionNos.length > 0 && (
                                <div className="mt-1 d-flex flex-wrap gap-1">
                                    {extrusionNos.map(no => (
                                        <Badge key={no} bg="secondary" className="d-flex align-items-center gap-1" style={{ fontSize: '0.8rem' }}>
                                            {no}
                                            <span
                                                style={{ cursor: 'pointer', lineHeight: 1 }}
                                                onClick={() => removeExtrusionNo(no)}
                                            >×</span>
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </Form.Group>
                    </Col>
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>嚴重度</Form.Label>
                            <Form.Select value={severity} onChange={e => setSeverity(e.target.value)}>
                                {SEVERITY_OPTIONS.map(s => (
                                    <option key={s} value={s}>{s}</option>
                                ))}
                            </Form.Select>
                        </Form.Group>
                    </Col>
                    <Col md={4}>
                        <Form.Group>
                            <Form.Label>不良類別</Form.Label>
                            <Form.Select value={defectCategory} onChange={e => setDefectCategory(e.target.value)}>
                                <option value="">— 請選擇 —</option>
                                {DEFECT_CATEGORY_OPTIONS.map(opt => (
                                    <option key={opt} value={opt}>{opt}</option>
                                ))}
                            </Form.Select>
                        </Form.Group>
                    </Col>
                    <Col md={12}>
                        <Form.Group>
                            <Form.Label>問題描述 <span className="text-danger">*</span></Form.Label>
                            <Form.Control
                                as="textarea"
                                rows={3}
                                value={description}
                                onChange={e => setDescription(e.target.value)}
                                placeholder="詳述客訴問題內容"
                            />
                        </Form.Group>
                    </Col>
                </Row>

                {/* ─ Warranty / Field Failure 額外欄位 ─ */}
                {isWarrantyType && (
                    <>
                        <h6 className="text-muted mb-3">
                            {complaintType === 'warranty' ? 'Warranty 申請資訊' : 'Field Failure 資訊'}
                        </h6>
                        <Row className="g-3 mb-3">
                            <Col md={4}>
                                <Form.Group>
                                    <Form.Label>裝置序號</Form.Label>
                                    <Form.Control
                                        value={deviceSerial}
                                        onChange={e => setDeviceSerial(e.target.value)}
                                    />
                                </Form.Group>
                            </Col>
                            <Col md={4}>
                                <Form.Group>
                                    <Form.Label>使用環境</Form.Label>
                                    <Form.Control
                                        value={usageEnv}
                                        onChange={e => setUsageEnv(e.target.value)}
                                    />
                                </Form.Group>
                            </Col>
                            <Col md={4}>
                                <Form.Group>
                                    <Form.Label>故障時數（hr）</Form.Label>
                                    <Form.Control
                                        type="number"
                                        min="0"
                                        value={failureHours}
                                        onChange={e => setFailureHours(e.target.value)}
                                    />
                                </Form.Group>
                            </Col>
                        </Row>
                    </>
                )}

                {/* ─ 應答時效 ─ */}
                <h6 className="text-muted mb-3">應答時效</h6>
                <Row className="g-3 mb-3">
                    <Col md={6}>
                        <Form.Group>
                            <Form.Label>初步回覆期限</Form.Label>
                            <Form.Control
                                type="date"
                                value={initialReplyDeadline}
                                onChange={e => setInitialReplyDeadline(e.target.value)}
                            />
                        </Form.Group>
                    </Col>
                    <Col md={6}>
                        <Form.Group>
                            <Form.Label>最終回覆期限</Form.Label>
                            <Form.Control
                                type="date"
                                value={finalReplyDeadline}
                                onChange={e => setFinalReplyDeadline(e.target.value)}
                            />
                        </Form.Group>
                    </Col>
                </Row>

                {/* ─ 處理回覆（僅編輯模式）─ */}
                {isEdit && (
                    <>
                        <h6 className="text-muted mb-3">處理回覆</h6>
                        <Row className="g-3 mb-3">
                            <Col md={4}>
                                <Form.Group>
                                    <Form.Label>狀態</Form.Label>
                                    <Form.Select value={status} onChange={e => setStatus(e.target.value)}>
                                        {['待處理', '處理中', '已結案'].map(s => (
                                            <option key={s} value={s}>{s}</option>
                                        ))}
                                    </Form.Select>
                                </Form.Group>
                            </Col>
                            <Col md={12}>
                                <Form.Group>
                                    <Form.Label>初步回覆內容</Form.Label>
                                    <Form.Control
                                        as="textarea"
                                        rows={2}
                                        value={initialReply}
                                        onChange={e => setInitialReply(e.target.value)}
                                    />
                                </Form.Group>
                            </Col>
                            <Col md={12}>
                                <Form.Group>
                                    <Form.Label>最終回覆內容</Form.Label>
                                    <Form.Control
                                        as="textarea"
                                        rows={2}
                                        value={finalReply}
                                        onChange={e => setFinalReply(e.target.value)}
                                    />
                                </Form.Group>
                            </Col>
                        </Row>
                    </>
                )}
            </Modal.Body>

            <Modal.Footer>
                <Button variant="secondary" onClick={onHide}>取消</Button>
                <Button
                    variant="primary"
                    onClick={handleSubmit}
                    disabled={isPending || !customer || !description}
                >
                    {isPending ? '儲存中…' : (isEdit ? '儲存更改' : '新增客訴')}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ComplaintModal;
