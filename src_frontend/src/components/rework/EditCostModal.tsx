import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import type { ReworkCostDetail } from '../../types';
import { useInspectors } from '../../hooks/useInspectors';
import { buildReworkCostPayload, calculateReworkTotalCost } from './reworkFormPayload';
import { useUpdateReworkCost } from './useReworkMutations';

// 使用 types/index.ts 的 ReworkCostDetail 取代本地 interface，保持型別一致
interface EditCostModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    cost: ReworkCostDetail | null;
}

const EditCostModal = ({ show, handleClose, onSuccess, cost }: EditCostModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show && !!cost });
    const updateCost = useUpdateReworkCost({
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

    const loadCostData = useCallback(() => {
        if (!cost) return;
        setCostType(cost.成本類型 || '人工成本');
        setCostItem(cost.成本項目 || '');
        setUnitCost(cost.單位成本?.toString() || '');
        setQuantity(cost.數量?.toString() || '1');
        setCurrency(cost.成本幣別 || 'TWD');
        setRecorder(cost.記錄人員姓名 || '');
        setRemark(cost.備註 || '');
    }, [cost]);

    // useEffect 放在 useCallback 宣告後，確保函數已初始化
    useEffect(() => {
        let cancelled = false;
        if (show && cost) {
            queueMicrotask(() => {
                if (!cancelled) loadCostData();
            });
        }
        return () => {
            cancelled = true;
        };
    }, [show, cost, loadCostData]);

    const handleSubmit = () => {
        if (!cost) return;
        const id = cost.識別碼;
        if (!id) return;

        updateCost.mutate({
            id,
            payload: buildReworkCostPayload({
                costType,
                costItem,
                unitCost,
                quantity,
                currency,
                recorder,
                remark
            })
        });
    };

    return (
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>編輯成本記錄</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>成本類型</Form.Label>
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
                                <Form.Label>成本項目</Form.Label>
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
                                    <option value="">請選擇</option>
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
                <Button variant="primary" onClick={handleSubmit} disabled={updateCost.isPending}>
                    {updateCost.isPending ? '儲存中...' : '儲存'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default EditCostModal;
