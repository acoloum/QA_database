import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import toast from 'react-hot-toast';
import { useInspectors } from '../../hooks/useInspectors';
import { buildReworkCostPayload, calculateReworkTotalCost } from './reworkFormPayload';
import { useCreateReworkCost } from './useReworkMutations';

interface CostModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    reworkNumber: string;
}

const CostModal = ({ show, handleClose, onSuccess, reworkNumber }: CostModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show });
    const createCost = useCreateReworkCost({
        onSuccess: () => {
            onSuccess();
            handleClose();
        }
    });

    const [costType, setCostType] = useState('人工成本');
    const [costItem, setCostItem] = useState('');
    const [unitCost, setUnitCost] = useState('');
    const [quantity, setQuantity] = useState('');
    const [currency, setCurrency] = useState('TWD');
    const [recorder, setRecorder] = useState('');
    const [remark, setRemark] = useState('');

    const resetForm = () => {
        setCostType('人工成本');
        setCostItem('');
        setUnitCost('');
        setQuantity('1');
        setCurrency('TWD');
        setRecorder('');
        setRemark('');
    };

    useEffect(() => {
        let cancelled = false;
        if (show) {
            queueMicrotask(() => {
                if (!cancelled) resetForm();
            });
        }
        return () => {
            cancelled = true;
        };
    }, [show]);

    useEffect(() => {
        let cancelled = false;
        if (show && inspectors.length > 0 && !recorder) {
            queueMicrotask(() => {
                if (!cancelled) setRecorder(inspectors[0].name);
            });
        }
        return () => {
            cancelled = true;
        };
    }, [show, inspectors, recorder]);

    const handleSubmit = () => {
        if (!costType || !costItem) {
            toast.error('請填寫成本類型和成本項目');
            return;
        }

        createCost.mutate(buildReworkCostPayload({
            reworkNumber,
            costType,
            costItem,
            unitCost,
            quantity,
            currency,
            recorder,
            remark
        }));
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
                        ${calculateReworkTotalCost(unitCost, quantity).toFixed(2)}
                    </div>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={createCost.isPending}>
                    {createCost.isPending ? '儲存中...' : '儲存'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default CostModal;
