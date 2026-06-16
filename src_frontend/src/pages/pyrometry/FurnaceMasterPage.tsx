import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Table, Modal, Form, Row, Col, Badge } from 'react-bootstrap';
import api from '../../services/api';
import type { Furnace } from '../../types';

const PROCESS_TYPES = ['T6時效', 'T4', '退火'];

const emptyForm = (): Partial<Furnace> => ({
  爐號: '', 名稱: '', 製程類型: '', TUS點數: 12, SAT點數: 2,
  TUS頻率_月: 3, SAT頻率_月: 3, TUS允許公差: '', SAT允許誤差: '',
  有效加熱區尺寸: '', 儀器型式: '', CQI9等級: '', 啟用狀態: true, 備註: '',
});

const FurnaceMasterPage = () => {
  const qc = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<Partial<Furnace>>(emptyForm());
  const [msg, setMsg] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['furnaces'],
    queryFn: () => api.get<{ data: Furnace[] }>('/pyrometry/furnaces').then(r => r.data.data),
  });

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<Furnace>) =>
      editId
        ? api.put(`/pyrometry/furnaces/${editId}`, payload)
        : api.post('/pyrometry/furnaces', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['furnaces'] });
      setShowModal(false);
      setMsg(editId ? '已更新' : '已新增');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/pyrometry/furnaces/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['furnaces'] }),
  });

  const openAdd = () => { setEditId(null); setForm(emptyForm()); setShowModal(true); };
  const openEdit = (f: Furnace) => { setEditId(f.識別碼); setForm({ ...f }); setShowModal(true); };
  const handleDelete = (id: number) => {
    if (!window.confirm('確定刪除此爐子設備？')) return;
    deleteMutation.mutate(id);
  };
  const set = (k: keyof Furnace, v: unknown) => setForm(prev => ({ ...prev, [k]: v }));

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>爐子設備主檔</h4>
        <Button variant="primary" size="sm" onClick={openAdd}>+ 新增</Button>
      </div>
      {msg && <div className="alert alert-success py-1">{msg}</div>}

      <Card>
        <Card.Body>
          {isLoading ? <p>載入中…</p> : (
            <Table bordered hover size="sm">
              <thead className="table-secondary">
                <tr>
                  <th>爐號</th><th>名稱</th><th>製程類型</th>
                  <th>TUS點數</th><th>SAT點數</th>
                  <th>TUS公差(±°C)</th><th>SAT誤差(±°C)</th>
                  <th>狀態</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                {(data || []).map(f => (
                  <tr key={f.識別碼}>
                    <td>{f.爐號}</td>
                    <td>{f.名稱}</td>
                    <td>{f.製程類型}</td>
                    <td>{f.TUS點數}</td>
                    <td>{f.SAT點數}</td>
                    <td>{f.TUS允許公差}</td>
                    <td>{f.SAT允許誤差}</td>
                    <td>
                      <Badge bg={f.啟用狀態 ? 'success' : 'secondary'}>
                        {f.啟用狀態 ? '啟用' : '停用'}
                      </Badge>
                    </td>
                    <td>
                      <Button size="sm" variant="outline-primary" className="me-1" onClick={() => openEdit(f)}>編輯</Button>
                      <Button size="sm" variant="outline-danger" onClick={() => handleDelete(f.識別碼)}>刪除</Button>
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
          <Modal.Title>{editId ? '編輯爐子設備' : '新增爐子設備'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Row className="g-2">
              <Col md={3}>
                <Form.Label>爐號 *</Form.Label>
                <Form.Control size="sm" value={form.爐號 || ''} onChange={e => set('爐號', e.target.value)} />
              </Col>
              <Col md={5}>
                <Form.Label>名稱 *</Form.Label>
                <Form.Control size="sm" value={form.名稱 || ''} onChange={e => set('名稱', e.target.value)} />
              </Col>
              <Col md={4}>
                <Form.Label>製程類型</Form.Label>
                <Form.Select size="sm" value={form.製程類型 || ''} onChange={e => set('製程類型', e.target.value)}>
                  <option value="">請選擇</option>
                  {PROCESS_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </Form.Select>
              </Col>
              <Col md={3}>
                <Form.Label>TUS點數</Form.Label>
                <Form.Control size="sm" type="number" value={form.TUS點數 ?? 12} onChange={e => set('TUS點數', Number(e.target.value))} />
              </Col>
              <Col md={3}>
                <Form.Label>SAT點數</Form.Label>
                <Form.Control size="sm" type="number" value={form.SAT點數 ?? 2} onChange={e => set('SAT點數', Number(e.target.value))} />
              </Col>
              <Col md={3}>
                <Form.Label>TUS頻率(月)</Form.Label>
                <Form.Control size="sm" type="number" value={form.TUS頻率_月 ?? 3} onChange={e => set('TUS頻率_月', Number(e.target.value))} />
              </Col>
              <Col md={3}>
                <Form.Label>SAT頻率(月)</Form.Label>
                <Form.Control size="sm" type="number" value={form.SAT頻率_月 ?? 3} onChange={e => set('SAT頻率_月', Number(e.target.value))} />
              </Col>
              <Col md={3}>
                <Form.Label>TUS允許公差(±°C)</Form.Label>
                <Form.Control size="sm" value={form.TUS允許公差 || ''} onChange={e => set('TUS允許公差', e.target.value)} />
              </Col>
              <Col md={3}>
                <Form.Label>SAT允許誤差(±°C)</Form.Label>
                <Form.Control size="sm" value={form.SAT允許誤差 || ''} onChange={e => set('SAT允許誤差', e.target.value)} />
              </Col>
              <Col md={6}>
                <Form.Label>有效加熱區尺寸</Form.Label>
                <Form.Control size="sm" value={form.有效加熱區尺寸 || ''} onChange={e => set('有效加熱區尺寸', e.target.value)} />
              </Col>
              <Col md={3}>
                <Form.Label>儀器型式</Form.Label>
                <Form.Control size="sm" value={form.儀器型式 || ''} onChange={e => set('儀器型式', e.target.value)} />
              </Col>
              <Col md={3}>
                <Form.Label>CQI-9等級</Form.Label>
                <Form.Control size="sm" value={form.CQI9等級 || ''} onChange={e => set('CQI9等級', e.target.value)} />
              </Col>
              <Col md={12}>
                <Form.Label>備註</Form.Label>
                <Form.Control as="textarea" rows={2} size="sm" value={form.備註 || ''} onChange={e => set('備註', e.target.value)} />
              </Col>
              <Col md={3}>
                <Form.Check type="checkbox" label="啟用" checked={!!form.啟用狀態} onChange={e => set('啟用狀態', e.target.checked)} />
              </Col>
            </Row>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
          <Button variant="primary" onClick={() => saveMutation.mutate(form)} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? '儲存中…' : '儲存'}
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default FurnaceMasterPage;
