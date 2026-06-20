import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import toast from 'react-hot-toast';
import api from '../../services/api';
import { getReworkErrorMessage } from './reworkError';
import type { ReworkInspectionDetail } from '../../types';
import { useInspectors } from '../../hooks/useInspectors';

// 使用 types/index.ts 的 ReworkInspectionDetail 取代本地 interface，保持型別一致
interface EditInspectionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    inspection: ReworkInspectionDetail | null;
}

const EditInspectionModal = ({ show, handleClose, onSuccess, inspection }: EditInspectionModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show && !!inspection });
    const [loading, setLoading] = useState(false);

    const [inspector, setInspector] = useState('');
    const [inspectionItem, setInspectionItem] = useState('');
    const [inspectionResult, setInspectionResult] = useState('合格');
    const [defectQty, setDefectQty] = useState('0');
    const [inspectionDate, setInspectionDate] = useState('');
    const [remark, setRemark] = useState('');

    const loadInspectionData = useCallback(() => {
        if (!inspection) return;
        setInspector(inspection.檢驗人員姓名 || '');
        setInspectionItem(inspection.檢驗項目 || '');
        setInspectionResult(inspection.檢驗結果 || '合格');
        setDefectQty(inspection.不良數量?.toString() || '0');
        setInspectionDate(inspection.檢驗日期 ? inspection.檢驗日期.split(' ')[0] : '');
        setRemark(inspection.檢驗備註 || '');
    }, [inspection]);

    // useEffect 放在 useCallback 宣告後，確保函數已初始化
    useEffect(() => {
        if (show && inspection) {
            loadInspectionData();
        }
    }, [show, inspection, loadInspectionData]);

    const handleSubmit = async () => {
        if (!inspection) return;

        setLoading(true);
        try {
            const payload: Partial<ReworkInspectionDetail> = {};
            
            if (inspector) payload.檢驗人員姓名 = inspector;
            if (inspectionItem) payload.檢驗項目 = inspectionItem;
            if (inspectionResult) payload.檢驗結果 = inspectionResult;
            if (defectQty !== undefined) payload.不良數量 = parseInt(defectQty) || 0;
            if (inspectionDate) payload.檢驗日期 = inspectionDate;
            if (remark !== undefined) payload.檢驗備註 = remark;

            await api.put(`/rework/inspection/${inspection.識別碼}`, payload);
            toast.success('品檢記錄已更新');
            onSuccess();
            handleClose();
        } catch (error: unknown) {
            toast.error(getReworkErrorMessage(error, '更新失敗'));
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
