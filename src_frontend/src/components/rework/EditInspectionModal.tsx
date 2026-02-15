import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import api from '../../services/api';

interface Inspector {
    id: number;
    name: string;
}

interface Inspection {
    識別碼: number;
    重工單號: string;
    檢驗項目: string;
    檢驗結果: string;
    不良數量: number;
    檢驗人員姓名: string;
    檢驗日期: string;
    檢驗備註: string;
}

interface EditInspectionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    inspection: Inspection | null;
}

const EditInspectionModal = ({ show, handleClose, onSuccess, inspection }: EditInspectionModalProps) => {
    const [inspectors, setInspectors] = useState<Inspector[]>([]);
    const [loading, setLoading] = useState(false);

    const [inspector, setInspector] = useState('');
    const [inspectionItem, setInspectionItem] = useState('');
    const [inspectionResult, setInspectionResult] = useState('合格');
    const [defectQty, setDefectQty] = useState('0');
    const [inspectionDate, setInspectionDate] = useState('');
    const [remark, setRemark] = useState('');

    useEffect(() => {
        if (show && inspection) {
            loadInspectors();
            loadInspectionData();
        }
    }, [show, inspection]);

    const loadInspectors = async () => {
        try {
            const res = await api.get<Inspector[]>('/inspectors');
            setInspectors(res.data);
        } catch (error) {
            console.error('Failed to load inspectors', error);
        }
    };

    const loadInspectionData = () => {
        if (!inspection) return;
        setInspector(inspection.檢驗人員姓名 || '');
        setInspectionItem(inspection.檢驗項目 || '');
        setInspectionResult(inspection.檢驗結果 || '合格');
        setDefectQty(inspection.不良數量?.toString() || '0');
        setInspectionDate(inspection.檢驗日期 ? inspection.檢驗日期.split(' ')[0] : '');
        setRemark(inspection.檢驗備註 || '');
    };

    const handleSubmit = async () => {
        if (!inspection) return;

        setLoading(true);
        try {
            const payload: any = {};
            
            if (inspector) payload.檢驗人員姓名 = inspector;
            if (inspectionItem) payload.檢驗項目 = inspectionItem;
            if (inspectionResult) payload.檢驗結果 = inspectionResult;
            if (defectQty !== undefined) payload.不良數量 = parseInt(defectQty) || 0;
            if (inspectionDate) payload.檢驗日期 = inspectionDate;
            if (remark !== undefined) payload.檢驗備註 = remark;

            await api.put(`/rework/inspection/${inspection.識別碼}`, payload);
            alert('品檢記錄已更新！');
            onSuccess();
            handleClose();
        } catch (error: any) {
            console.error(error);
            alert(error.response?.data?.error || '更新失敗');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>編輯品檢記錄</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>檢驗人員</Form.Label>
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
                        <Form.Label>檢驗項目</Form.Label>
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

export default EditInspectionModal;
