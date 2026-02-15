import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import api from '../../services/api';

interface Inspector {
    id: number;
    name: string;
}

interface CostModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    reworkId: number;
    reworkNumber: string;
}

const CostModal = ({ show, handleClose, onSuccess, reworkId, reworkNumber }: CostModalProps) => {
    const [inspectors, setInspectors] = useState<Inspector[]>([]);
    const [loading, setLoading] = useState(false);

    const [costType, setCostType] = useState('人工成本');
    const [costItem, setCostItem] = useState('');
    const [unitCost, setUnitCost] = useState('');
    const [quantity, setQuantity] = useState('');
    const [currency, setCurrency] = useState('TWD');
    const [recorder, setRecorder] = useState('');
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
            if (res.data.length > 0) {
                setRecorder(res.data[0].name);
            }
        } catch (error) {
            console.error('Failed to load inspectors', error);
        }
    };

    const resetForm = () => {
        setCostType('人工成本');
        setCostItem('');
        setUnitCost('');
        setQuantity('1');
        setCurrency('TWD');
        setRemark('');
    };

    const handleSubmit = async () => {
        if (!costType || !costItem) {
            alert('請填寫成本類型和成本項目');
            return;
        }

        const qty = parseFloat(quantity) || 1;
        const uCost = parseFloat(unitCost) || 0;
        const totalCost = uCost * qty;

        setLoading(true);
        try {
            const payload = {
                "重工單號": reworkNumber,
                "成本類型": costType,
                "成本項目": costItem,
                "單位成本": uCost,
                "數量": qty,
                "總成本": totalCost,
                "成本幣別": currency,
                "記錄人員姓名": recorder,
                "備註": remark
            };

            await api.post('/rework/cost', payload);
            alert('成本記錄已新增！');
            onSuccess();
            handleClose();
        } catch (error: any) {
            console.error(error);
            alert(error.response?.data?.error || '新增失敗');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>新增成本記錄 - {reworkNumber}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>成本類型 *</Form.Label>
                                <Form.Select
                                    value={costType}
                                    onChange={(e) => setCostType(e.target.value)}
                                >
                                    <option value="人工成本">人工成本</option>
                                    <option value="材料成本">材料成本</option>
                                    <option value="設備成本">設備成本</option>
                                    <option value="其他成本">其他成本</option>
                                </Form.Select>
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>成本項目 *</Form.Label>
                                <Form.Control
                                    value={costItem}
                                    onChange={(e) => setCostItem(e.target.value)}
                                    placeholder="例如: 人力費用、原料費用"
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Row>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>單位成本</Form.Label>
                                <Form.Control
                                    type="number"
                                    step="0.01"
                                    value={unitCost}
                                    onChange={(e) => setUnitCost(e.target.value)}
                                    placeholder="0.00"
                                />
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>數量</Form.Label>
                                <Form.Control
                                    type="number"
                                    value={quantity}
                                    onChange={(e) => setQuantity(e.target.value)}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>幣別</Form.Label>
                                <Form.Select value={currency} onChange={(e) => setCurrency(e.target.value)}>
                                    <option value="TWD">TWD</option>
                                    <option value="USD">USD</option>
                                    <option value="EUR">EUR</option>
                                    <option value="JPY">JPY</option>
                                </Form.Select>
                            </Form.Group>
                        </Col>
                    </Row>

                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>記錄人員</Form.Label>
                                <Form.Select
                                    value={recorder}
                                    onChange={(e) => setRecorder(e.target.value)}
                                >
                                    {inspectors.map(i => (
                                        <option key={i.id} value={i.name}>{i.name}</option>
                                    ))}
                                </Form.Select>
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

                    <div className="alert alert-info">
                        <strong>預估總成本：</strong> 
                        ${((parseFloat(unitCost) || 0) * (parseFloat(quantity) || 0)).toFixed(2)}
                    </div>
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

export default CostModal;
