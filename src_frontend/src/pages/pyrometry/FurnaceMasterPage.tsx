import { useState } from 'react';
import { Button, Card, Table, Modal, Form, Row, Col, Badge } from 'react-bootstrap';
import toast from 'react-hot-toast';
import type { Furnace } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import { useDeleteFurnace, useFurnaces, useFurnaceTusTrend, useSaveFurnace } from '../../hooks/usePyrometry';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { buildFurnacePayload, type FurnaceFormState } from './furnaceFormPayload';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const PROCESS_TYPES = ['T6時效', 'T4', '退火'];

const emptyForm = (): FurnaceFormState => ({
  爐號: '', 名稱: '', 製程類型: '', TUS點數: 12, SAT點數: 2,
  TUS頻率_月: 3, SAT頻率_月: 3, TUS允許公差: '', SAT允許誤差: '',
  有效加熱區尺寸: '', 儀器型式: '', CQI9等級: '', 啟用狀態: true, 備註: '',
});

const FurnaceMasterPage = () => {
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FurnaceFormState>(emptyForm());
  const [showTrend, setShowTrend] = useState(false);
  const [trendFurnaceId, setTrendFurnaceId] = useState<number | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

  const { data, isLoading } = useFurnaces();
  const { data: trendData } = useFurnaceTusTrend(trendFurnaceId);
  const saveMutation = useSaveFurnace(editId);
  const deleteMutation = useDeleteFurnace();

  const openAdd = () => { setEditId(null); setForm(emptyForm()); setShowModal(true); };
  const openEdit = (f: Furnace) => { setEditId(f.識別碼); setForm({ ...f }); setShowModal(true); };
  const handleDelete = (f: Furnace) => setConfirmAction({
    title: '刪除爐子設備',
    message: `確定刪除「${f.爐號} ${f.名稱}」？此操作會連同設備設定移除。`,
    confirmLabel: '刪除',
    confirmVariant: 'danger',
    onConfirm: async () => {
      await deleteMutation.mutateAsync(f.識別碼);
    },
  });
  const set = (k: keyof FurnaceFormState, v: unknown) => setForm(prev => ({ ...prev, [k]: v }));
  const handleSave = () => {
    try {
      saveMutation.mutate({ payload: buildFurnacePayload(form) }, { onSuccess: () => setShowModal(false) });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '爐子設備資料格式不正確');
    }
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h4>爐子設備主檔</h4>
        <Button variant="primary" size="sm" onClick={openAdd}>+ 新增</Button>
      </div>
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
                      <Button size="sm" variant="outline-danger" onClick={() => handleDelete(f)}>刪除</Button>
                      <Button size="sm" variant="outline-info" className="ms-1"
                        onClick={() => { setTrendFurnaceId(f.識別碼); setShowTrend(true); }}>趨勢</Button>
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
                <Form.Control size="sm" type="number" value={form.TUS點數 ?? ''} onChange={e => set('TUS點數', e.target.value)} />
              </Col>
              <Col md={3}>
                <Form.Label>SAT點數</Form.Label>
                <Form.Control size="sm" type="number" value={form.SAT點數 ?? ''} onChange={e => set('SAT點數', e.target.value)} />
              </Col>
              <Col md={3}>
                <Form.Label>TUS頻率(月)</Form.Label>
                <Form.Control size="sm" type="number" value={form.TUS頻率_月 ?? ''} onChange={e => set('TUS頻率_月', e.target.value)} />
              </Col>
              <Col md={3}>
                <Form.Label>SAT頻率(月)</Form.Label>
                <Form.Control size="sm" type="number" value={form.SAT頻率_月 ?? ''} onChange={e => set('SAT頻率_月', e.target.value)} />
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
          <Button
            variant="primary"
            onClick={handleSave}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? '儲存中…' : '儲存'}
          </Button>
        </Modal.Footer>
      </Modal>
      <Modal show={showTrend} onHide={() => setShowTrend(false)} size="lg">
        <Modal.Header closeButton>
          <Modal.Title>歷年 TUS 趨勢</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {trendData && trendData.length > 0 ? (
            <Line
              data={{
                labels: trendData.map(t => t.測試日期),
                datasets: [
                  { label: '均勻度極差', data: trendData.map(t => Number(t.均勻度極差) || 0), borderColor: '#e6194b', tension: 0.3 },
                  { label: '最大正偏差', data: trendData.map(t => Number(t.最大正偏差) || 0), borderColor: '#3cb44b', tension: 0.3 },
                  { label: '最大負偏差', data: trendData.map(t => Number(t.最大負偏差) || 0), borderColor: '#4363d8', tension: 0.3 },
                ],
              }}
              options={{
                responsive: true,
                plugins: { legend: { position: 'bottom' as const }, title: { display: true, text: 'TUS 歷年趨勢（°C）' } },
              }}
            />
          ) : <p className="text-muted">尚無 TUS 測試紀錄。</p>}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowTrend(false)}>關閉</Button>
        </Modal.Footer>
      </Modal>
      <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
    </div>
  );
};

export default FurnaceMasterPage;
