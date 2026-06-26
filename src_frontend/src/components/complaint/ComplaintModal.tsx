import { useState, useEffect } from 'react';
import {
    Modal, Button, Alert, Badge
} from 'react-bootstrap';
import {
    useCreateComplaint,
    useUpdateComplaint,
    COMPLAINT_TYPE_LABELS,
} from '../../hooks/useComplaint';
import type { CustomerComplaint, ComplaintType } from '../../types';
import { buildComplaintPayload, getDefaultReplyDeadlines } from './complaintFormUtils';
import { formatLocalDate } from '../../utils/dateUtils';
import {
    ComplaintBasicSection,
    ComplaintDeadlineSection,
    ComplaintResponseSection,
    ComplaintWarrantySection,
} from './ComplaintSections';

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
const ComplaintModal = ({ show, onHide, editData, onSuccess }: ComplaintModalProps) => {
    const createMutation = useCreateComplaint();
    const updateMutation = useUpdateComplaint();

    const isEdit = !!editData;

    // 表單狀態
    const [customer,               setCustomer]               = useState('');
    const [complaintDate,          setComplaintDate]          = useState(formatLocalDate());
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
            let cancelled = false;
            queueMicrotask(() => {
                if (cancelled) return;
                const deadlines = getDefaultReplyDeadlines(complaintDate, complaintType);
                setInitialReplyDeadline(deadlines.initialReplyDeadline);
                setFinalReplyDeadline(deadlines.finalReplyDeadline);
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
                setComplaintDate(formatLocalDate());
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

    const handleSubmit = async () => {
        const payload = buildComplaintPayload({
            isEdit,
            customer,
            complaintDate,
            material,
            spec,
            extrusionNos,
            description,
            severity,
            defectCategory,
            complaintType,
            deviceSerial,
            usageEnv,
            failureHours,
            initialReplyDeadline,
            finalReplyDeadline,
            status,
            initialReply,
            finalReply,
        });
        if (isEdit && editData) {
            await updateMutation.mutateAsync({ id: editData.id, data: payload });
        } else {
            await createMutation.mutateAsync(payload);
        }
        onSuccess?.();
        onHide();
    };

    const isPending = createMutation.isPending || updateMutation.isPending;
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

                <ComplaintBasicSection
                    customer={customer}
                    complaintDate={complaintDate}
                    complaintType={complaintType}
                    material={material}
                    spec={spec}
                    extrusionInput={extrusionInput}
                    extrusionNos={extrusionNos}
                    severity={severity}
                    defectCategory={defectCategory}
                    description={description}
                    complaintTypeLabels={COMPLAINT_TYPE_LABELS}
                    severityOptions={SEVERITY_OPTIONS}
                    defectCategoryOptions={DEFECT_CATEGORY_OPTIONS}
                    onCustomerChange={setCustomer}
                    onComplaintDateChange={setComplaintDate}
                    onComplaintTypeChange={setComplaintType}
                    onMaterialChange={setMaterial}
                    onSpecChange={setSpec}
                    onExtrusionInputChange={setExtrusionInput}
                    onAddExtrusionNo={addExtrusionNo}
                    onRemoveExtrusionNo={removeExtrusionNo}
                    onSeverityChange={setSeverity}
                    onDefectCategoryChange={setDefectCategory}
                    onDescriptionChange={setDescription}
                />

                {/* ─ Warranty / Field Failure 額外欄位 ─ */}
                <ComplaintWarrantySection
                    complaintType={complaintType}
                    deviceSerial={deviceSerial}
                    usageEnv={usageEnv}
                    failureHours={failureHours}
                    onDeviceSerialChange={setDeviceSerial}
                    onUsageEnvChange={setUsageEnv}
                    onFailureHoursChange={setFailureHours}
                />

                <ComplaintDeadlineSection
                    initialReplyDeadline={initialReplyDeadline}
                    finalReplyDeadline={finalReplyDeadline}
                    onInitialReplyDeadlineChange={setInitialReplyDeadline}
                    onFinalReplyDeadlineChange={setFinalReplyDeadline}
                />

                {/* ─ 處理回覆（僅編輯模式）─ */}
                {isEdit && (
                    <ComplaintResponseSection
                        status={status}
                        initialReply={initialReply}
                        finalReply={finalReply}
                        onStatusChange={setStatus}
                        onInitialReplyChange={setInitialReply}
                        onFinalReplyChange={setFinalReply}
                    />
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
