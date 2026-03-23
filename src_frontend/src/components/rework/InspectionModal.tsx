import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import api from '../../services/api';

interface Inspector {
    id: number;
    name: string;
}

interface InspectionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    reworkNumber: string;
}

const InspectionModal = ({ show, handleClose, onSuccess, reworkNumber }: InspectionModalProps) => {
    const [inspectors, setInspectors] = useState<Inspector[]>([]);
    const [loading, setLoading] = useState(false);

    const [inspector, setInspector] = useState('');
    const [inspectionItem, setInspectionItem] = useState('');
    const [inspectionResult, setInspectionResult] = useState('合格');
    const [defectQty, setDefectQty] = useState('0');
    const [inspectionDate, setInspectionDate] = useState('');
    const [remark, setRemark] = useState('');

    useEffect(() => {
        if (show) {
            loadInspectors();
            resetForm();
        }
    }, [show]);

    const loadInspectors = async () => {
        try {
            const res = await api.get<Inspector[]>('/inspectors');
            setInspectors(res.data);
        } catch (error) {
            console.error('Failed to load inspectors', error);
        }
    };

    const resetForm = () => {
        setInspector('');
        setInspectionItem('');
        setInspectionResult('合格');
        setDefectQty('0');
        setInspectionDate(new Date().toISOString().split('T')[0]);
        setRemark('');
    };

    const handleSubmit = async () => {
        if (!inspector || !inspectionItem) {
            alert('請填寫檢驗人員和檢驗項目');
            return;
        }

        setLoading(true);
        try {
            const payload = {
                "重工單號": reworkNumber,
                "檢驗人員姓名": inspector,
                "檢驗項目": inspectionItem,
                "檢驗結果": inspectionResult,
                "不良數量": parseInt(defectQty) || 0,
                "檢驗日期": inspectionDate,
                "檢驗備註": remark
            };

            await api.post('/rework/inspect', payload);
            alert('品檢記錄已新增！');
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
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>新增品檢記錄 - {reworkNumber}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>檢驗人員 *</Form.Label>
                                <Form.Select
                                    value={inspector}
                                    onChange={(e) => setInspector(e.target.value)}
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
                                <Form.Label>檢驗日期</Form.Label>
                                <Form.Control
                                    type="date"
                                    value={inspectionDate}
                                    onChange={(e) => setInspectionDate(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Form.Group className="mb-3">
                        <Form.Label>檢驗項目 *</Form.Label>
                        <Form.Control
                            value={inspectionItem}
                            onChange={(e) => setInspectionItem(e.target.value)}
                            placeholder="例如: 外觀檢驗、尺寸檢驗、功能測試"
                        />
                    </Form.Group>

                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>檢驗結果</Form.Label>
                                <Form.Select
                                    value={inspectionResult}
                                    onChange={(e) => setInspectionResult(e.target.value)}
                                >
                                    <option value="合格">合格</option>
                                    <option value="不合格">不合格</option>
                                    <option value="待判定">待判定</option>
                                </Form.Select>
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>不良數量</Form.Label>
                                <Form.Control
                                    type="number"
                                    value={defectQty}
                                    onChange={(e) => setDefectQty(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Form.Group className="mb-3">
                        <Form.Label>備註</Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={2}
                            value={remark}
                            onChange={(e) => setRemark(e.target.value)}
                            placeholder="備註說明"
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

export default InspectionModal;
