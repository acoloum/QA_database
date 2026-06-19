import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Modal, Form, Row, Col, Button, Table, Nav } from 'react-bootstrap';
import api from '../../services/api';
import type { Furnace, TusPoint, SatPoint, SatReading } from '../../types';
import TusChart from '../../components/pyrometry/TusChart';
import TusDataTable from '../../components/pyrometry/TusDataTable';
import {
  computeRangeStats,
  emptyItemRow,
  emptyReading,
  emptySatPoint,
  emptyTusPoint,
  splitReportFields,
  type ChartData,
  type ItemRow,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';

interface Inspector { id: number; name: string; }
interface Props { editId: number | null; onClose: () => void; onSaved: () => void; }

/** 單一控溫區的讀值表格（含新增/刪除列） */
const ZoneTab = ({
  point, tolerance, onUpdateField, onUpdateReading, onAddReading, onRemoveReading,
}: {
  point: SatPoint;
  tolerance: string;
  onUpdateField: (k: keyof SatPoint, v: string) => void;
  onUpdateReading: (ri: number, k: keyof SatReading, v: string) => void;
  onAddReading: () => void;
  onRemoveReading: (ri: number) => void;
}) => {
  const tol = parseFloat(String(tolerance)) || 0;
  const corr = parseFloat(String(point.修正值 ?? 0)) || 0;

  const validReadings = point.readings.filter(
    r => r.校正測試讀值 !== '' && r.校正測試讀值 !== null,
  );
  const passCount = validReadings.filter(r => {
    const ctrl = parseFloat(String(r.控制儀表讀值));
    const test = parseFloat(String(r.校正測試讀值));
    if (isNaN(ctrl) || isNaN(test)) return false;
    const dev = Math.round((test - ctrl + corr) * 100) / 100;
    return Math.abs(dev) <= tol;
  }).length;

  return (
    <>
      <Row className="g-2 mb-2 align-items-end">
        <Col md={3}>
          <Form.Label className="mb-0" style={{ fontSize: 12 }}>控溫區名稱</Form.Label>
          <Form.Control size="sm" value={point.控溫區}
            onChange={e => onUpdateField('控溫區', e.target.value)} />
        </Col>
        <Col md={1}>
          <Form.Label className="mb-0" style={{ fontSize: 12 }}>頻道</Form.Label>
          <Form.Control size="sm" type="number" min={1} max={99}
            value={point.頻道 ?? ''}
            onChange={e => onUpdateField('頻道', e.target.value)} />
        </Col>
        <Col md={2}>
          <Form.Label className="mb-0" style={{ fontSize: 12 }}>修正值 (°C)</Form.Label>
          <Form.Control size="sm" value={String(point.修正值 ?? '')}
            onChange={e => onUpdateField('修正值', e.target.value)} />
        </Col>
        <Col md="auto">
          <Button size="sm" variant="outline-success" onClick={onAddReading}>＋ 新增讀值</Button>
        </Col>
        <Col md="auto" className="ms-auto text-end">
          <span className="text-muted" style={{ fontSize: 12 }}>
            有效讀值 {validReadings.length} 筆，合格 {passCount} / {validReadings.length}
          </span>
        </Col>
      </Row>

      <Table bordered size="sm" className="text-center align-middle">
        <thead className="table-secondary">
          <tr>
            <th style={{ width: 36 }}>#</th>
            <th>控制儀表讀值</th>
            <th>校正測試讀值</th>
            <th style={{ minWidth: 50 }}>差值</th>
            <th style={{ minWidth: 50 }}>偏差</th>
            <th style={{ width: 42 }}>合格</th>
            <th style={{ width: 36 }}></th>
          </tr>
        </thead>
        <tbody>
          {point.readings.map((r, ri) => {
            const ctrl = parseFloat(String(r.控制儀表讀值));
            const test = parseFloat(String(r.校正測試讀值));
            const diff = (!isNaN(ctrl) && !isNaN(test)) ? Math.round((test - ctrl) * 100) / 100 : null;
            const dev  = diff !== null ? Math.round((diff + corr) * 100) / 100 : null;
            const pass = dev !== null ? Math.abs(dev) <= tol : null;
            const devColor = dev === null ? undefined : Math.abs(dev) > tol ? '#842029' : '#0a3622';
            return (
              <tr key={ri} style={pass === false ? { background: '#fff5f5' } : undefined}>
                <td className="text-muted" style={{ fontSize: 11 }}>{ri + 1}</td>
                <td>
                  <Form.Control size="sm" value={String(r.控制儀表讀值 ?? '')}
                    onChange={e => onUpdateReading(ri, '控制儀表讀值', e.target.value)} />
                </td>
                <td>
                  <Form.Control size="sm" value={String(r.校正測試讀值 ?? '')}
                    onChange={e => onUpdateReading(ri, '校正測試讀值', e.target.value)} />
                </td>
                <td className="text-muted">{diff ?? '—'}</td>
                <td style={{ fontWeight: dev !== null ? 600 : undefined, color: devColor }}>
                  {dev ?? '—'}
                </td>
                <td>
                  {pass === null ? '—' : pass
                    ? <span style={{ color: '#198754', fontWeight: 700 }}>✓</span>
                    : <span style={{ color: '#dc3545', fontWeight: 700 }}>✗</span>}
                </td>
                <td>
                  <Button size="sm" variant="outline-danger"
                    style={{ padding: '1px 5px', fontSize: 11, lineHeight: 1.2 }}
                    disabled={point.readings.length <= 1}
                    onClick={() => onRemoveReading(ri)}>✕</Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </>
  );
};

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
  const [activeZone, setActiveZone] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // TUS：記錄器資料
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [rangeStart, setRangeStart] = useState(0);
  const [rangeEnd, setRangeEnd] = useState(0);
  const [showDetail, setShowDetail] = useState(false);

  // SAT：SAT 儀器詳細資料
  const [satChartData, setSatChartData] = useState<ChartData | null>(null);
  const [satRangeStart, setSatRangeStart] = useState(0);
  const [satRangeEnd, setSatRangeEnd] = useState(0);
  const [showSatDetail, setShowSatDetail] = useState(false);

  // SAT：爐體記錄數據
  const [furnaceChartData, setFurnaceChartData] = useState<ChartData | null>(null);
  const [furnaceRangeStart, setFurnaceRangeStart] = useState(0);
  const [furnaceRangeEnd, setFurnaceRangeEnd] = useState(0);
  const [showFurnaceDetail, setShowFurnaceDetail] = useState(false);

  const [showReport, setShowReport] = useState(false);
  const [reportMeta, setReportMeta] = useState<Record<string, string>>({});
  const [itemRows, setItemRows] = useState<ItemRow[]>([emptyItemRow()]);

  const { data: furnaces } = useQuery({
    queryKey: ['furnaces-active'],
    queryFn: () => api.get<{ data: Furnace[] }>('/pyrometry/furnaces?active_only=1').then(r => r.data.data),
  });
  const { data: inspectors } = useQuery({
    queryKey: ['inspectors'],
    queryFn: () => api.get<{ id: number; name: string }[]>('/inspectors').then(r => r.data),
  });

  const applyFurnaceDefaults = (fid: string, type: 'TUS' | 'SAT') => {
    const f = (furnaces || []).find(x => String(x.識別碼) === fid);
    if (!f) return;
    setTolerance(type === 'TUS' ? f.TUS允許公差 : f.SAT允許誤差);
    const n = type === 'TUS' ? f.TUS點數 : f.SAT點數;
    if (type === 'TUS') {
      setTusPoints(Array.from({ length: n }, (_, i) => ({ ...emptyTusPoint(i + 1), 點位: `TUS-${i + 1}` })));
    } else {
      setSatPoints(Array.from({ length: n }, (_, i) => ({ ...emptySatPoint(13 + i), 控溫區: `Zone${i + 1}` })));
      setActiveZone(0);
    }
  };

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
      setTusPoints(tus_points.map((p: TusPoint, i: number) => ({
        ...p,
        點位: /^P\d+$/.test(p.點位 || '') ? `TUS-${i + 1}` : (p.點位 || `TUS-${i + 1}`),
        頻道: p.頻道 ?? (i + 1),
      })));
      setSatPoints(sat_points.map((p: SatPoint, i: number) => ({
        ...p,
        頻道: p.頻道 ?? (13 + i),
        readings: p.readings?.length ? p.readings : [emptyReading()],
      })));
      setActiveZone(0);
      if (cd) {
        if (main.測試類型 === 'TUS' && cd.時間) {
          setChartData({ 時間: cd.時間, 數值: cd.數值 });
          setRangeStart(cd.穩定開始 ?? 0);
          setRangeEnd(cd.穩定結束 ?? (cd.時間.length - 1));
        }
        if (main.測試類型 === 'SAT' && cd.時間) {
          setSatChartData({ 時間: cd.時間, 數值: cd.數值 });
          setSatRangeStart(cd.穩定開始 ?? 0);
          setSatRangeEnd(cd.穩定結束 ?? (cd.時間.length - 1));
        }
        if (cd.爐體數值) {
          setFurnaceChartData({ 時間: cd.爐體時間 || cd.時間, 數值: cd.爐體數值 });
          const fLen = (cd.爐體時間 || cd.時間).length;
          setFurnaceRangeStart(cd.爐體穩定開始 ?? 0);
          setFurnaceRangeEnd(cd.爐體穩定結束 ?? (fLen - 1));
        }
      }
      const { itemRows: savedItems, meta } = splitReportFields(r.data.報告欄位 || {});
      setItemRows(savedItems.length ? savedItems : [emptyItemRow()]);
      setReportMeta(meta);
    });
  }, [editId]);

  // TUS 量測點更新
  const updateTus = (i: number, k: keyof TusPoint, v: string) =>
    setTusPoints(prev => prev.map((p, idx) =>
      idx === i ? { ...p, [k]: k === '頻道' ? (v === '' ? null : Number(v)) : v } : p,
    ));

  // SAT zone 欄位更新（控溫區、頻道、修正值）
  const updateSatField = (i: number, k: keyof SatPoint, v: string) =>
    setSatPoints(prev => prev.map((p, idx) =>
      idx === i ? { ...p, [k]: k === '頻道' ? (v === '' ? null : Number(v)) : v } : p,
    ));

  // SAT 單筆讀值更新
  const updateSatReading = (i: number, ri: number, k: keyof SatReading, v: string) =>
    setSatPoints(prev => prev.map((p, idx) =>
      idx === i
        ? { ...p, readings: p.readings.map((r, rIdx) => rIdx === ri ? { ...r, [k]: v } : r) }
        : p,
    ));

  const addSatReading = (i: number) =>
    setSatPoints(prev => prev.map((p, idx) =>
      idx === i ? { ...p, readings: [...p.readings, emptyReading()] } : p,
    ));

  const removeSatReading = (i: number, ri: number) =>
    setSatPoints(prev => prev.map((p, idx) =>
      idx === i ? { ...p, readings: p.readings.filter((_, rIdx) => rIdx !== ri) } : p,
    ));

  const updateItemRow = (idx: number, k: keyof ItemRow, v: string) =>
    setItemRows(prev => prev.map((row, i) => i === idx ? { ...row, [k]: v } : row));

  // TUS 恆溫穩定期 → 回填最高/最低溫
  const applyRangeTus = () => {
    if (!chartData) return;
    const stats = computeRangeStats(chartData.數值, rangeStart, rangeEnd);
    setTusPoints(prev => prev.map((p, i) => {
      const ch = stats[i];
      return ch ? { ...p, 最高溫: String(ch.最高溫), 最低溫: String(ch.最低溫) } : p;
    }));
  };

  // SAT 恆溫穩定期 → 每個通道的每個時間點填入「校正測試讀值」
  const applyRangeSat = () => {
    if (!satChartData) return;
    const channels = Object.keys(satChartData.數值);
    setSatPoints(prev => prev.map((p, i) => {
      const ch = channels[i];
      if (!ch) return p;
      const values = satChartData.數值[ch]
        .slice(satRangeStart, satRangeEnd + 1)
        .filter((v): v is number => v !== null && v !== undefined);
      if (!values.length) return p;
      const newReadings: SatReading[] = values.map((v, vi) => ({
        控制儀表讀值: p.readings[vi]?.控制儀表讀值 ?? '',
        校正測試讀值: String(Math.round(v * 100) / 100),
      }));
      return { ...p, readings: newReadings };
    }));
  };

  // 爐體恆溫穩定期 → 每個通道的每個時間點填入「控制儀表讀值」
  const applyRangeFurnace = () => {
    if (!furnaceChartData) return;
    const channels = Object.keys(furnaceChartData.數值);
    setSatPoints(prev => prev.map((p, i) => {
      const ch = channels[i];
      if (!ch) return p;
      const values = furnaceChartData.數值[ch]
        .slice(furnaceRangeStart, furnaceRangeEnd + 1)
        .filter((v): v is number => v !== null && v !== undefined);
      if (!values.length) return p;
      const newReadings: SatReading[] = values.map((v, vi) => ({
        控制儀表讀值: String(Math.round(v * 100) / 100),
        校正測試讀值: p.readings[vi]?.校正測試讀值 ?? '',
      }));
      return { ...p, readings: newReadings };
    }));
  };

  const applyCorrections = async (type: 'TUS' | 'SAT') => {
    const count = type === 'TUS' ? tusPoints.length : satPoints.length;
    if (!count) return;
    let url = `/pyrometry/corrections?setpoint=${Number(setpoint) || 0}&type=${type}&count=${count}`;
    if (type === 'TUS') {
      const chs = tusPoints.map(p => p.頻道 ?? '').join(',');
      if (chs) url += `&channels=${chs}`;
    } else {
      const chs = satPoints.map(p => p.頻道 ?? '').join(',');
      if (chs) url += `&channels=${chs}`;
    }
    const r = await api.get<{ success: boolean; data: number[] }>(url);
    if (r.data.success) {
      if (type === 'TUS') {
        setTusPoints(prev => prev.map((p, i) => ({ ...p, 修正值: String(r.data.data[i] ?? '') })));
      } else {
        setSatPoints(prev => prev.map((p, i) => ({ ...p, 修正值: String(r.data.data[i] ?? '') })));
      }
    }
  };

  const inheritFromTus = async () => {
    if (!furnaceId || !testDate) return;
    try {
      const list = await api.get<{ success: boolean; data: { 識別碼: number }[] }>(
        `/pyrometry/tests?furnace_id=${furnaceId}&test_type=TUS&date_from=${testDate}&date_to=${testDate}&page_size=1`,
      );
      if (!list.data.data?.length) {
        alert('找不到同日同爐的 TUS 紀錄，請確認爐號與測試日期已填寫');
        return;
      }
      const tusId = list.data.data[0].識別碼;
      const detail = await api.get<{ 報告欄位?: ReportFieldsResponse }>(`/pyrometry/tests/${tusId}`);
      const { itemRows: inheritedItems, meta } = splitReportFields(detail.data.報告欄位 || {});
      setReportMeta(prev => ({ ...prev, ...meta }));
      if (inheritedItems.length) setItemRows(inheritedItems);
    } catch {
      alert('繼承失敗，請稍後再試');
    }
  };

  const handleFileUpload = async (file: File, dest: 'recorder' | 'sat' | 'furnace') => {
    const formData = new FormData();
    formData.append('file', file);
    const r = await api.post<{
      success: boolean;
      data: { 時間: string[]; 通道: { 名稱: string }[]; 數值: Record<string, number[]> };
    }>('/pyrometry/parse-data', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
    if (!r.data.success) return;
    const lastIdx = r.data.data.時間.length - 1;
    if (dest === 'furnace') {
      setFurnaceChartData({ 時間: r.data.data.時間, 數值: r.data.data.數值 });
      setFurnaceRangeStart(0); setFurnaceRangeEnd(lastIdx);
    } else if (dest === 'recorder') {
      setChartData({ 時間: r.data.data.時間, 數值: r.data.data.數值 });
      setRangeStart(0); setRangeEnd(lastIdx);
      // 初始回填 TUS 量測點（全範圍 max/min）
      const channels = Object.keys(r.data.data.數值);
      setTusPoints(prev => prev.map((p, i) => {
        const ch = channels[i];
        if (!ch) return p;
        const vals = r.data.data.數值[ch].filter((v): v is number => v !== null);
        return vals.length
          ? { ...p, 最高溫: String(Math.max(...vals)), 最低溫: String(Math.min(...vals)) }
          : p;
      }));
    } else {
      // dest === 'sat'：每個通道每個時間點 → 一筆讀值
      setSatChartData({ 時間: r.data.data.時間, 數值: r.data.data.數值 });
      setSatRangeStart(0); setSatRangeEnd(lastIdx);
      const channels = Object.keys(r.data.data.數值);
      setSatPoints(prev => prev.map((p, i) => {
        const ch = channels[i];
        if (!ch) return p;
        const values = r.data.data.數值[ch].filter((v): v is number => v !== null);
        const newReadings: SatReading[] = values.map((v, vi) => ({
          控制儀表讀值: p.readings[vi]?.控制儀表讀值 ?? '',
          校正測試讀值: String(Math.round(v * 100) / 100),
        }));
        return newReadings.length ? { ...p, readings: newReadings } : p;
      }));
    }
  };

  const handleSave = async () => {
    setSaving(true); setError('');
    try {
      const curveData = testType === 'TUS'
        ? (chartData ? {
            時間: chartData.時間, 數值: chartData.數值,
            穩定開始: rangeStart, 穩定結束: rangeEnd,
          } : null)
        : (satChartData ? {
            時間: satChartData.時間, 數值: satChartData.數值,
            穩定開始: satRangeStart, 穩定結束: satRangeEnd,
            爐體時間: furnaceChartData?.時間 || null,
            爐體數值: furnaceChartData?.數值 || null,
            爐體穩定開始: furnaceChartData ? furnaceRangeStart : null,
            爐體穩定結束: furnaceChartData ? furnaceRangeEnd : null,
          } : (furnaceChartData ? {
            爐體時間: furnaceChartData.時間, 爐體數值: furnaceChartData.數值,
            爐體穩定開始: furnaceRangeStart, 爐體穩定結束: furnaceRangeEnd,
          } : null));

      const payload = {
        爐子ID: Number(furnaceId), 測試類型: testType,
        測試日期: testDate, 設定溫度: setpoint, 允許公差: tolerance,
        測試人員: testerId ? Number(testerId) : null,
        測試儀器編號: testInstrument, 標準校正儀器編號: stdInstrument,
        儀器校正到期日: calDueDate || null, 備註: note,
        points: testType === 'TUS' ? tusPoints : satPoints,
        曲線資料: curveData,
        報告欄位: { ...reportMeta, 料號批次: itemRows },
      };
      if (editId) {
        await api.put(`/pyrometry/tests/${editId}`, payload);
      } else {
        await api.post('/pyrometry/tests', payload);
      }
      onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '儲存失敗');
    } finally {
      setSaving(false);
    }
  };

  const timeLabels = chartData?.時間 ?? [];
  const satTimeLabels = satChartData?.時間 ?? [];
  const furnaceTimeLabels = furnaceChartData?.時間 ?? [];

  const furnaceSection = furnaceChartData ? (
    <>
      <Col md={12}>
        <TusChart
          時間={furnaceChartData.時間} 數值={furnaceChartData.數值}
          設定溫度={Number(setpoint) || 180} 公差={Number(tolerance) || 10}
          startIdx={furnaceRangeStart} endIdx={furnaceRangeEnd}
          標題="爐體記錄溫度曲線"
        />
      </Col>
      <Col md={12}>
        <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
          <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>爐體恆溫穩定期：</span>
          <div className="d-flex align-items-center gap-1">
            <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
            <Form.Select size="sm" style={{ minWidth: 120 }} value={furnaceRangeStart}
              onChange={e => setFurnaceRangeStart(Number(e.target.value))}>
              {furnaceTimeLabels.map((t, i) => <option key={i} value={i}>{t}</option>)}
            </Form.Select>
          </div>
          <div className="d-flex align-items-center gap-1">
            <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
            <Form.Select size="sm" style={{ minWidth: 120 }} value={furnaceRangeEnd}
              onChange={e => setFurnaceRangeEnd(Number(e.target.value))}>
              {furnaceTimeLabels.map((t, i) => <option key={i} value={i}>{t}</option>)}
            </Form.Select>
          </div>
          <Button size="sm" variant="primary" onClick={applyRangeFurnace}>
            套用並回填控制儀表讀值
          </Button>
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
            <span style={{ background: '#f8d7da', color: '#842029', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>紅底＝超上限</span>
            <span style={{ background: '#cfe2ff', color: '#084298', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>藍底＝低於下限</span>
          </span>
        </div>
        {showFurnaceDetail && (
          <TusDataTable
            時間={furnaceChartData.時間} 數值={furnaceChartData.數值}
            設定溫度={Number(setpoint) || 180} 公差={Number(tolerance) || 10}
            穩定開始={furnaceRangeStart} 穩定結束={furnaceRangeEnd}
          />
        )}
      </Col>
    </>
  ) : null;

  return (
    <Modal show onHide={onClose} size="xl">
      <Modal.Header closeButton>
        <Modal.Title>{editId ? '編輯爐溫測試' : '新增爐溫測試'}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {error && <div className="alert alert-danger py-1">{error}</div>}
        <Form>
          {/* ── 基本資料 ── */}
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

          {/* ── 報告欄位 ── */}
          <div className="mb-3">
            <Button size="sm" variant="outline-secondary" className="mb-2" onClick={() => setShowReport(v => !v)}>
              {showReport ? '隱藏報告欄位' : '報告欄位（客戶/料號/核准等，QRA073/074）'}
            </Button>
            {showReport && (
              <div className="p-2 bg-light rounded border">
                {testType === 'SAT' && (
                  <div className="mb-2">
                    <Button size="sm" variant="outline-info"
                      disabled={!furnaceId || !testDate}
                      onClick={inheritFromTus}>
                      從同日 TUS 繼承報告資料
                    </Button>
                    {(!furnaceId || !testDate) && (
                      <span className="text-muted ms-2" style={{ fontSize: 12 }}>（需先填寫爐號與測試日期）</span>
                    )}
                  </div>
                )}
                <Row className="g-2 mb-2">
                  {/* 爐具測試溫度（由設定溫度帶入，唯讀） */}
                  <Col md={3}>
                    <Form.Label className="mb-0" style={{ fontSize: 12 }}>爐具測試溫度 (°C)</Form.Label>
                    <Form.Control size="sm" value={setpoint || ''} readOnly className="bg-white" />
                  </Col>
                  {/* 測試條件：三選一 */}
                  <Col md={4}>
                    <Form.Label className="mb-0" style={{ fontSize: 12 }}>測試條件</Form.Label>
                    <div className="d-flex gap-3 pt-1">
                      {['空爐', '滿爐', '其他'].map(opt => (
                        <Form.Check key={opt} type="radio" inline label={opt}
                          checked={reportMeta['測試條件'] === opt}
                          onChange={() => setReportMeta(prev => ({ ...prev, 測試條件: opt }))} />
                      ))}
                    </div>
                  </Col>
                  {/* 其他單值欄位 */}
                  {(['客戶名稱', '預估總重量', '控制器型號', '控制器設定值', '控制器補償', '溫濕度', '執行單位', '核准', '製表'] as const).map(k => (
                    <Col md={3} key={k}>
                      <Form.Label className="mb-0" style={{ fontSize: 12 }}>{k}</Form.Label>
                      <Form.Control size="sm" value={reportMeta[k] || ''}
                        onChange={e => setReportMeta(prev => ({ ...prev, [k]: e.target.value }))} />
                    </Col>
                  ))}
                </Row>
                {/* 工件明細表 */}
                <Form.Label className="mb-1 fw-semibold" style={{ fontSize: 12 }}>工件明細</Form.Label>
                <Table bordered size="sm" className="mb-1">
                  <thead className="table-secondary">
                    <tr>
                      <th>工件料號</th>
                      <th>生產批號</th>
                      <th style={{ width: 130 }}>內外徑尺寸</th>
                      <th style={{ width: 100 }}>支數</th>
                      <th style={{ width: 36 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {itemRows.map((row, idx) => (
                      <tr key={idx}>
                        <td><Form.Control size="sm" value={row.工件料號} onChange={e => updateItemRow(idx, '工件料號', e.target.value)} /></td>
                        <td><Form.Control size="sm" value={row.生產批號} onChange={e => updateItemRow(idx, '生產批號', e.target.value)} /></td>
                        <td><Form.Control size="sm" value={row.內外徑尺寸} onChange={e => updateItemRow(idx, '內外徑尺寸', e.target.value)} /></td>
                        <td><Form.Control size="sm" value={row.支數} onChange={e => updateItemRow(idx, '支數', e.target.value)} /></td>
                        <td className="text-center align-middle">
                          {itemRows.length > 1 && (
                            <Button size="sm" variant="outline-danger"
                              onClick={() => setItemRows(prev => prev.filter((_, i) => i !== idx))}>×</Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <Button size="sm" variant="outline-secondary"
                  onClick={() => setItemRows(prev => [...prev, emptyItemRow()])}>+ 新增工件</Button>
              </div>
            )}
          </div>

          {/* ── TUS 資料上傳 ── */}
          {testType === 'TUS' && (
            <Row className="g-2 mb-3">
              <Col md={12}>
                <Form.Label>測試儀器數據（CSV/Excel）</Form.Label>
                <input className="form-control form-control-sm" type="file" accept=".csv,.xlsx,.xls"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f, 'recorder'); }} />
              </Col>
              {chartData && (
                <>
                  <Col md={12}>
                    <TusChart
                      時間={chartData.時間} 數值={chartData.數值}
                      設定溫度={Number(setpoint) || 180} 公差={Number(tolerance) || 10}
                      startIdx={rangeStart} endIdx={rangeEnd}
                      標題="測試儀器（記錄器）溫度曲線"
                    />
                  </Col>
                  <Col md={12}>
                    <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
                      <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>恆溫穩定期：</span>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
                        <Form.Select size="sm" style={{ minWidth: 120 }} value={rangeStart}
                          onChange={e => setRangeStart(Number(e.target.value))}>
                          {timeLabels.map((t, i) => <option key={i} value={i}>{t}</option>)}
                        </Form.Select>
                      </div>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
                        <Form.Select size="sm" style={{ minWidth: 120 }} value={rangeEnd}
                          onChange={e => setRangeEnd(Number(e.target.value))}>
                          {timeLabels.map((t, i) => <option key={i} value={i}>{t}</option>)}
                        </Form.Select>
                      </div>
                      <Button size="sm" variant="primary" onClick={applyRangeTus}>套用並回填量測點</Button>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        共 {rangeEnd >= rangeStart ? rangeEnd - rangeStart + 1 : 0} 筆
                      </span>
                    </div>
                  </Col>
                  <Col md={12}>
                    <div className="d-flex align-items-center gap-2 mb-1">
                      <Button size="sm" variant="outline-secondary" onClick={() => setShowDetail(v => !v)}>
                        {showDetail ? '隱藏詳細數據表' : '顯示詳細數據表'}
                      </Button>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        <span style={{ background: '#f8d7da', color: '#842029', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>紅底＝超上限</span>
                        <span style={{ background: '#cfe2ff', color: '#084298', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>藍底＝低於下限</span>
                      </span>
                    </div>
                    {showDetail && (
                      <TusDataTable
                        時間={chartData.時間} 數值={chartData.數值}
                        設定溫度={Number(setpoint) || 180} 公差={Number(tolerance) || 10}
                        穩定開始={rangeStart} 穩定結束={rangeEnd}
                      />
                    )}
                  </Col>
                </>
              )}
            </Row>
          )}

          {/* ── TUS 量測點明細 ── */}
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
                  <tr><th>點位</th><th style={{ width: 100, minWidth: 100 }}>頻道</th><th>修正值</th><th>最高溫</th><th>最低溫</th></tr>
                </thead>
                <tbody>
                  {tusPoints.map((p, i) => (
                    <tr key={i}>
                      <td><Form.Control size="sm" value={p.點位} onChange={e => updateTus(i, '點位', e.target.value)} /></td>
                      <td><Form.Control size="sm" type="number" min={1} max={99} value={p.頻道 ?? ''} onChange={e => updateTus(i, '頻道', e.target.value)} style={{ minWidth: 70 }} /></td>
                      <td><Form.Control size="sm" value={String(p.修正值 ?? '')} onChange={e => updateTus(i, '修正值', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.最高溫 ?? '')} onChange={e => updateTus(i, '最高溫', e.target.value)} /></td>
                      <td><Form.Control size="sm" value={String(p.最低溫 ?? '')} onChange={e => updateTus(i, '最低溫', e.target.value)} /></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </>
          )}

          {/* ── SAT 資料上傳 ── */}
          {testType === 'SAT' && (
            <Row className="g-2 mb-3">
              <Col md={6}>
                <Form.Label>SAT 儀器詳細資料（CSV/Excel，選配）</Form.Label>
                <input className="form-control form-control-sm" type="file" accept=".csv,.xlsx,.xls"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f, 'sat'); }} />
              </Col>
              <Col md={6}>
                <Form.Label>爐體記錄數據（對照，選配）</Form.Label>
                <input className="form-control form-control-sm" type="file" accept=".csv,.xlsx,.xls"
                  onChange={e => { const f = e.target.files?.[0]; if (f) handleFileUpload(f, 'furnace'); }} />
              </Col>

              {satChartData && (
                <>
                  <Col md={12}>
                    <TusChart
                      時間={satChartData.時間} 數值={satChartData.數值}
                      設定溫度={Number(setpoint) || 180} 公差={Number(tolerance) || 10}
                      startIdx={satRangeStart} endIdx={satRangeEnd}
                      標題="SAT 儀器溫度曲線"
                    />
                  </Col>
                  <Col md={12}>
                    <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
                      <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>SAT 恆溫穩定期：</span>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
                        <Form.Select size="sm" style={{ minWidth: 120 }} value={satRangeStart}
                          onChange={e => setSatRangeStart(Number(e.target.value))}>
                          {satTimeLabels.map((t, i) => <option key={i} value={i}>{t}</option>)}
                        </Form.Select>
                      </div>
                      <div className="d-flex align-items-center gap-1">
                        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
                        <Form.Select size="sm" style={{ minWidth: 120 }} value={satRangeEnd}
                          onChange={e => setSatRangeEnd(Number(e.target.value))}>
                          {satTimeLabels.map((t, i) => <option key={i} value={i}>{t}</option>)}
                        </Form.Select>
                      </div>
                      <Button size="sm" variant="primary" onClick={applyRangeSat}>
                        套用並回填讀值
                      </Button>
                      <span className="text-muted" style={{ fontSize: 11 }}>
                        共 {satRangeEnd >= satRangeStart ? satRangeEnd - satRangeStart + 1 : 0} 筆
                      </span>
                    </div>
                  </Col>
                  <Col md={12}>
                    <div className="d-flex align-items-center gap-2 mb-1">
                      <Button size="sm" variant="outline-secondary" onClick={() => setShowSatDetail(v => !v)}>
                        {showSatDetail ? '隱藏 SAT 詳細數據表' : '顯示 SAT 詳細數據表'}
                      </Button>
                    </div>
                    {showSatDetail && (
                      <TusDataTable
                        時間={satChartData.時間} 數值={satChartData.數值}
                        設定溫度={Number(setpoint) || 180} 公差={Number(tolerance) || 10}
                        穩定開始={satRangeStart} 穩定結束={satRangeEnd}
                      />
                    )}
                  </Col>
                </>
              )}

              {furnaceSection}
            </Row>
          )}

          {/* ── SAT 量測點明細（分頁 Tab） ── */}
          {testType === 'SAT' && satPoints.length > 0 && (
            <>
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h6 className="mb-0">SAT 量測點明細</h6>
                <Button size="sm" variant="outline-secondary" onClick={() => applyCorrections('SAT')}>
                  帶入儀器校正補正值
                </Button>
              </div>
              <div className="text-muted mb-2" style={{ fontSize: 11 }}>
                偏差＝（校正測試讀值＋修正值）− 控制讀值；每筆讀值均需符合公差 ±{tolerance || '?'}°C
              </div>

              {/* 控溫區 Tab 列 */}
              <Nav variant="tabs" activeKey={activeZone}
                onSelect={k => setActiveZone(Number(k))}>
                {satPoints.map((p, i) => {
                  const tol = parseFloat(String(tolerance)) || 0;
                  const corr = parseFloat(String(p.修正值 ?? 0)) || 0;
                  const allPass = p.readings.every(r => {
                    const ctrl = parseFloat(String(r.控制儀表讀值));
                    const test = parseFloat(String(r.校正測試讀值));
                    if (isNaN(ctrl) || isNaN(test)) return true;
                    return Math.abs(test - ctrl + corr) <= tol;
                  });
                  const hasData = p.readings.some(r => r.校正測試讀值 !== '' && r.校正測試讀值 !== null);
                  return (
                    <Nav.Item key={i}>
                      <Nav.Link eventKey={i} style={{ fontSize: 13, padding: '6px 14px' }}>
                        {p.控溫區 || `Zone${i + 1}`}
                        {hasData && (
                          <span style={{ marginLeft: 6, fontWeight: 700 }}>
                            {allPass
                              ? <span style={{ color: '#198754' }}>✓</span>
                              : <span style={{ color: '#dc3545' }}>✗</span>}
                          </span>
                        )}
                      </Nav.Link>
                    </Nav.Item>
                  );
                })}
              </Nav>

              {/* 當前 Tab 內容 */}
              <div className="border border-top-0 rounded-bottom p-3 mb-3">
                {satPoints.map((p, i) =>
                  i === activeZone ? (
                    <ZoneTab
                      key={i}
                      point={p}
                      tolerance={tolerance}
                      onUpdateField={(k, v) => updateSatField(i, k, v)}
                      onUpdateReading={(ri, k, v) => updateSatReading(i, ri, k, v)}
                      onAddReading={() => addSatReading(i)}
                      onRemoveReading={ri => removeSatReading(i, ri)}
                    />
                  ) : null,
                )}
              </div>
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
