import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal, Form, Row, Col, Button, Table } from 'react-bootstrap';
import api from '../../services/api';
import type { Furnace, TusPoint, SatPoint } from '../../types';
import TusChart from '../../components/pyrometry/TusChart';
import TusDataTable from '../../components/pyrometry/TusDataTable';

interface Inspector { id: number; name: string; }
interface Props { editId: number | null; onClose: () => void; onSaved: () => void; }

const emptyTusPoint = (): TusPoint => ({ 點位: '', 熱電偶編號: '', 修正值: '', 最高溫: '', 最低溫: '' });
const emptySatPoint = (): SatPoint => ({ 控溫區: '', 控制儀表讀值: '', 校正測試儀表讀值: '', 修正值: '' });

const computeRangeStats = (
  數值: Record<string, number[]>,
  start: number,
  end: number,
): { 名稱: string; 最高溫: number; 最低溫: number }[] =>
  Object.keys(數值).map(ch => {
    const slice = 數值[ch].slice(start, end + 1).filter((v): v is number => v !== null && v !== undefined);
    return {
      名稱: ch,
      最高溫: slice.length ? Math.max(...slice) : 0,
      最低溫: slice.length ? Math.min(...slice) : 0,
    };
  });

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
  const [furnaceChartData, setFurnaceChartData] = useState<{ 時間: string[]; 數值: Record<string, number[]> } | null>(null);
  const [rangeStart, setRangeStart] = useState(0);
  const [rangeEnd, setRangeEnd] = useState(0);
  const [furnaceRangeStart, setFurnaceRangeStart] = useState(0);
  const [furnaceRangeEnd, setFurnaceRangeEnd] = useState(0);
  const [showDetail, setShowDetail] = useState(false);
  const [showFurnaceDetail, setShowFurnaceDetail] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [reportMeta, setReportMeta] = useState<Record<string, string>>({});

  const { data: furnaces } = useQuery({
    queryKey: ['furnaces-active'],
    queryFn: () => api.get<{ data: Furnace[] }>('/pyrometry/furnaces?active_only=1').then(r => r.data.data),
  });

  const { data: inspectors } = useQuery({
    queryKey: ['inspectors'],
    queryFn: () => api.get<{ id: number; name: string }[]>('/inspectors').then(r => r.data),
  });

  // 由使用者「主動」選爐子或切類型時，才帶出公差並重建量測點模板。
  // 不放在 useEffect：否則編輯載入或清單 refetch 時會誤觸發，把已載入/已上傳的量測點清空。
  const applyFurnaceDefaults = (fid: string, type: 'TUS' | 'SAT') => {
    const f = (furnaces || []).find(x => String(x.識別碼) === fid);
    if (!f) return;
    setTolerance(type === 'TUS' ? f.TUS允許公差 : f.SAT允許誤差);
    const n = type === 'TUS' ? f.TUS點數 : f.SAT點數;
    if (type === 'TUS') {
      setTusPoints(Array.from({ length: n }, (_, i) => ({ ...emptyTusPoint(), 點位: `P${i + 1}` })));
    } else {
      setSatPoints(Array.from({ length: n }, (_, i) => ({ ...emptySatPoint(), 控溫區: `Zone${i + 1}` })));
    }
  };

  // 若是編輯，載入既有資料
  useEffect(() => {
    if (!editId) return;
    api.get(`/pyrometry/tests/${editId}`).then(r => {
      const { main, tus_points, sat_points } = r.data;
      const cd = r.data.曲線資料;
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
      if (cd && cd.時間) {
        setChartData({ 時間: cd.時間, 數值: cd.數值 });
        if (cd.爐體數值) {
          setFurnaceChartData({ 時間: cd.爐體時間 || cd.時間, 數值: cd.爐體數值 });
          const fLen = (cd.爐體時間 || cd.時間).length;
          setFurnaceRangeStart(cd.爐體穩定開始 ?? 0);
          setFurnaceRangeEnd(cd.爐體穩定結束 ?? (fLen - 1));
        }
        setRangeStart(cd.穩定開始 ?? 0);
        setRangeEnd(cd.穩定結束 ?? (cd.時間.length - 1));
      }
      setReportMeta(r.data.報告欄位 || {});
    });
  }, [editId]);

  const updateTus = (i: number, k: keyof TusPoint, v: string) =>
    setTusPoints(prev => prev.map((p, idx) => idx === i ? { ...p, [k]: v } : p));
  const updateSat = (i: number, k: keyof SatPoint, v: string) =>
    setSatPoints(prev => prev.map((p, idx) => idx === i ? { ...p, [k]: v } : p));

  // 套用選定時間區間 → 重新計算各通道 max/min → 回填量測點
  const applyRange = () => {
    if (!chartData) return;
    const stats = computeRangeStats(chartData.數值, rangeStart, rangeEnd);
    setTusPoints(prev => prev.map((p, i) => {
      const ch = stats[i];
      if (!ch) return p;
      return { ...p, 最高溫: String(ch.最高溫), 最低溫: String(ch.最低溫) };
    }));
  };

  // 依設定溫度向後端取各點修正值（熱電偶+記錄器補正）並回填
  const applyCorrections = async (type: 'TUS' | 'SAT') => {
    const count = type === 'TUS' ? tusPoints.length : satPoints.length;
    if (!count) return;
    const r = await api.get<{ success: boolean; data: number[] }>(
      `/pyrometry/corrections?setpoint=${Number(setpoint) || 0}&type=${type}&count=${count}`,
    );
    if (r.data.success) {
      if (type === 'TUS') {
        setTusPoints(prev => prev.map((p, i) => ({ ...p, 修正值: String(r.data.data[i] ?? '') })));
      } else {
        setSatPoints(prev => prev.map((p, i) => ({ ...p, 修正值: String(r.data.data[i] ?? '') })));
      }
    }
  };

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
        const lastIdx = r.data.data.時間.length - 1;
        setFurnaceChartData({ 時間: r.data.data.時間, 數值: r.data.data.數值 });
        setFurnaceRangeStart(0);
        setFurnaceRangeEnd(lastIdx);
      } else {
        const lastIdx = r.data.data.時間.length - 1;
        setChartData({ 時間: r.data.data.時間, 數值: r.data.data.數值 });
        setRangeStart(0);
        setRangeEnd(lastIdx);
        // 初始自動回填（全範圍）
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
        曲線資料: (testType === 'TUS' && chartData) ? {
          時間: chartData.時間,
          數值: chartData.數值,
          爐體時間: furnaceChartData?.時間 || null,
          爐體數值: furnaceChartData?.數值 || null,
          穩定開始: rangeStart,
          穩定結束: rangeEnd,
          爐體穩定開始: furnaceChartData ? furnaceRangeStart : null,
          爐體穩定結束: furnaceChartData ? furnaceRangeEnd : null,
        } : null,
        報告欄位: reportMeta,
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

  const timeLabels = chartData?.時間 ?? [];

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
              <Form.Select size="sm" value={furnaceId}
                onChange={e => { setFurnaceId(e.target.value); applyFurnaceDefaults(e.target.value, testType); }}>
                <option value="">請選擇</option>
                {(furnaces || []).map(f => <option key={f.識別碼} value={f.識別碼}>{f.爐號} {f.名稱}</option>)}
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label>類型 *</Form.Label>
              <Form.Select size="sm" value={testType}
                onChange={e => { const v = e.target.value as 'TUS' | 'SAT'; setTestType(v); applyFurnaceDefaults(furnaceId, v); }}>
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

          {/* 報告表頭欄位（QRA073/074 匯出用） */}
          <div className="mb-3">
            <Button size="sm" variant="outline-secondary" className="mb-2" onClick={() => setShowReport(v => !v)}>
              {showReport ? '隱藏報告欄位' : '報告欄位（客戶/料號/核准等，QRA073/074）'}
            </Button>
            {showReport && (
              <Row className="g-2 p-2 bg-light rounded border">
                {([
                  ['客戶名稱', 3], ['工件料號', 3], ['生產批號', 3], ['內外徑尺寸', 3],
                  ['長度支數', 3], ['預估總重量', 3], ['測試條件', 3], ['控制器型號', 3],
                  ['控制器設定值', 3], ['控制器補償', 3], ['溫濕度', 3], ['執行單位', 3],
                  ['TAF編號', 3], ['核准', 3], ['製表', 3],
                ] as [string, number][]).map(([k, md]) => (
                  <Col md={md} key={k}>
                    <Form.Label className="mb-0" style={{ fontSize: 12 }}>{k}</Form.Label>
                    <Form.Control size="sm" value={reportMeta[k] || ''}
                      onChange={e => setReportMeta(prev => ({ ...prev, [k]: e.target.value }))} />
                  </Col>
                ))}
              </Row>
            )}
          </div>

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
                <>
                  <Col md={12}>
                    <TusChart
                      時間={chartData.時間}
                      數值={chartData.數值}
                      設定溫度={Number(setpoint) || 180}
                      公差={Number(tolerance) || 10}
                      startIdx={rangeStart}
                      endIdx={rangeEnd}
                      標題="測試儀器（記錄器）溫度曲線"
                    />
                  </Col>

                  {/* 時間區間選取列 */}
                  <Col md={12}>
                    <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
                      <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>
                        恆溫穩定期：
                      </span>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
                        <Form.Select
                          size="sm"
                          style={{ minWidth: 120 }}
                          value={rangeStart}
                          onChange={e => setRangeStart(Number(e.target.value))}
                        >
                          {timeLabels.map((t, i) => (
                            <option key={i} value={i}>{t}</option>
                          ))}
                        </Form.Select>
                      </div>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
                        <Form.Select
                          size="sm"
                          style={{ minWidth: 120 }}
                          value={rangeEnd}
                          onChange={e => setRangeEnd(Number(e.target.value))}
                        >
                          {timeLabels.map((t, i) => (
                            <option key={i} value={i}>{t}</option>
                          ))}
                        </Form.Select>
                      </div>
                      <Button size="sm" variant="primary" onClick={applyRange}>
                        套用並回填量測點
                      </Button>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        共 {rangeEnd >= rangeStart ? rangeEnd - rangeStart + 1 : 0} 筆
                      </span>
                    </div>
                  </Col>

                  {/* 詳細數據表 */}
                  <Col md={12}>
                    <div className="d-flex align-items-center gap-2 mb-1">
                      <Button size="sm" variant="outline-secondary" onClick={() => setShowDetail(v => !v)}>
                        {showDetail ? '隱藏詳細數據表' : '顯示詳細數據表'}
                      </Button>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        恆溫穩定期內：
                        <span style={{ background: '#f8d7da', color: '#842029', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>紅底＝超上限</span>
                        <span style={{ background: '#cfe2ff', color: '#084298', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>藍底＝低於下限</span>
                      </span>
                    </div>
                    {showDetail && (
                      <TusDataTable
                        時間={chartData.時間}
                        數值={chartData.數值}
                        設定溫度={Number(setpoint) || 180}
                        公差={Number(tolerance) || 10}
                        穩定開始={rangeStart}
                        穩定結束={rangeEnd}
                      />
                    )}
                  </Col>
                </>
              )}

              {/* 爐體曲線：獨立於記錄器資料，有上傳即顯示 */}
              {furnaceChartData && (
                <>
                  <Col md={12}>
                    <TusChart
                      時間={furnaceChartData.時間}
                      數值={furnaceChartData.數值}
                      設定溫度={Number(setpoint) || 180}
                      公差={Number(tolerance) || 10}
                      startIdx={furnaceRangeStart}
                      endIdx={furnaceRangeEnd}
                      標題="爐體記錄溫度曲線"
                    />
                  </Col>

                  {/* 爐體恆溫穩定期選取列 */}
                  <Col md={12}>
                    <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
                      <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>
                        爐體恆溫穩定期：
                      </span>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
                        <Form.Select
                          size="sm"
                          style={{ minWidth: 120 }}
                          value={furnaceRangeStart}
                          onChange={e => setFurnaceRangeStart(Number(e.target.value))}
                        >
                          {furnaceChartData.時間.map((t, i) => (
                            <option key={i} value={i}>{t}</option>
                          ))}
                        </Form.Select>
                      </div>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
                        <Form.Select
                          size="sm"
                          style={{ minWidth: 120 }}
                          value={furnaceRangeEnd}
                          onChange={e => setFurnaceRangeEnd(Number(e.target.value))}
                        >
                          {furnaceChartData.時間.map((t, i) => (
                            <option key={i} value={i}>{t}</option>
                          ))}
                        </Form.Select>
                      </div>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        共 {furnaceRangeEnd >= furnaceRangeStart ? furnaceRangeEnd - furnaceRangeStart + 1 : 0} 筆
                      </span>
                    </div>
                  </Col>

                  <Col md={12}>
                    <div className="d-flex align-items-center gap-2 mb-1">
                      <Button size="sm" variant="outline-secondary" onClick={() => setShowFurnaceDetail(v => !v)}>
                        {showFurnaceDetail ? '隱藏爐體詳細數據表' : '顯示爐體詳細數據表'}
                      </Button>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        恆溫穩定期內：
                        <span style={{ background: '#f8d7da', color: '#842029', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>紅底＝超上限</span>
                        <span style={{ background: '#cfe2ff', color: '#084298', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>藍底＝低於下限</span>
                      </span>
                    </div>
                    {showFurnaceDetail && (
                      <TusDataTable
                        時間={furnaceChartData.時間}
                        數值={furnaceChartData.數值}
                        設定溫度={Number(setpoint) || 180}
                        公差={Number(tolerance) || 10}
                        穩定開始={furnaceRangeStart}
                        穩定結束={furnaceRangeEnd}
                      />
                    )}
                  </Col>
                </>
              )}
            </Row>
          )}

          {testType === 'TUS' && tusPoints.length > 0 && (
            <>
              <div className="d-flex justify-content-between align-items-center">
                <h6 className="mb-0">TUS 量測點明細</h6>
                <Button size="sm" variant="outline-secondary" onClick={() => applyCorrections('TUS')}>
                  帶入儀器校正補正值
                </Button>
              </div>
              <div className="text-muted mb-1" style={{ fontSize: 11 }}>
                修正值＝熱電偶補正＋記錄器補正（依設定溫度內插）；校正後溫度＝量測值＋修正值
              </div>
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
              <div className="d-flex justify-content-between align-items-center">
                <h6 className="mb-0">SAT 量測點明細</h6>
                <Button size="sm" variant="outline-secondary" onClick={() => applyCorrections('SAT')}>
                  帶入儀器校正補正值
                </Button>
              </div>
              <div className="text-muted mb-1" style={{ fontSize: 11 }}>
                偏差＝（校正測試讀值＋修正值）− 控制讀值
              </div>
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
