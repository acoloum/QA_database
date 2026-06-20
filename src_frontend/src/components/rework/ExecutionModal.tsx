import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import api from '../../services/api';
import { useInspectors } from '../../hooks/useInspectors';

interface ExecutionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    reworkNumber: string;
}

const ExecutionModal = ({ show, handleClose, onSuccess, reworkNumber }: ExecutionModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show });
    const [loading, setLoading] = useState(false);

    const [responsiblePerson, setResponsiblePerson] = useState('');
    const [department, setDepartment] = useState('製造部');
    const [collaborators, setCollaborators] = useState('');
    const [startTime, setStartTime] = useState('');
    const [expectedEndTime, setExpectedEndTime] = useState('');
    const [actualEndTime, setActualEndTime] = useState('');
    const [equipment, setEquipment] = useState('');
    const [method, setMethod] = useState('');
    const [sopNo, setSopNo] = useState('');
    const [consumables, setConsumables] = useState('');
    const [completedQty, setCompletedQty] = useState('');
    const [defectQty, setDefectQty] = useState('');
    const [status, setStatus] = useState('');
    const [abnormalStatus, setAbnormalStatus] = useState('');

    useEffect(() => {
        if (show) {
            resetForm();
        }
    }, [show]);

    const resetForm = () => {
        setResponsiblePerson('');
        setDepartment('製造部');
        setCollaborators('');
        setStartTime('');
        setExpectedEndTime('');
        setActualEndTime('');
        setEquipment('');
        setMethod('');
        setSopNo('');
        setConsumables('');
        setCompletedQty('');
        setDefectQty('');
        setStatus('');
        setAbnormalStatus('');
    };

    const handleSubmit = async () => {
        if (!responsiblePerson) {
            alert('請選擇負責人員');
            return;
        }

        setLoading(true);
        try {
            const payload = {
                "重工單號": reworkNumber,
                "負責人員姓名": responsiblePerson,
                "執行部門": department,
                "協同人員": collaborators,
                "開始時間": startTime,
                "預計完成時間": expectedEndTime,
                "實際完成時間": actualEndTime,
                "使用設備": equipment,
                "重工方式": method,
                "SOP編號": sopNo,
                "耗材記錄": consumables,
                "完成數量": completedQty || 0,
                "不良數量": defectQty || 0,
                "執行狀況": status,
                "異常狀況": abnormalStatus
            };

            await api.post('/rework/execute', payload);
            alert('執行記錄已新增！');
            onSuccess();
            handleClose();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } } };
            console.error(error);
            alert(err.response?.data?.error || '新增失敗');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal show={show} onHide={handleClose} size="lg" dialogClassName="modal-rework">
            <style type="text/css">{`
                .modal-rework {
                    max-width: 800px !important;
                }
                .modal-rework .modal-body {
                    max-height: 75vh;
                    overflow-y: auto;
                }
            `}</style>
            <Modal.Header closeButton>
                <Modal.Title>新增執行記錄 - {reworkNumber}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>負責人員 *</Form.Label>
                                <Form.Select
                                    value={responsiblePerson}
                                    onChange={(e) => setResponsiblePerson(e.target.value)}
                                >
                                    <option value="">請選擇</option>
                                    {inspectors.map(i => (
                                        <option key={i.id} value={i.name}>{i.name}</option>
                                    ))}
                                </Form.Select>
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>執行部門</Form.Label>
                                <Form.Select value={department} onChange={(e) => setDepartment(e.target.value)}>
                                    <option value="製造部">製造部</option>
                                    <option value="品保部">品保部</option>
                                    <option value="工程部">工程部</option>
                                </Form.Select>
                            </Form.Group>
                        </Col>
                    </Row>

                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>開始時間</Form.Label>
                                <Form.Control
                                    type="datetime-local"
                                    value={startTime}
                                    onChange={(e) => setStartTime(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>預計完成時間</Form.Label>
                                <Form.Control
                                    type="datetime-local"
                                    value={expectedEndTime}
                                    onChange={(e) => setExpectedEndTime(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>實際完成時間</Form.Label>
                                <Form.Control
                                    type="datetime-local"
                                    value={actualEndTime}
                                    onChange={(e) => setActualEndTime(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>使用設備</Form.Label>
                                <Form.Control
                                    value={equipment}
                                    onChange={(e) => setEquipment(e.target.value)}
                                    placeholder="設備名稱"
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>重工方式</Form.Label>
                                <Form.Control
                                    value={method}
                                    onChange={(e) => setMethod(e.target.value)}
                                    placeholder="重工方式描述"
                                />
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>SOP編號</Form.Label>
                                <Form.Control
                                    value={sopNo}
                                    onChange={(e) => setSopNo(e.target.value)}
                                    placeholder="SOP-XXX"
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Form.Group className="mb-3">
                        <Form.Label>耗材記錄</Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={2}
                            value={consumables}
                            onChange={(e) => setConsumables(e.target.value)}
                            placeholder="使用的耗材記錄"
                        />
                    </Form.Group>

                    <Row>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>完成數量</Form.Label>
                                <Form.Control
                                    type="number"
                                    value={completedQty}
                                    onChange={(e) => setCompletedQty(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>不良數量</Form.Label>
                                <Form.Control
                                    type="number"
                                    value={defectQty}
                                    onChange={(e) => setDefectQty(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>協同人員</Form.Label>
                                <Form.Control
                                    value={collaborators}
                                    onChange={(e) => setCollaborators(e.target.value)}
                                    placeholder="協同人員"
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Form.Group className="mb-3">
                        <Form.Label>執行狀況</Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={2}
                            value={status}
                            onChange={(e) => setStatus(e.target.value)}
                            placeholder="執行狀況描述"
                        />
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>異常狀況</Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={2}
                            value={abnormalStatus}
                            onChange={(e) => setAbnormalStatus(e.target.value)}
                            placeholder="異常狀況描述"
                        />
                    </Form.Group>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={loading}>
                    {loading ? '儲存中...' : '儲存'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ExecutionModal;
