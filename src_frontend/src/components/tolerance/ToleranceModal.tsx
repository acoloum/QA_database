import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col, Table } from 'react-bootstrap';
import api from '../../services/api';

interface ToleranceModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
    vendors: any[];
}

interface DetailRow {
    item: string;
    position: string;
    size_min: string;
    size_max: string;
    tol_min: string;
    tol_max: string;
    std: string;
    unit: string;
    remark: string;
}

const ToleranceModal = ({ show, handleClose, onSuccess, editId, vendors }: ToleranceModalProps) => {
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [vendorId, setVendorId] = useState('');
    const [remark, setRemark] = useState('');
    const [details, setDetails] = useState<DetailRow[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (show) {
            if (editId) {
                loadDetail(editId);
            } else {
                resetForm();
            }
        }
    }, [show, editId]);

    const resetForm = () => {
        setMaterial('');
        setSpec('');
        setVendorId('');
        setRemark('');
        setDetails([createEmptyRow()]);
    };

    const createEmptyRow = (): DetailRow => ({
        item: '', position: '', size_min: '', size_max: '', tol_min: '', tol_max: '', std: '', unit: 'mm', remark: ''
    });

    const loadDetail = async (id: number) => {
        setLoading(true);
        try {
            const res = await api.get(`/tolerance/${id}`);
            if (res.data.success) {
                const { main, details: dList } = res.data;
                setMaterial(main.材質 || '');
                setSpec(main.規格 || '');
                setVendorId(main.廠商ID || '');
                setRemark(main.備註 || '');

                if (dList && dList.length > 0) {
                    setDetails(dList.map((d: any) => ({
                        item: d.測量項目 || '',
                        position: d.測量位置 || '',
                        size_min: d.尺寸下限 ?? '',
                        size_max: d.尺寸上限 ?? '',
                        tol_min: d.公差下限 ?? '',
                        tol_max: d.公差上限 ?? '',
                        std: d.標準值 ?? '',
                        unit: d.單位 || 'mm',
                        remark: d.備註 || ''
                    })));
                } else {
                    setDetails([createEmptyRow()]);
                }
            }
        } catch (error) {
            console.error("Failed to load detail", error);
        } finally {
            setLoading(false);
        }
    };

    const handleDetailChange = (index: number, field: keyof DetailRow, value: string) => {
        const newDetails = [...details];
        newDetails[index][field] = value;
        setDetails(newDetails);
    };

    const addRow = () => {
        setDetails([...details, createEmptyRow()]);
    };

    const removeRow = (index: number) => {
        if (details.length > 1) {
            setDetails(details.filter((_, i) => i !== index));
        }
    };

    const handleSave = async () => {
        if (!material) {
            alert('請輸入材質');
            return;
        }

        const payloadDetails = details
            .filter(d => d.item) // Filter out empty rows
            .map(d => ({
                測量項目: d.item,
                測量位置: d.position,
                尺寸下限: d.size_min === '' ? null : parseFloat(d.size_min),
                尺寸上限: d.size_max === '' ? null : parseFloat(d.size_max),
                公差下限: d.tol_min === '' ? null : parseFloat(d.tol_min),
                公差上限: d.tol_max === '' ? null : parseFloat(d.tol_max),
                標準值: d.std === '' ? null : parseFloat(d.std),
                單位: d.unit,
                備註: d.remark
            }));

        const payload = {
            材質: material,
            規格: spec,
            廠商ID: vendorId ? parseInt(vendorId) : null,
            備註: remark,
            details: payloadDetails
        };

        try {
            const url = editId ? `/tolerance/update/${editId}` : '/tolerance/add';
            const res = await api.post(url, payload);
            if (res.data.success) {
                alert('儲存成功');
                onSuccess();
                handleClose();
            } else {
                alert(res.data.error || '儲存失敗');
            }
        } catch (error: any) {
            console.error("Save failed", error);
            alert('儲存失敗');
        }
    };

    return (
        <Modal show={show} onHide={handleClose} size="xl" backdrop="static">
            <Modal.Header closeButton>
                <Modal.Title>{editId ? '編輯公差資料' : '新增公差資料'}</Modal.Title>
            </Modal.Header>
            <Modal.Body style={{ maxHeight: '80vh', overflowY: 'auto' }}>
                {loading ? <div className="text-center">載入中...</div> : (
                    <>
                        <div className="bg-light p-3 rounded mb-3">
                            <Row className="g-3">
                                <Col md={4}><Form.Label>材質 <span className="text-danger">*</span></Form.Label><Form.Control value={material} onChange={e => setMaterial(e.target.value)} required /></Col>
                                <Col md={4}><Form.Label>規格</Form.Label><Form.Control value={spec} onChange={e => setSpec(e.target.value)} /></Col>
                                <Col md={4}>
                                    <Form.Label>廠商</Form.Label>
                                    <Form.Select value={vendorId} onChange={e => setVendorId(e.target.value)}>
                                        <option value="">-- 請選擇 --</option>
                                        {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                                    </Form.Select>
                                </Col>
                                <Col md={12}><Form.Label>備註</Form.Label><Form.Control value={remark} onChange={e => setRemark(e.target.value)} /></Col>
                            </Row>
                        </div>

                        <div className="d-flex justify-content-between align-items-center mb-2">
                            <h5 className="mb-0"><i className="bi bi-list"></i> 公差明細</h5>
                            <Button variant="outline-primary" size="sm" onClick={addRow}><i className="bi bi-plus"></i> 新增明細</Button>
                        </div>

                        <Table bordered hover responsive size="sm">
                            <thead className="table-light text-center">
                                <tr>
                                    <th style={{ width: '15%' }}>測量項目</th>
                                    <th style={{ width: '8%' }}>位置</th>
                                    <th>尺寸下限</th>
                                    <th>尺寸上限</th>
                                    <th>公差下限</th>
                                    <th>公差上限</th>
                                    <th>標準值</th>
                                    <th style={{ width: '8%' }}>單位</th>
                                    <th>備註</th>
                                    <th style={{ width: '5%' }}></th>
                                </tr>
                            </thead>
                            <tbody>
                                {details.map((d, index) => (
                                    <tr key={index}>
                                        <td><Form.Control size="sm" value={d.item} onChange={e => handleDetailChange(index, 'item', e.target.value)} placeholder="項目" /></td>
                                        <td><Form.Control size="sm" value={d.position} onChange={e => handleDetailChange(index, 'position', e.target.value)} placeholder="Pos" /></td>
                                        <td><Form.Control size="sm" type="number" step="0.0001" value={d.size_min} onChange={e => handleDetailChange(index, 'size_min', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" step="0.0001" value={d.size_max} onChange={e => handleDetailChange(index, 'size_max', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" step="0.0001" value={d.tol_min} onChange={e => handleDetailChange(index, 'tol_min', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" step="0.0001" value={d.tol_max} onChange={e => handleDetailChange(index, 'tol_max', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" step="0.0001" value={d.std} onChange={e => handleDetailChange(index, 'std', e.target.value)} /></td>
                                        <td><Form.Control size="sm" value={d.unit} onChange={e => handleDetailChange(index, 'unit', e.target.value)} /></td>
                                        <td><Form.Control size="sm" value={d.remark} onChange={e => handleDetailChange(index, 'remark', e.target.value)} /></td>
                                        <td className="text-center">
                                            <Button variant="outline-danger" size="sm" onClick={() => removeRow(index)} tabIndex={-1}><i className="bi bi-trash"></i></Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    </>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSave}>儲存</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ToleranceModal;
