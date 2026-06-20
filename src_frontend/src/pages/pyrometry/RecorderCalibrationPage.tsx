import { useState } from 'react';
import { Button, Card, Table, Modal, Form, Row, Col, Badge } from 'react-bootstrap';
import type { Recorder, RecorderCalPoint } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import { useDeleteRecorder, useRecorderDetail, useRecorders, useSaveRecorder } from '../../hooks/usePyrometry';

const STD_TEMPS = [100, 200, 300, 400, 500, 600];
const CHANNELS = Array.from({ length: 18 }, (_, i) => i + 1);

type Grid = Record<string, string>;   // key: `${channel}_${temp}` → 器差值字串

const cellKey = (ch: number, t: number) => `${ch}_${t}`;

const emptyMeta = () => ({
  編號: '', 校正日期: '', 到期日: '', 啟用狀態: true, 備註: '',
});

const RecorderCalibrationPage = () => {
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [meta, setMeta] = useState(emptyMeta());
  const [grid, setGrid] = useState<Grid>({});
  const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

  const { data, isLoading } = useRecorders();
  const recorderDetail = useRecorderDetail();
  const saveMutation = useSaveRecorder(editId);
  const deleteMutation = useDeleteRecorder();

  const openAdd = () => {
    setEditId(null);
    setMeta(emptyMeta());
    setGrid({});
    setShowModal(true);
  };

  const openEdit = async (r: Recorder) => {
    setEditId(r.識別碼);
    const detail = await recorderDetail.mutateAsync(r.識別碼);
    setMeta({
      編號: detail.編號 || '',
      校正日期: detail.校正日期 || '',
      到期日: detail.到期日 || '',
      啟用狀態: detail.啟用狀態,
      備註: detail.備註 || '',
    });
    const g: Grid = {};
    (detail.校正點 || []).forEach((cp: RecorderCalPoint) => {
      g[cellKey(cp.頻道, Number(cp.標準溫度))] = String(cp.器差值);
    });
    setGrid(g);
    setShowModal(true);
  };

  const handleDelete = (r: Recorder) => setConfirmAction({
    title: '刪除溫度記錄器',
    message: `確定刪除記錄器「${r.編號}」與其校正資料？`,
    confirmLabel: '刪除',
    confirmVariant: 'danger',
    onConfirm: async () => {
      await deleteMutation.mutateAsync(r.識別碼);
    },
  });

  const setCell = (ch: number, t: number, v: string) =>
    setGrid(prev => ({ ...prev, [cellKey(ch, t)]: v }));

  const handleSave = () => {
    const 校正點: RecorderCalPoint[] = [];
    CHANNELS.forEach(ch => STD_TEMPS.forEach(t => {
      const v = grid[cellKey(ch, t)];
      if (v !== undefined && v !== '') {
        校正點.push({ 頻道: ch, 標準溫度: t, 器差值: Number(v) });
      }
    }));
    saveMutation.mutate({ payload: { ...meta, 校正點 } as unknown as Partial<Recorder> }, { onSuccess: () => setShowModal(false) });
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>溫度記錄器校正</h4>
        <Button variant="primary" size="sm" onClick={openAdd}>+ 新增</Button>
      </div>
      <Card>
        <Card.Body>
          {isLoading ? <p>載入中…</p> : (
            <Table bordered hover size="sm">
              <thead className="table-secondary">
                <tr>
                  <th>編號</th><th>校正日期</th><th>到期日</th>
                  <th>狀態</th><th>操作</th>
                </tr>
              </thead>
              <tbody>
                {(data || []).map(r => (
                  <tr key={r.識別碼}>
                    <td>{r.編號}</td>
                    <td>{r.校正日期 || '—'}</td>
                    <td>{r.到期日 || '—'}</td>
                    <td>
                      <Badge bg={r.啟用狀態 ? 'success' : 'secondary'}>
                        {r.啟用狀態 ? '啟用' : '停用'}
                      </Badge>
                    </td>
                    <td>
                      <Button size="sm" variant="outline-primary" className="me-1" onClick={() => openEdit(r)}>編輯</Button>
                      <Button size="sm" variant="outline-danger" onClick={() => handleDelete(r)}>刪除</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card.Body>
      </Card>

      <Modal show={showModal} onHide={() => setShowModal(false)} size="xl">
        <Modal.Header closeButton>
          <Modal.Title>{editId ? '編輯記錄器校正' : '新增記錄器校正'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Form>
            <Row className="g-2 mb-3">
              <Col md={3}>
                <Form.Label>編號 *</Form.Label>
                <Form.Control size="sm" value={meta.編號} onChange={e => setMeta({ ...meta, 編號: e.target.value })} />
              </Col>
              <Col md={2}>
                <Form.Label>校正日期</Form.Label>
                <Form.Control size="sm" type="date" value={meta.校正日期} onChange={e => setMeta({ ...meta, 校正日期: e.target.value })} />
              </Col>
              <Col md={2}>
                <Form.Label>到期日</Form.Label>
                <Form.Control size="sm" type="date" value={meta.到期日} onChange={e => setMeta({ ...meta, 到期日: e.target.value })} />
              </Col>
              <Col md={3} className="d-flex align-items-end">
                <Form.Check type="checkbox" label="啟用" checked={meta.啟用狀態} onChange={e => setMeta({ ...meta, 啟用狀態: e.target.checked })} />
              </Col>
              <Col md={12}>
                <Form.Label>備註</Form.Label>
                <Form.Control as="textarea" rows={1} size="sm" value={meta.備註} onChange={e => setMeta({ ...meta, 備註: e.target.value })} />
              </Col>
            </Row>

            <h6>各頻道器差值（器示值 − 標準值，°C）</h6>
            <div style={{ maxHeight: 360, overflow: 'auto' }}>
              <Table bordered size="sm" className="text-center align-middle">
                <thead className="table-secondary" style={{ position: 'sticky', top: 0 }}>
                  <tr>
                    <th>頻道＼標準溫度</th>
                    {STD_TEMPS.map(t => <th key={t}>{t}°C</th>)}
                  </tr>
                </thead>
                <tbody>
                  {CHANNELS.map(ch => (
                    <tr key={ch}>
                      <td className="table-secondary">CH{ch}</td>
                      {STD_TEMPS.map(t => (
                        <td key={t} style={{ padding: 2 }}>
                          <Form.Control
                            size="sm"
                            style={{ minWidth: 64, textAlign: 'center' }}
                            value={grid[cellKey(ch, t)] ?? ''}
                            onChange={e => setCell(ch, t, e.target.value)}
                          />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
          <Button variant="primary" onClick={handleSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? '儲存中…' : '儲存'}
          </Button>
        </Modal.Footer>
      </Modal>
      <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
    </div>
  );
};

export default RecorderCalibrationPage;
