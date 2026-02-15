import { useState, useEffect, Fragment } from 'react';
import { Modal, Button, Form, Row, Col, Table } from 'react-bootstrap';
import api from '../../services/api';

interface PatrolModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

interface PatrolDetailInput {
    group: string;
    item: string;
    pos: string;
    min: string;
    max: string;
}

const PatrolModal = ({ show, handleClose, onSuccess, editId }: PatrolModalProps) => {
    // Form State
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [machine, setMachine] = useState('');
    const [operator, setOperator] = useState('');
    const [inspector, setInspector] = useState('');
    const [customer, setCustomer] = useState('');
    const [material, setMaterial] = useState('');
    const [batch, setBatch] = useState('');
    const [spec, setSpec] = useState('');

    // Details State
    const [groupCount, setGroupCount] = useState(1);
    const [details, setDetails] = useState<PatrolDetailInput[]>([]);
    const [showInner, setShowInner] = useState(false);

    // Options
    const [machines, setMachines] = useState<{ id: number, name: string }[]>([]);
    const [operators, setOperators] = useState<{ id: number, name: string }[]>([]);
    const [inspectors, setInspectors] = useState<{ id: number, name: string }[]>([]);
    const [customers, setCustomers] = useState<{ id: number, name: string }[]>([]);

    useEffect(() => {
        if (show) {
            fetchOptions();
            if (editId) {
                loadDetail(editId);
            } else {
                resetForm();
            }
        }
    }, [show, editId]);

    const fetchOptions = async () => {
        try {
            const res = await api.get('/patrol/options');
            setMachines(res.data.machines);
            setOperators(res.data.operators);
            setInspectors(res.data.inspectors);
            setCustomers(res.data.customers);
        } catch (error) {
            console.error("Failed to load options", error);
        }
    };

    const resetForm = () => {
        setDate(new Date().toISOString().split('T')[0]);
        setMachine('');
        setOperator('');
        setInspector('');
        setCustomer('');
        setMaterial('');
        setBatch('');
        setSpec('');
        setGroupCount(1);
        setDetails([]); // Will be populated by initial render logic or kept empty
        setShowInner(false);
    };

    const loadDetail = async (id: number) => {
        try {
            const res = await api.get(`/patrol/detail/${id}`);
            const d = res.data;
            setDate(d.main.檢驗日期);
            setMachine(d.main.機台);
            setOperator(d.main.主機手);
            setInspector(d.main.檢驗人員);
            setCustomer(d.main.客戶名稱);
            setMaterial(d.main.材質);
            setBatch(d.main.原料批號);
            setSpec(d.main.擠壓規格);

            // Parse details to state
            const newDetails: PatrolDetailInput[] = d.details.map((item: any) => ({
                group: item.group,
                item: item.item,
                pos: item.pos,
                min: item.min?.toString() || '',
                max: item.max?.toString() || ''
            }));
            setDetails(newDetails);

            // Determine group count
            const groups = new Set(newDetails.map(d => d.group));
            setGroupCount(groups.size || 1);
        } catch (error) {
            console.error("Failed to load detail", error);
        }
    };

    const handleDetailChange = (group: string, pos: string, item: string, type: 'min' | 'max', value: string) => {
        setDetails(prev => {
            const existingIndex = prev.findIndex(d => d.group === group && d.pos === pos && d.item === item);
            if (existingIndex >= 0) {
                const newDetails = [...prev];
                newDetails[existingIndex] = { ...newDetails[existingIndex], [type]: value };
                return newDetails;
            } else {
                return [...prev, {
                    group, item, pos, min: type === 'min' ? value : '', max: type === 'max' ? value : ''
                }];
            }
        });
    };

    const getDetailValue = (group: string, pos: string, item: string, type: 'min' | 'max') => {
        const detail = details.find(d => d.group === group && d.pos === pos && d.item === item);
        return detail ? detail[type] : '';
    };

    const handleSubmit = async () => {
        // Collect valid details
        const validDetails = details.filter(d => d.min !== '' || d.max !== '').map(d => ({
            group: d.group,
            item: d.item,
            pos: d.pos,
            min: d.min === '' ? null : parseFloat(d.min),
            max: d.max === '' ? null : parseFloat(d.max)
        }));

        if (validDetails.length === 0) {
            alert('請至少輸入一組測量數值');
            return;
        }

        const payload = {
            id: editId,
            "檢驗日期": date,
            "機台": machine,
            "主機手": operator,
            "客戶名稱": customer,
            "材質": material,
            "原料批號": batch,
            "擠壓規格": spec,
            "檢驗人員": inspector,
            "details": validDetails
        };

        try {
            const url = editId ? '/patrol/update' : '/patrol/add';
            await api.post(url, payload);
            alert('儲存成功');
            onSuccess();
            handleClose();
        } catch (error: any) {
            console.error("Save failed", error);
            alert(error.response?.data?.error || '儲存失敗');
        }
    };

    // Render helper
    const renderTableRows = () => {
        const rows = [];
        const positions = ['前段', '中段', '後段'];
        const items = ['外徑', '內徑', '厚度'];

        for (let i = 1; i <= groupCount; i++) {
            const gName = `第${i}組`;
            rows.push(
                <tr key={i}>
                    <td className="fw-bold bg-light">{gName}</td>
                    {positions.map(pos =>
                        items.map(item => {
                            if (item === '內徑' && !showInner) return null;
                            return (
                                <Fragment key={`${pos}-${item}`}>
                                    <td>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            step="0.01"
                                            value={getDetailValue(gName, pos, item, 'min')}
                                            onChange={e => handleDetailChange(gName, pos, item, 'min', e.target.value)}
                                            className="patrol-input"
                                        />
                                    </td>
                                    <td>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            step="0.01"
                                            value={getDetailValue(gName, pos, item, 'max')}
                                            onChange={e => handleDetailChange(gName, pos, item, 'max', e.target.value)}
                                            className="patrol-input"
                                        />
                                    </td>
                                </Fragment>
                            );
                        })
                    )}
                </tr>
            );
        }
        return rows;
    };

    return (
        <Modal show={show} onHide={handleClose} dialogClassName="modal-95w" backdrop="static">
            <Modal.Header closeButton>
                <Modal.Title>{editId ? '編輯巡檢紀錄' : '新增巡檢紀錄'}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Row className="g-3 mb-4">
                        <Col md={3}><Form.Label>日期</Form.Label><Form.Control type="date" value={date} onChange={e => setDate(e.target.value)} /></Col>
                        <Col md={3}>
                            <Form.Label>機台</Form.Label>
                            <Form.Select value={machine} onChange={e => setMachine(e.target.value)}>
                                <option value="">請選擇</option>
                                {machines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                            </Form.Select>
                        </Col>
                        <Col md={3}>
                            <Form.Label>主機手</Form.Label>
                            <Form.Select value={operator} onChange={e => setOperator(e.target.value)}>
                                <option value="">請選擇</option>
                                {operators.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                            </Form.Select>
                        </Col>
                        <Col md={3}>
                            <Form.Label>檢驗員</Form.Label>
                            <Form.Select value={inspector} onChange={e => setInspector(e.target.value)}>
                                <option value="">請選擇</option>
                                {inspectors.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                            </Form.Select>
                        </Col>
                        <Col md={4}>
                            <Form.Label>客戶名稱</Form.Label>
                            <Form.Select value={customer} onChange={e => setCustomer(e.target.value)} style={{ minWidth: '100%' }}>
                                <option value="">請選擇</option>
                                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                            </Form.Select>
                        </Col>
                        <Col md={4}><Form.Label>材質</Form.Label><Form.Control value={material} onChange={e => setMaterial(e.target.value)} style={{ width: '100%' }} /></Col>
                        <Col md={4}><Form.Label>原料批號</Form.Label><Form.Control value={batch} onChange={e => setBatch(e.target.value)} style={{ width: '100%' }} /></Col>
                        <Col md={12}><Form.Label>擠壓規格</Form.Label><Form.Control value={spec} onChange={e => setSpec(e.target.value)} style={{ width: '100%' }} /></Col>
                    </Row>

                    <div className="table-responsive">
                        <Table bordered size="sm" className="text-center align-middle">
                            <thead className="table-light">
                                <tr>
                                    <th rowSpan={3}>組別</th>
                                    <th colSpan={showInner ? 6 : 4}>前段</th>
                                    <th colSpan={showInner ? 6 : 4}>中段</th>
                                    <th colSpan={showInner ? 6 : 4}>後段</th>
                                </tr>
                                <tr>
                                    {['前段', '中段', '後段'].map(pos => (
                                        <Fragment key={pos}>
                                            <th colSpan={2}>外徑</th>
                                            {showInner && <th colSpan={2}>內徑</th>}
                                            <th colSpan={2}>厚度</th>
                                        </Fragment>
                                    ))}
                                </tr>
                                <tr>
                                    {['前段', '中段', '後段'].map(_ =>
                                        ['外徑', '內徑', '厚度'].map(item => {
                                            if (item === '內徑' && !showInner) return null;
                                            return <Fragment key={item}><th>Min</th><th>Max</th></Fragment>;
                                        })
                                    )}
                                </tr>
                            </thead>
                            <tbody>
                                {renderTableRows()}
                            </tbody>
                        </Table>
                    </div>

                    <div className="d-flex gap-2 mt-3">
                        <Button variant="outline-primary" onClick={() => setGroupCount(c => c + 1)}>
                            <i className="bi bi-plus-lg"></i> 新增組別
                        </Button>
                        <Button variant="outline-danger" onClick={() => setGroupCount(c => Math.max(1, c - 1))}>
                            <i className="bi bi-dash-lg"></i> 刪除組別
                        </Button>
                        <Button variant={showInner ? "info" : "outline-info"} onClick={() => setShowInner(!showInner)}>
                            <i className={`bi bi-arrows-${showInner ? 'collapse' : 'expand'}`}></i> {showInner ? '隱藏內徑' : '展開內徑'}
                        </Button>
                    </div>

                </Form>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="success" onClick={handleSubmit}>儲存</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default PatrolModal;
