import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Table, Modal, Form, Row, Col, Badge } from 'react-bootstrap';
import api from '../../services/api';
import type { Thermocouple, ThermocoupleCalPoint } from '../../types';

interface PointRow { 標準溫度: string; 器差值: string; }

const emptyMeta = () => ({
  編號: '', 型式: 'TYPE K', 校正日期: '', 到期日: '', 啟用狀態: true, 備註: '',
});

const ThermocoupleCalibrationPage = () => {
  const qc = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [meta, setMeta] = useState(emptyMeta());
  const [points, setPoints] = useState<PointRow[]>([{ 標準溫度: '', 器差值: '' }]);
  const [msg, setMsg] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['thermocouples'],
    queryFn: () => api.get<{ data: Thermocouple[] }>('/pyrometry/thermocouples').then(r => r.data.data),
  });

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<Thermocouple>) =>
      editId
        ? api.put(`/pyrometry/thermocouples/${editId}`, payload)
        : api.post('/pyrometry/thermocouples', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['thermocouples'] });
      setShowModal(false);
      setMsg(editId ? '已更新' : '已新增');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/pyrometry/thermocouples/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['thermocouples'] }),
  });

  const openAdd = () => {
    setEditId(null);
    setMeta(emptyMeta());
    setPoints([{ 標準溫度: '', 器差值: '' }]);
    setShowModal(true);
  };

  const openEdit = async (t: Thermocouple) => {
    setEditId(t.識別碼);
    const d = await api.get<{ data: Thermocouple }>(`/pyrometry/thermocouples/${t.識別碼}`).then(res => res.data.data);
    setMeta({
      編號: d.編號 || '', 型式: d.型式 || '',
      校正日期: d.校正日期 || '', 到期日: d.到期日 || '',
      啟用狀態: d.啟用狀態, 備註: d.備註 || '',
    });
    const rows = (d.校正點 || []).map((cp: ThermocoupleCalPoint) => ({
      標準溫度: String(cp.標準溫度), 器差值: String(cp.器差值),
    }));
    setPoints(rows.length ? rows : [{ 標準溫度: '', 器差值: '' }]);
    setShowModal(true);
  };

  const handleDelete = (id: number) => {
    if (!window.confirm('確定刪除此熱電偶與其校正資料？')) return;
    deleteMutation.mutate(id);
  };

  const setRow = (i: number, k: keyof PointRow, v: string) =>
    setPoints(prev => prev.map((p, idx) => idx === i ? { ...p, [k]: v } : p));
  const addRow = () => setPoints(prev => [...prev, { 標準溫度: '', 器差值: '' }]);
  const delRow = (i: number) => setPoints(prev => prev.filter((_, idx) => idx !== i));

  const handleSave = () => {
    const 校正點 = points
      .filter(p => p.標準溫度 !== '' && p.器差值 !== '')
      .map(p => ({ 標準溫度: Number(p.標準溫度), 器差值: Number(p.器差值) }));
    saveMutation.mutate({ ...meta, 校正點 } as unknown as Partial<Thermocouple>);
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>熱電偶校正</h4>
        <Button variant="primary" size="sm" onClick={openAdd}>+ 新增</Button>
      </div>
      {msg && <div className="alert alert-success py-1">{msg}</div>}

      <Card>
        <Card.Body>
          {isLoading ? <p>載入中…</p> : (
            <Table bordered hover size="sm">
              <thead className="table-secondary">
                <tr>
                  <th>編號</th><th>型式</th><th>校正日期</th><th>到期日</th>
                  <th>校正點數</th><th>狀態</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                {(data || []).map(t => (
                  <tr key={t.識別碼}>
                    <td>{t.編號}</td>
                    <td>{t.型式}</td>
                    <td>{t.校正日期 || '—'}</td>
                    <td>{t.到期日 || '—'}</td>
                    <td>{t.校正點?.length ?? '—'}</td>
                    <td>
                      <Badge bg={t.啟用狀態 ? 'success' : 'secondary'}>
                        {t.啟用狀態 ? '啟用' : '停用'}
                      </Badge>
                    </td>
                    <td>
                      <Button size="sm" variant="outline-primary" className="me-1" onClick={() => openEdit(t)}>編輯</Button>
                      <Button size="sm" variant="outline-danger" onClick={() => handleDelete(t.識別碼)}>刪除</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      <Modal show={showModal} onHide={() => setShowModal(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>{editId ? '編輯熱電偶校正' : '新增熱電偶校正'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Row className="g-2 mb-3">
              <Col md={3}>
                <Form.Label>編號 *</Form.Label>
                <Form.Control size="sm" value={meta.編號} onChange={e => setMeta({ ...meta, 編號: e.target.value })} />
              </Col>
              <Col md={2}>
                <Form.Label>型式</Form.Label>
                <Form.Control size="sm" value={meta.型式} onChange={e => setMeta({ ...meta, 型式: e.target.value })} />
              </Col>
              <Col md={3}>
                <Form.Label>校正日期</Form.Label>
                <Form.Control size="sm" type="date" value={meta.校正日期} onChange={e => setMeta({ ...meta, 校正日期: e.target.value })} />
              </Col>
              <Col md={3}>
                <Form.Label>到期日</Form.Label>
                <Form.Control size="sm" type="date" value={meta.到期日} onChange={e => setMeta({ ...meta, 到期日: e.target.value })} />
              </Col>
              <Col md={1} className="d-flex align-items-end">
                <Form.Check type="checkbox" label="啟用" checked={meta.啟用狀態} onChange={e => setMeta({ ...meta, 啟用狀態: e.target.checked })} />
              </Col>
              <Col md={12}>
                <Form.Label>備註</Form.Label>
                <Form.Control as="textarea" rows={1} size="sm" value={meta.備註} onChange={e => setMeta({ ...meta, 備註: e.target.value })} />
              </Col>
            </Row>

            <div className="d-flex justify-content-between align-items-center">
              <h6 className="mb-0">校正曲線（標準溫度 → 器差值＝器示值−標準值）</h6>
              <Button size="sm" variant="outline-secondary" onClick={addRow}>+ 新增一列</Button>
            </div>
            <div className="text-muted mb-1" style={{ fontSize: 11 }}>
              補正值＝−器差值（依設定溫度於各點間線性內插）
            </div>
            <Table bordered size="sm" style={{ maxWidth: 420 }}>
              <thead className="table-secondary">
                <tr><th>標準溫度(°C)</th><th>器差值(°C)</th><th></th></tr>
              </thead>
              <tbody>
                {points.map((p, i) => (
                  <tr key={i}>
                    <td><Form.Control size="sm" value={p.標準溫度} onChange={e => setRow(i, '標準溫度', e.target.value)} /></td>
                    <td><Form.Control size="sm" value={p.器差值} onChange={e => setRow(i, '器差值', e.target.value)} /></td>
                    <td className="text-center">
                      <Button size="sm" variant="outline-danger" onClick={() => delRow(i)} disabled={points.length <= 1}>✕</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
          <Button variant="primary" onClick={handleSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? '儲存中…' : '儲存'}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default ThermocoupleCalibrationPage;
