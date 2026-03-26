import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Nav, Tab, Row, Col, Alert } from 'react-bootstrap';
import api from '../../services/api';
import type { CAR, Inspector } from '../../types';

interface CARAModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

const CARAModal = ({ show, handleClose, onSuccess, editId }: CARAModalProps) => {
    const [loading, setLoading] = useState(false);
    const [ncmrInfo, setNcmrInfo] = useState<CAR | null>(null);
    const [caraInfo, setCaraInfo] = useState<Partial<CAR>>({});
    const [inspectors, setInspectors] = useState<Inspector[]>([]);

    // Form fields
    const [owner, setOwner] = useState('');
    const [dContent, setDContent] = useState<Record<string, string>>({});
    const [isClosed, setIsClosed] = useState(false);

    const fetchInspectors = useCallback(async () => {
        try {
            const res = await api.get('/inspectors');
            setInspectors(res.data);
        } catch (error) {
            console.error("Failed to load inspectors", error);
        }
    }, []);

    const loadDetail = useCallback(async (id: number) => {
        setLoading(true);
        try {
            const res = await api.get(`/cara/detail/${id}`);
            const { ncmr, cara } = res.data;
            setNcmrInfo(ncmr);
            setCaraInfo(cara);
            setOwner(cara.負責人員姓名 || '');
            setIsClosed(cara.狀態 === '已結案');

            // Map D-steps (Skip D1, D5)
            const dMap: Record<string, string> = {};
            [2, 3, 4, 6, 7, 8].forEach(i => {
                const key = `D${i}_${getDName(i)}`;
                dMap[`d${i}`] = cara[key] || '';
            });
            setDContent(dMap);

        } catch (error) {
            console.error("Failed to load CAR detail", error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (show && editId) {
            loadDetail(editId);
            fetchInspectors();
        }
    }, [show, editId, loadDetail, fetchInspectors]);

    const getDName = (i: number) => {
        const map: Record<number, string> = { 2: '問題描述', 3: '暫時對策', 4: '真因分析', 6: '成效驗證', 7: '預防再發', 8: '結案確認' };
        return map[i];
    };

    const handleSave = async () => {
        const payload: Partial<CAR> = {
            "識別碼": editId,
            "負責人員姓名": owner,
            "狀態": isClosed ? '已結案' : '進行中'
        };

        [2, 3, 4, 6, 7, 8].forEach(i => {
            payload[`D${i}_${getDName(i)}`] = dContent[`d${i}`];
        });

        try {
            await api.post('/cara/update', payload);
            alert('儲存成功');
            onSuccess();
            handleClose();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } }; message?: string };
            alert('儲存失敗: ' + (err.response?.data?.error || err.message));
        }
    };

    const updateD = (key: string, val: string) => {
        setDContent(prev => ({ ...prev, [key]: val }));
    };

    return (
        <Modal show={show} onHide={handleClose} size="xl" backdrop="static">
            <Modal.Header closeButton>
                {/* caraInfo 屬性型別為 unknown，需轉為 string 才能在 JSX 中顯示 */}
                <Modal.Title>CAR 單號: {String(caraInfo.單號 ?? '')}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {loading ? <div className="text-center">載入中...</div> : (
                    <>
                        {ncmrInfo && (
                            <Alert variant="info">
                                <h6 className="fw-bold"><i className="bi bi-info-circle"></i> 異常資訊摘要</h6>
                                <Row className="small">
                                    {/* ncmrInfo 屬性型別為 unknown，需轉為 string */}
                                    <Col md={3}><strong>日期:</strong> {String(ncmrInfo.發現日期 ?? '').substring(0, 10)}</Col>
                                    <Col md={3}><strong>廠商:</strong> {String(ncmrInfo.廠商 ?? '')}</Col>
                                    <Col md={3}><strong>材質:</strong> {String(ncmrInfo.材質 ?? '')}</Col>
                                    <Col md={3}><strong>規格:</strong> {String(ncmrInfo.產品資訊 ?? '')}</Col>
                                    <Col md={12} className="mt-2"><strong>不良描述:</strong> {String(ncmrInfo.不良描述 ?? '')}</Col>
                                </Row>
                            </Alert>
                        )}

                        <Tab.Container defaultActiveKey="d2">
                            <Nav variant="tabs" className="mb-3">
                                {[2, 3, 4, 6, 7, 8].map(i => (
                                    <Nav.Item key={i}>
                                        <Nav.Link eventKey={`d${i}`}>D{i} {getDName(i).substring(0, 2)}</Nav.Link>
                                    </Nav.Item>
                                ))}
                            </Nav>
                            <Tab.Content>
                                {[2, 3, 4, 6, 7, 8].map(i => (
                                    <Tab.Pane eventKey={`d${i}`} key={i}>
                                        <Form.Group>
                                            <Form.Label className="fw-bold">D{i}. {getDName(i)}</Form.Label>
                                            <Form.Control
                                                as="textarea"
                                                rows={10}
                                                value={dContent[`d${i}`] || ''}
                                                onChange={e => updateD(`d${i}`, e.target.value)}
                                                placeholder={`請輸入D${i}內容...`}
                                            />
                                        </Form.Group>
                                        {i === 8 && (
                                            <Form.Check
                                                type="switch"
                                                id="close-switch-car"
                                                label="確認結案 (此單據將無法再編輯)"
                                                className="mt-3 text-success fw-bold"
                                                checked={isClosed}
                                                onChange={e => setIsClosed(e.target.checked)}
                                            />
                                        )}
                                    </Tab.Pane>
                                ))}
                            </Tab.Content>
                        </Tab.Container>
                    </>
                )}
            </Modal.Body>
            <Modal.Footer>
                <div className="d-flex align-items-center me-auto">
                    <Form.Label className="me-2 mb-0">負責人員:</Form.Label>
                    <Form.Select value={owner} onChange={e => setOwner(e.target.value)} style={{ width: '150px' }}>
                        <option value="">請選擇</option>
                        {inspectors.map((insp: Inspector) => <option key={insp.id} value={insp.name}>{insp.name}</option>)}
                    </Form.Select>
                </div>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSave}>儲存進度</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default CARAModal;
