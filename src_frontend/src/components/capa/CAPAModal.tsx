import { useState, useEffect } from 'react';
import { Modal, Button, Form, Nav, Tab, Row, Col, Alert } from 'react-bootstrap';
import api from '../../services/api';
import type { CAPA, Inspector } from '../../types';

interface CAPAModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

const CAPAModal = ({ show, handleClose, onSuccess, editId }: CAPAModalProps) => {
    const [loading, setLoading] = useState(false);
    const [ncmrInfo, setNcmrInfo] = useState<CAPA | null>(null);
    const [capaInfo, setCapaInfo] = useState<Partial<CAPA>>({});
    const [inspectors, setInspectors] = useState<Inspector[]>([]);

    // Form fields
    const [owner, setOwner] = useState('');
    const [dContent, setDContent] = useState<Record<string, string>>({});
    const [isClosed, setIsClosed] = useState(false);

    useEffect(() => {
        if (show && editId) {
            loadDetail(editId);
            fetchInspectors();
        }
    }, [show, editId]);

    const fetchInspectors = async () => {
        try {
            const res = await api.get('/inspectors');
            setInspectors(res.data);
        } catch (error) {
            console.error("Failed to load inspectors", error);
        }
    };

    const loadDetail = async (id: number) => {
        setLoading(true);
        try {
            const res = await api.get(`/capa/detail/${id}`);
            const { ncmr, capa } = res.data;
            setNcmrInfo(ncmr);
            setCapaInfo(capa);
            setOwner(capa.負責人員姓名 || '');
            setIsClosed(capa.狀態 === '已結案');

            // Map D1-D8
            const dMap: Record<string, string> = {};
            for (let i = 1; i <= 8; i++) {
                const key = `D${i}_${getDName(i)}`;
                dMap[`d${i}`] = capa[key] || '';
            }
            setDContent(dMap);

        } catch (error) {
            console.error("Failed to load CAPA detail", error);
        } finally {
            setLoading(false);
        }
    };

    const getDName = (i: number) => {
        const map: Record<number, string> = { 1: '小組成員', 2: '問題描述', 3: '暫時對策', 4: '真因分析', 5: '永久對策', 6: '成效驗證', 7: '預防再發', 8: '結案確認' };
        return map[i];
    };

    const handleSave = async () => {
        const payload: any = {
            "識別碼": editId,
            "負責人員姓名": owner,
            "狀態": isClosed ? '已結案' : '進行中'
        };

        for (let i = 1; i <= 8; i++) {
            payload[`D${i}_${getDName(i)}`] = dContent[`d${i}`];
        }

        try {
            await api.post('/capa/update', payload);
            alert('儲存成功');
            onSuccess();
            handleClose();
        } catch (error: any) {
            alert('儲存失敗: ' + (error.response?.data?.error || error.message));
        }
    };

    const updateD = (key: string, val: string) => {
        setDContent(prev => ({ ...prev, [key]: val }));
    };

    return (
        <Modal show={show} onHide={handleClose} size="xl" backdrop="static">
            <Modal.Header closeButton>
                <Modal.Title>CAPA 單號: {capaInfo['8D單號'] || capaInfo.識別碼}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {loading ? <div className="text-center">載入中...</div> : (
                    <>
                        {ncmrInfo && (
                            <Alert variant="info">
                                <h6 className="fw-bold"><i className="bi bi-info-circle"></i> 異常資訊摘要</h6>
                                <Row className="small">
                                    <Col md={3}><strong>日期:</strong> {ncmrInfo.發現日期?.substring(0, 10)}</Col>
                                    <Col md={3}><strong>廠商:</strong> {ncmrInfo.廠商}</Col>
                                    <Col md={3}><strong>材質:</strong> {ncmrInfo.材質}</Col>
                                    <Col md={3}><strong>規格:</strong> {ncmrInfo.產品資訊}</Col>
                                    <Col md={12} className="mt-2"><strong>不良描述:</strong> {ncmrInfo.不良描述}</Col>
                                </Row>
                            </Alert>
                        )}

                        <Tab.Container defaultActiveKey="d1">
                            <Nav variant="tabs" className="mb-3">
                                {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
                                    <Nav.Item key={i}>
                                        <Nav.Link eventKey={`d${i}`}>D{i} {getDName(i).substring(0, 2)}</Nav.Link>
                                    </Nav.Item>
                                ))}
                            </Nav>
                            <Tab.Content>
                                {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
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
                                                id="close-switch"
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
                        {inspectors.map((insp: any) => <option key={insp.id} value={insp.name}>{insp.name}</option>)}
                    </Form.Select>
                </div>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSave}>儲存進度</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default CAPAModal;
