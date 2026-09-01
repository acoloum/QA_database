import { Badge, Button, Form, InputGroup, Row, Col } from 'react-bootstrap';

import type { ComplaintType } from '../../types';

interface ComplaintBasicSectionProps {
    customer: string;
    complaintDate: string;
    complaintType: ComplaintType;
    material: string;
    spec: string;
    extrusionInput: string;
    extrusionNos: string[];
    severity: string;
    defectCategory: string;
    description: string;
    complaintTypeLabels: Record<string, string>;
    severityOptions: string[];
    defectCategoryOptions: string[];
    onCustomerChange: (value: string) => void;
    onComplaintDateChange: (value: string) => void;
    onComplaintTypeChange: (value: ComplaintType) => void;
    onMaterialChange: (value: string) => void;
    onSpecChange: (value: string) => void;
    onExtrusionInputChange: (value: string) => void;
    onAddExtrusionNo: () => void;
    onRemoveExtrusionNo: (value: string) => void;
    onSeverityChange: (value: string) => void;
    onDefectCategoryChange: (value: string) => void;
    onDescriptionChange: (value: string) => void;
}

export const ComplaintBasicSection = ({
    customer,
    complaintDate,
    complaintType,
    material,
    spec,
    extrusionInput,
    extrusionNos,
    severity,
    defectCategory,
    description,
    complaintTypeLabels,
    severityOptions,
    defectCategoryOptions,
    onCustomerChange,
    onComplaintDateChange,
    onComplaintTypeChange,
    onMaterialChange,
    onSpecChange,
    onExtrusionInputChange,
    onAddExtrusionNo,
    onRemoveExtrusionNo,
    onSeverityChange,
    onDefectCategoryChange,
    onDescriptionChange,
}: ComplaintBasicSectionProps) => (
    <>
        <h6 className="text-muted mb-3">基本資訊</h6>
        <Row className="g-3 mb-3">
            <Col md={4}>
                <Form.Group>
                    <Form.Label>客戶 <span className="text-danger">*</span></Form.Label>
                    <Form.Control value={customer} onChange={e => onCustomerChange(e.target.value)} placeholder="客戶名稱" />
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group>
                    <Form.Label>客訴日期 <span className="text-danger">*</span></Form.Label>
                    <Form.Control type="date" value={complaintDate} onChange={e => onComplaintDateChange(e.target.value)} />
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group>
                    <Form.Label>客訴類型</Form.Label>
                    <Form.Select value={complaintType} onChange={e => onComplaintTypeChange(e.target.value as ComplaintType)}>
                        {Object.entries(complaintTypeLabels).map(([key, label]) => (
                            <option key={key} value={key}>{label}</option>
                        ))}
                    </Form.Select>
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group>
                    <Form.Label>材質</Form.Label>
                    <Form.Control value={material} onChange={e => onMaterialChange(e.target.value)} placeholder="如：6061、6063…" />
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group>
                    <Form.Label>規格</Form.Label>
                    <Form.Control value={spec} onChange={e => onSpecChange(e.target.value)} placeholder="如：T5、T6…" />
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group>
                    <Form.Label>擠製編號</Form.Label>
                    <InputGroup>
                        <Form.Control
                            value={extrusionInput}
                            onChange={e => onExtrusionInputChange(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); onAddExtrusionNo(); } }}
                            placeholder="輸入後按 Enter 新增"
                        />
                        <Button variant="outline-secondary" onClick={onAddExtrusionNo}>新增</Button>
                    </InputGroup>
                    {extrusionNos.length > 0 && (
                        <div className="mt-1 d-flex flex-wrap gap-1">
                            {extrusionNos.map(no => (
                                <Badge key={no} bg="secondary" className="d-flex align-items-center gap-1" style={{ fontSize: '0.8rem' }}>
                                    {no}
                                    <span
                                        style={{ cursor: 'pointer', lineHeight: 1 }}
                                        onClick={() => onRemoveExtrusionNo(no)}
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
                    <Form.Select value={severity} onChange={e => onSeverityChange(e.target.value)}>
                        {severityOptions.map(option => (
                            <option key={option} value={option}>{option}</option>
                        ))}
                    </Form.Select>
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group>
                    <Form.Label>不良類別</Form.Label>
                    <Form.Select value={defectCategory} onChange={e => onDefectCategoryChange(e.target.value)}>
                        <option value="">— 請選擇 —</option>
                        {defectCategoryOptions.map(option => (
                            <option key={option} value={option}>{option}</option>
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
                        onChange={e => onDescriptionChange(e.target.value)}
                        placeholder="詳述客訴問題內容"
                    />
                </Form.Group>
            </Col>
        </Row>
    </>
);

interface ComplaintDeadlineSectionProps {
    initialReplyDeadline: string;
    finalReplyDeadline: string;
    onInitialReplyDeadlineChange: (value: string) => void;
    onFinalReplyDeadlineChange: (value: string) => void;
}

export const ComplaintDeadlineSection = ({
    initialReplyDeadline,
    finalReplyDeadline,
    onInitialReplyDeadlineChange,
    onFinalReplyDeadlineChange,
}: ComplaintDeadlineSectionProps) => (
    <>
        <h6 className="text-muted mb-3">應答時效</h6>
        <Row className="g-3 mb-3">
            <Col md={6}>
                <Form.Group>
                    <Form.Label>初步回覆期限</Form.Label>
                    <Form.Control
                        type="date"
                        value={initialReplyDeadline}
                        onChange={e => onInitialReplyDeadlineChange(e.target.value)}
                    />
                </Form.Group>
            </Col>
            <Col md={6}>
                <Form.Group>
                    <Form.Label>最終回覆期限</Form.Label>
                    <Form.Control
                        type="date"
                        value={finalReplyDeadline}
                        onChange={e => onFinalReplyDeadlineChange(e.target.value)}
                    />
                </Form.Group>
            </Col>
        </Row>
    </>
);

interface ComplaintWarrantySectionProps {
    complaintType: ComplaintType;
    deviceSerial: string;
    usageEnv: string;
    failureHours: string;
    onDeviceSerialChange: (value: string) => void;
    onUsageEnvChange: (value: string) => void;
    onFailureHoursChange: (value: string) => void;
}

export const ComplaintWarrantySection = ({
    complaintType,
    deviceSerial,
    usageEnv,
    failureHours,
    onDeviceSerialChange,
    onUsageEnvChange,
    onFailureHoursChange,
}: ComplaintWarrantySectionProps) => {
    if (complaintType !== 'warranty' && complaintType !== 'field_failure') return null;

    return (
        <>
            <h6 className="text-muted mb-3">
                {complaintType === 'warranty' ? 'Warranty 申請資訊' : 'Field Failure 資訊'}
            </h6>
            <Row className="g-3 mb-3">
                <Col md={4}>
                    <Form.Group>
                        <Form.Label>裝置序號</Form.Label>
                        <Form.Control value={deviceSerial} onChange={e => onDeviceSerialChange(e.target.value)} />
                    </Form.Group>
                </Col>
                <Col md={4}>
                    <Form.Group>
                        <Form.Label>使用環境</Form.Label>
                        <Form.Control value={usageEnv} onChange={e => onUsageEnvChange(e.target.value)} />
                    </Form.Group>
                </Col>
                <Col md={4}>
                    <Form.Group>
                        <Form.Label>故障時數（hr）</Form.Label>
                        <Form.Control
                            type="number"
                            min="0"
                            value={failureHours}
                            onChange={e => onFailureHoursChange(e.target.value)}
                        />
                    </Form.Group>
                </Col>
            </Row>
        </>
    );
};

interface ComplaintResponseSectionProps {
    status: string;
    initialReply: string;
    finalReply: string;
    onStatusChange: (value: string) => void;
    onInitialReplyChange: (value: string) => void;
    onFinalReplyChange: (value: string) => void;
}

export const ComplaintResponseSection = ({
    status,
    initialReply,
    finalReply,
    onStatusChange,
    onInitialReplyChange,
    onFinalReplyChange,
}: ComplaintResponseSectionProps) => (
    <>
        <h6 className="text-muted mb-3">處理回覆</h6>
        <Row className="g-3 mb-3">
            <Col md={4}>
                <Form.Group>
                    <Form.Label>狀態</Form.Label>
                    <Form.Select value={status} onChange={e => onStatusChange(e.target.value)}>
                        {['待處理', '處理中', '已結案'].map(option => (
                            <option key={option} value={option}>{option}</option>
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
                        onChange={e => onInitialReplyChange(e.target.value)}
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
                        onChange={e => onFinalReplyChange(e.target.value)}
                    />
                </Form.Group>
            </Col>
        </Row>
    </>
);
