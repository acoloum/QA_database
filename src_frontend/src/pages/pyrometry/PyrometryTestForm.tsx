import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal, Form, Row, Col, Button, Table } from 'react-bootstrap';
import api from '../../services/api';
import type { Furnace, TusPoint, SatPoint } from '../../types';
import TusChart from '../../components/pyrometry/TusChart';

interface Inspector { id: number; name: string; }
interface Props { editId: number | null; onClose: () => void; onSaved: () => void; }

const emptyTusPoint = (): TusPoint => ({ 點位: '', 熱電偶編號: '', 修正值: '', 最高溫: '', 最低溫: '' });
const emptySatPoint = (): SatPoint => ({ 控溫區: '', 控制儀表讀值: '', 校正測試儀表讀值: '', 修正值: '' });

const PyrometryTestForm = ({ editId, onClose, onSaved }: Props) => {
  const [furnaceId, setFurnaceId] = useState('');
  const [testType, setTestType] = useState<'TUS' | 'SAT'>('TUS');
  const [testDate, setTestDate] = useState('');
  const [setpoint, setSetpoint] = useState('');
  const [tolerance, setTolerance] = useState('');
  const [testerId, setTesterId] = useState('');
  const [testInstrument, setTestInstrument] = useState('');
  const [stdInstrument, setStdInstrument] = useState('');
  const [calDueDate, setCalDueDate] = useState('');
  const [note, setNote] = useState('');
  const [tusPoints, setTusPoints] = useState<TusPoint[]>([]);
  const [satPoints, setSatPoints] = useState<SatPoint[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [chartData, setChartData] = useState<{ 時間: string[]; 數值: Record<string, number[]> } | null>(null);
  const [furnaceChartData, setFurnaceChartData] = useState<{ 數值: Record<string, number[]> } | null>(null);

  const { data: furnaces } = useQuery({
    queryKey: ['furnaces-active'],
    queryFn: () => api.get<{ data: Furnace[] }>('/pyrometry/furnaces?active_only=1').then(r => r.data.data),
  });

  const { data: inspectors } = useQuery({
    queryKey: ['inspectors'],
    queryFn: () => api.get<{ id: number; name: string }[]>('/inspectors').then(r => r.data),
  });

  const selectedFurnace = (furnaces || []).find(f => String(f.識別碼) === furnaceId);

  // 選爐子或類型後自動帶公差與點數
  useEffect(() => {
    if (!selectedFurnace) return;
    setTolerance(testType === 'TUS' ? selectedFurnace.TUS允許公差 : selectedFurnace.SAT允許誤差);
    const n = testType === 'TUS' ? selectedFurnace.TUS點數 : selectedFurnace.SAT點數;
    if (testType === 'TUS') {
      setTusPoints(Array.from({ length: n }, (_, i) => ({ ...emptyTusPoint(), 點位: `P${i + 1}` })));
    } else {
      setSatPoints(Array.from({ length: n }, (_, i) => ({ ...emptySatPoint(), 控溫區: `Zone${i + 1}` })));
    }
  }, [furnaceId, testType]);

  // 若是編輯，載入既有資料
  useEffect(() => {
    if (!editId) return;
    api.get(`/pyrometry/tests/${editId}`).then(r => {
      const { main, tus_points, sat_points } = r.data;
      setFurnaceId(String(main.爐子ID));
      setTestType(main.測試類型);
      setTestDate(main.測試日期);
      setSetpoint(main.設定溫度);
      setTolerance(main.允許公差);
      setTesterId(main.測試人員 ? String(main.測試人員) : '');
      setTestInstrument(main.測試儀器編號);
      setStdInstrument(main.標準校正儀器編號);
      setCalDueDate(main.儀器校正到期日 || '');
      setNote(main.備註);
      setTusPoints(tus_points);
      setSatPoints(sat_points);
    });
  }, [editId]);

  const updateTus = (i: number, k: keyof TusPoint, v: string) =>
    setTusPoints(prev => prev.map((p, idx) => idx === i ? { ...p, [k]: v } : p));
  const updateSat = (i: number, k: keyof SatPoint, v: string) =>
    setSatPoints(prev => prev.map((p, idx) => idx === i ? { ...p, [k]: v } : p));

  const handleFileUpload = async (file: File, isFurnaceData: boolean) => {
    const formData = new FormData();
    formData.append('file', file);
    const r = await api.post<{
      success: boolean;
      data: {
        時間: string[];
        通道: { 名稱: string; 最高溫: number; 最低溫: number }[];
        數值: Record<string, number[]>;
      };
    }>('/pyrometry/parse-data', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
    if (r.data.success) {
      if (isFurnaceData) {
        setFurnaceChartData({ 數值: r.data.data.數值 });
      } else {
        setChartData({ 時間: r.data.data.時間, 數值: r.data.data.數值 });
        // 自動回填 TUS 量測點（依通道順序對應 P1..Pn）
        if (testType === 'TUS') {
          setTusPoints(prev => prev.map((p, i) => {
            const ch = r.data.data.通道[i];
            if (!ch) return p;
            return { ...p, 最高溫: String(ch.最高溫), 最低溫: String(ch.最低溫) };
          }));
        }
      }
    }
  };

  const handleSave = async () => {
    setSaving(true); setError('');
    try {
      const payload = {
        爐子ID: Number(furnaceId), 測試類型: testType,
        測試日期: testDate, 設定溫度: setpoint, 允許公差: tolerance,
        測試人員: testerId ? Number(testerId) : null,
        測試儀器編號: testInstrument, 標準校正儀器編號: stdInstrument,
        儀器校正到期日: calDueDate || null, 備註: note,
        points: testType === 'TUS' ? tusPoints : satPoints,
      };
      if (editId) {
        await api.put(`/pyrometry/tests/${editId}`, payload);
      } else {
        await api.post('/pyrometry/tests', payload);
      }
      onSaved();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '儲存失敗';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal show onHide={onClose} size="xl">
      <Modal.Header closeButton>
        <Modal.Title>{editId ? '編輯爐溫測試' : '新增爐溫測試'}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {error && <div className="alert alert-danger py-1">{error}</div>}
        <Form>
          <Row className="g-2 mb-3">
            <Col md={3}>
              <Form.Label>爐子 *</Form.Label>
              <Form.Select size="sm" value={furnaceId} onChange={e => setFurnaceId(e.target.value)}>
                <option value="">請選擇</option>
                {(furnaces || []).map(f => <option key={f.識別碼} value={f.識別碼}>{f.爐號} {f.名稱}</option>)}
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label>類型 *</Form.Label>
              <Form.Select size="sm" value={testType} onChange={e => setTestType(e.target.value as 'TUS' | 'SAT')}>
                <option value="TUS">TUS</option>
                <option value="SAT">SAT</option>
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label>測試日期 *</Form.Label>
              <Form.Control size="sm" type="date" value={testDate} onChange={e => setTestDate(e.target.value)} />
            </Col>
            <Col md={2}>
              <Form.Label>設定溫度(°C) *</Form.Label>
              <Form.Control size="sm" value={setpoint} onChange={e => setSetpoint(e.target.value)} />
            </Col>
            <Col md={2}>
              <Form.Label>允許公差(±°C)</Form.Label>
              <Form.Control size="sm" value={tolerance} onChange={e => setTolerance(e.target.value)} />
            </Col>
            <Col md={3}>
              <Form.Label>測試人員</Form.Label>
              <Form.Select size="sm" value={testerId} onChange={e => setTesterId(e.target.value)}>
                <option value="">請選擇</option>
                {(inspectors || []).map((i: Inspector) => <option key={i.id} value={i.id}>{i.name}</option>)}
              </Form.Select>
            </Col>
            <Col md={3}>
              <Form.Label>測試儀器編號</Form.Label>
              <Form.Control size="sm" value={testInstrument} onChange={e => setTestInstrument(e.target.value)} />
            </Col>
            <Col md={3}>
              <Form.Label>標準校正儀器編號</Form.Label>
              <Form.Control size="sm" value={stdInstrument} onChange={e => setStdInstrument(e.target.value)} />
            </Col>
            <Col md={2}>
              <Form.Label>儀器校正到期日</Form.Label>
              <Form.Control size="sm" type="date" value={calDueDate} onChange={e => setCalDueDate(e.target.value)} />
            </Col>
            <Col md={12}>
              <Form.Label>備註</Form.Label>
              <Form.Control as="textarea" rows={2} size="sm" value={note} onChange={e => setNote(e.target.value)} />
            </Col>
          </Row>

          {testType === 'TUS' && (
            <Row className="g-2 mb-3">
              <Col md={6}>
                <Form.Label>測試儀器數據（基準，CSV/Excel）</Form.Label>
                <input className="form-control form-control-sm" type="file" accept=".csv,.xlsx,.xls"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f, false); }} />
              </Col>
              <Col md={6}>
                <Form.Label>爐體記錄數據（對照，選配）</Form.Label>
                <input className="form-control form-control-sm" type="file" accept=".csv,.xlsx,.xls"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f, true); }} />
              </Col>
              {chartData && (
                <Col md={12}>
                  <TusChart
                    時間={chartData.時間}
                    數值={chartData.數值}
                    爐體數值={furnaceChartData?.數值}
                    設定溫度={Number(setpoint) || 180}
                    公差={Number(tolerance) || 10}
                  />
                </Col>
              )}
            </Row>
          )}

          {testType === 'TUS' && tusPoints.length > 0 && (
            <>
              <h6>TUS 量測點明細</h6>
              <Table bordered size="sm">
                <thead className="table-secondary">
                  <tr><th>點位</th><th>熱電偶編號</th><th>修正值</th><th>最高溫</th><th>最低溫</th></tr>
                </thead>
                <tbody>
                  {tusPoints.map((p, i) => (
                    <tr key={i}>
                      <td><Form.Control size="sm" value={p.點位} onChange={e => updateTus(i, '點位', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={p.熱電偶編號} onChange={e => updateTus(i, '熱電偶編號', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.修正值 ?? '')} onChange={e => updateTus(i, '修正值', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.最高溫 ?? '')} onChange={e => updateTus(i, '最高溫', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.最低溫 ?? '')} onChange={e => updateTus(i, '最低溫', e.target.value)} /></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </>
          )}

          {testType === 'SAT' && satPoints.length > 0 && (
            <>
              <h6>SAT 量測點明細</h6>
              <Table bordered size="sm">
                <thead className="table-secondary">
                  <tr><th>控溫區</th><th>控制儀表讀值</th><th>校正測試儀表讀值</th><th>修正值</th></tr>
                </thead>
                <tbody>
                  {satPoints.map((p, i) => (
                    <tr key={i}>
                      <td><Form.Control size="sm" value={p.控溫區} onChange={e => updateSat(i, '控溫區', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.控制儀表讀值 ?? '')} onChange={e => updateSat(i, '控制儀表讀值', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.校正測試儀表讀值 ?? '')} onChange={e => updateSat(i, '校正測試儀表讀值', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.修正值 ?? '')} onChange={e => updateSat(i, '修正值', e.target.value)} /></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </>
          )}
        </Form>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onClose}>取消</Button>
        <Button variant="primary" onClick={handleSave} disabled={saving}>
          {saving ? '儲存中…' : '儲存'}
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default PyrometryTestForm;
