import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import toast from 'react-hot-toast';
import api from '../../services/api';
import { getReworkErrorMessage } from './reworkError';
import type { ReworkExecutionDetail } from '../../types';
import { useInspectors } from '../../hooks/useInspectors';

// 使用 types/index.ts 的 ReworkExecutionDetail 取代本地 interface，保持型別一致
interface EditExecutionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    execution: ReworkExecutionDetail | null;
}

const EditExecutionModal = ({ show, handleClose, onSuccess, execution }: EditExecutionModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show && !!execution });
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

    const loadExecutionData = useCallback(() => {
        if (!execution) return;
        setResponsiblePerson(execution.負責人員姓名 || '');
        setDepartment(execution.執行部門 || '製造部');
        setCollaborators(execution.協同人員 || '');
        setStartTime(formatDateTimeLocal(execution.開始時間 || ''));
        setExpectedEndTime(formatDateTimeLocal(execution.預計完成時間 || ''));
        setActualEndTime(formatDateTimeLocal(execution.實際完成時間 || ''));
        setEquipment(execution.使用設備 || '');
        setMethod(execution.重工方式 || '');
        setSopNo(execution.SOP編號 || '');
        setConsumables(execution.耗材記錄 || '');
        setCompletedQty(execution.完成數量?.toString() || '');
        setDefectQty(execution.不良數量?.toString() || '');
        setStatus(execution.執行狀況 || '');
        setAbnormalStatus(execution.異常狀況 || '');
    }, [execution]);

    // useEffect 放在 useCallback 宣告後，確保函數已初始化
    useEffect(() => {
        if (show && execution) {
            loadExecutionData();
        }
    }, [show, execution, loadExecutionData]);

    const formatDateTimeLocal = (dateStr: string) => {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return '';
        // 以本地時間組字串，避免 toISOString() 轉成 UTC 導致時間偏移
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
    };

    const handleSubmit = async () => {
        if (!execution) return;

        setLoading(true);
        try {
            const payload: ReworkExecutionDetail = {} as ReworkExecutionDetail;
            
            if (responsiblePerson) payload.負責人員姓名 = responsiblePerson;
            if (department) payload.執行部門 = department;
            if (collaborators) payload.協同人員 = collaborators;
            if (startTime) payload.開始時間 = startTime;
            if (expectedEndTime) payload.預計完成時間 = expectedEndTime;
            if (actualEndTime) payload.實際完成時間 = actualEndTime;
            if (equipment) payload.使用設備 = equipment;
            if (method) payload.重工方式 = method;
            if (sopNo) payload.SOP編號 = sopNo;
            if (consumables) payload.耗材記錄 = consumables;
            if (completedQty) payload.完成數量 = parseFloat(completedQty);
            if (defectQty) payload.不良數量 = parseFloat(defectQty);
            if (status) payload.執行狀況 = status;
            if (abnormalStatus) payload.異常狀況 = abnormalStatus;

            await api.put(`/rework/execution/${execution.識別碼}`, payload);
            toast.success('執行記錄已更新');
            onSuccess();
            handleClose();
        } catch (error: unknown) {
            toast.error(getReworkErrorMessage(error, '更新失敗'));
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
                <Modal.Title>編輯執行記錄</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>負責人員</Form.Label>
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

export default EditExecutionModal;
