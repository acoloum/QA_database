import { Form, Row, Col } from 'react-bootstrap';

import type { ComplaintType } from '../../types';

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
