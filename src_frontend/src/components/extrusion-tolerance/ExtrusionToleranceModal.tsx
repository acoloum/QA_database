import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Row, Col, Table } from 'react-bootstrap';
import {
    useExtrusionToleranceDetail,
    useAddExtrusionTolerance,
    useUpdateExtrusionTolerance,
} from '../../hooks/useExtrusionTolerance';

interface DetailRow {
    測量項目: string;
    公差下限: string;
    公差上限: string;
    標準值: string;
    單位: string;
}

const ITEMS = ['外徑', '內徑', '厚度'];

const emptyRow = (): DetailRow => ({
    測量項目: '外徑',
    公差下限: '',
    公差上限: '',
    標準值: '',
    單位: 'mm',
});

interface Props {
    show: boolean;
    editId: number | null;
    onClose: () => void;
    onSuccess: () => void;
}

const ExtrusionToleranceModal = ({ show, editId, onClose, onSuccess }: Props) => {
    const { data: detail, isLoading } = useExtrusionToleranceDetail(editId);
    const addMutation = useAddExtrusionTolerance();
    const updateMutation = useUpdateExtrusionTolerance();

    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [note, setNote] = useState('');
    const [createdAt, setCreatedAt] = useState(new Date().toISOString().split('T')[0]);
    const [rows, setRows] = useState<DetailRow[]>([emptyRow()]);

    const reset = useCallback(() => {
        setMaterial('');
        setSpec('');
        setNote('');
        setCreatedAt(new Date().toISOString().split('T')[0]);
        setRows([emptyRow()]);
    }, []);

    useEffect(() => {
        if (!show) return;
        if (!editId) { reset(); return; }
        if (!detail) return;
        const m = detail.main;
        setMaterial(m.材質);
        setSpec(m.規格 || '');
        setNote(m.備註 || '');
        setCreatedAt(m.建立日期?.split('T')[0] || new Date().toISOString().split('T')[0]);
        setRows(
            detail.details.length > 0
                ? detail.details.map((d) => ({
                      測量項目: d.測量項目,
                      公差下限: d.公差下限 != null ? String(d.公差下限) : '',
                      公差上限: d.公差上限 != null ? String(d.公差上限) : '',
                      標準值: d.標準值 != null ? String(d.標準值) : '',
                      單位: d.單位 || 'mm',
                  }))
                : [emptyRow()]
        );
    }, [show, editId, detail, reset]);

    const updateRow = (idx: number, field: keyof DetailRow, val: string) => {
        setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: val } : r)));
    };

    const handleSubmit = async () => {
        if (!material.trim()) { alert('材質為必填'); return; }
        const payload = {
            材質: material.trim(),
            規格: spec.trim() || null,
            備註: note.trim() || null,
            建立日期: createdAt,
            details: rows.map((r) => ({
                測量項目: r.測量項目,
                公差下限: r.公差下限 !== '' ? parseFloat(r.公差下限) : null,
                公差上限: r.公差上限 !== '' ? parseFloat(r.公差上限) : null,
                標準值: r.標準值 !== '' ? parseFloat(r.標準值) : null,
                單位: r.單位 || 'mm',
            })),
        };
        try {
            if (editId) {
                await updateMutation.mutateAsync({ id: editId, data: payload });
            } else {
                await addMutation.mutateAsync(payload);
            }
            onSuccess();
            onClose();
        } catch {
            // toast 由 mutation onError 處理（若有設定）
        }
    };

    return (
        <Modal show={show} onHide={onClose} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>{editId ? '編輯' : '新增'}擠壓公差</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {isLoading && editId ? (
                    <p>載入中…</p>
                ) : (
                    <>
                        <Row className="mb-2">
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>材質 <span className="text-danger">*</span></Form.Label>
                                    <Form.Control value={material} onChange={(e) => setMaterial(e.target.value)} placeholder="如 6063" />
                                </Form.Group>
                            </Col>
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>規格</Form.Label>
                                    <Form.Control value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="如 62.5*2.3（留空=通用）" />
                                </Form.Group>
                            </Col>
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>建立日期</Form.Label>
                                    <Form.Control type="date" value={createdAt} onChange={(e) => setCreatedAt(e.target.value)} />
                                </Form.Group>
                            </Col>
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>備註</Form.Label>
                                    <Form.Control value={note} onChange={(e) => setNote(e.target.value)} />
                                </Form.Group>
                            </Col>
                        </Row>

                        <Table bordered size="sm" className="mt-3">
                            <thead className="table-secondary">
                                <tr>
                                    <th style={{ minWidth: '110px' }}>測量項目</th>
                                    <th>公差下限</th>
                                    <th>公差上限</th>
                                    <th>標準值</th>
                                    <th>單位</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((r, i) => (
                                    <tr key={i}>
                                        <td>
                                            <Form.Select size="sm" value={r.測量項目} onChange={(e) => updateRow(i, '測量項目', e.target.value)}>
                                                {ITEMS.map((it) => <option key={it}>{it}</option>)}
                                            </Form.Select>
                                        </td>
                                        <td><Form.Control size="sm" type="number" value={r.公差下限} onChange={(e) => updateRow(i, '公差下限', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" value={r.公差上限} onChange={(e) => updateRow(i, '公差上限', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" value={r.標準值} onChange={(e) => updateRow(i, '標準值', e.target.value)} /></td>
                                        <td>
                                            <Form.Select size="sm" value={r.單位} onChange={(e) => updateRow(i, '單位', e.target.value)}>
                                                <option>mm</option>
                                            </Form.Select>
                                        </td>
                                        <td>
                                            <Button size="sm" variant="outline-danger" onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}>✕</Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                        <Button size="sm" variant="outline-secondary" onClick={() => setRows((prev) => [...prev, emptyRow()])}>
                            + 新增明細列
                        </Button>
                    </>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={addMutation.isPending || updateMutation.isPending}>
                    {editId ? '更新' : '新增'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ExtrusionToleranceModal;
