import { useState, useEffect } from 'react';
import { Modal, Form, Row, Col, Button } from 'react-bootstrap';
import toast from 'react-hot-toast';
import type { TusPoint, SatPoint, SatReading } from '../../types';
import { useInspectors } from '../../hooks/useInspectors';
import {
  useFurnaces,
  useLoadPyrometryTestDetail,
  useParsePyrometryData,
  usePyrometryCorrections,
  usePyrometryTestDetail,
  useSavePyrometryTest,
  useTusTestOnDate,
} from '../../hooks/usePyrometry';
import FurnaceRecorderSection from './FurnaceRecorderSection';
import ReportFieldsSection from './ReportFieldsSection';
import SatSection from './SatSection';
import TusSection from './TusSection';
import { buildPyrometryPayload } from './pyrometryPayload';
import { buildPyrometryEditFormState } from './pyrometryFormHydration';
import {
  applyChartRangeToSatReadings,
  applyChartRangeToTusPoints,
  emptyItemRow,
  emptyReading,
  emptySatPoint,
  emptyTusPoint,
  splitReportFields,
  type ChartData,
  type ItemRow,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';

interface Props { editId: number | null; onClose: () => void; onSaved: () => void; }

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

  const { data: furnaces } = useFurnaces({ activeOnly: true });
  const { data: inspectors } = useInspectors();
  const { data: editData, isError: isEditLoadError } = usePyrometryTestDetail(editId);
  const loadTestDetail = useLoadPyrometryTestDetail();
  const saveTest = useSavePyrometryTest(editId);
  const correctionsMutation = usePyrometryCorrections();
  const parseMutation = useParsePyrometryData();
  const tusOnDateMutation = useTusTestOnDate();

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
    if (!editId || !editData) return;
    let active = true;
    setError('');
    queueMicrotask(() => {
      if (!active) return;
      const state = buildPyrometryEditFormState(editData);
      setFurnaceId(state.furnaceId);
      setTestType(state.testType);
      setTestDate(state.testDate);
      setSetpoint(state.setpoint);
      setTolerance(state.tolerance);
      setTesterId(state.testerId);
      setTestInstrument(state.testInstrument);
      setStdInstrument(state.stdInstrument);
      setCalDueDate(state.calDueDate);
      setNote(state.note);
      setTusPoints(state.tusPoints);
      setSatPoints(state.satPoints);
      setActiveZone(state.activeZone);
      setChartData(state.chartData);
      setRangeStart(state.rangeStart);
      setRangeEnd(state.rangeEnd);
      setSatChartData(state.satChartData);
      setSatRangeStart(state.satRangeStart);
      setSatRangeEnd(state.satRangeEnd);
      setFurnaceChartData(state.furnaceChartData);
      setFurnaceRangeStart(state.furnaceRangeStart);
      setFurnaceRangeEnd(state.furnaceRangeEnd);
      setItemRows(state.itemRows);
      setReportMeta(state.reportMeta);
    });

    return () => {
      active = false;
    };
  }, [editId, editData]);

  useEffect(() => {
    if (isEditLoadError) setError('載入爐溫測試資料失敗');
  }, [isEditLoadError]);

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
    setTusPoints(prev => applyChartRangeToTusPoints(prev, chartData, rangeStart, rangeEnd));
  };

  // SAT 恆溫穩定期 → 每個通道的每個時間點填入「校正測試讀值」
  const applyRangeSat = () => {
    if (!satChartData) return;
    setSatPoints(prev => applyChartRangeToSatReadings(
      prev,
      satChartData,
      satRangeStart,
      satRangeEnd,
      '校正測試讀值',
    ));
  };

  // 爐體恆溫穩定期 → 每個通道的每個時間點填入「控制儀表讀值」
  const applyRangeFurnace = () => {
    if (!furnaceChartData) return;
    setSatPoints(prev => applyChartRangeToSatReadings(
      prev,
      furnaceChartData,
      furnaceRangeStart,
      furnaceRangeEnd,
      '控制儀表讀值',
    ));
  };

  const applyCorrections = async (type: 'TUS' | 'SAT') => {
    const count = type === 'TUS' ? tusPoints.length : satPoints.length;
    if (!count) return;
    const channels = (type === 'TUS' ? tusPoints : satPoints).map(p => p.頻道 ?? '').join(',');
    const r = await correctionsMutation.mutateAsync({
      setpoint: Number(setpoint) || 0,
      type,
      count,
      channels: channels || undefined,
    });
    if (r.success) {
      if (type === 'TUS') {
        setTusPoints(prev => prev.map((p, i) => ({ ...p, 修正值: String(r.data[i] ?? '') })));
      } else {
        setSatPoints(prev => prev.map((p, i) => ({ ...p, 修正值: String(r.data[i] ?? '') })));
      }
    }
  };

  const inheritFromTus = async () => {
    if (!furnaceId || !testDate) return;
    try {
      const list = await tusOnDateMutation.mutateAsync({ furnaceId, testDate });
      if (!list.data?.length) {
        toast.error('找不到同日同爐的 TUS 紀錄，請確認爐號與測試日期已填寫');
        return;
      }
      const tusId = list.data[0].識別碼;
      const detail = await loadTestDetail.mutateAsync(tusId) as { 報告欄位?: ReportFieldsResponse };
      const { itemRows: inheritedItems, meta } = splitReportFields(detail.報告欄位 || {});
      setReportMeta(prev => ({ ...prev, ...meta }));
      if (inheritedItems.length) setItemRows(inheritedItems);
    } catch {
      toast.error('繼承失敗，請稍後再試');
    }
  };

  const handleFileUpload = async (file: File, dest: 'recorder' | 'sat' | 'furnace') => {
    const r = await parseMutation.mutateAsync(file);
    if (!r.success) return;
    const lastIdx = r.data.時間.length - 1;
    if (dest === 'furnace') {
      setFurnaceChartData({ 時間: r.data.時間, 數值: r.data.數值 });
      setFurnaceRangeStart(0); setFurnaceRangeEnd(lastIdx);
    } else if (dest === 'recorder') {
      setChartData({ 時間: r.data.時間, 數值: r.data.數值 });
      setRangeStart(0); setRangeEnd(lastIdx);
      // 初始回填 TUS 量測點（全範圍 max/min）
      setTusPoints(prev => applyChartRangeToTusPoints(prev, r.data, 0, lastIdx));
    } else {
      // dest === 'sat'：每個通道每個時間點 → 一筆讀值
      setSatChartData({ 時間: r.data.時間, 數值: r.data.數值 });
      setSatRangeStart(0); setSatRangeEnd(lastIdx);
      setSatPoints(prev => applyChartRangeToSatReadings(prev, r.data, 0, lastIdx, '校正測試讀值'));
    }
  };

  const handleSave = async () => {
    setSaving(true); setError('');
    try {
      const payload = buildPyrometryPayload({
        furnaceId,
        testType,
        testDate,
        setpoint,
        tolerance,
        testerId,
        testInstrument,
        stdInstrument,
        calDueDate,
        note,
        tusPoints,
        satPoints,
        chartData,
        rangeStart,
        rangeEnd,
        satChartData,
        satRangeStart,
        satRangeEnd,
        furnaceChartData,
        furnaceRangeStart,
        furnaceRangeEnd,
        reportMeta,
        itemRows,
      });
      await saveTest.mutateAsync({ payload });
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

  const furnaceSection = (
    <FurnaceRecorderSection
      furnaceChartData={furnaceChartData}
      setpoint={setpoint}
      tolerance={tolerance}
      furnaceRangeStart={furnaceRangeStart}
      furnaceRangeEnd={furnaceRangeEnd}
      furnaceTimeLabels={furnaceTimeLabels}
      showFurnaceDetail={showFurnaceDetail}
      onFurnaceRangeStartChange={setFurnaceRangeStart}
      onFurnaceRangeEndChange={setFurnaceRangeEnd}
      onApplyRangeFurnace={applyRangeFurnace}
      onToggleFurnaceDetail={() => setShowFurnaceDetail(v => !v)}
    />
  );

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
                {(inspectors || []).map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
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

          <ReportFieldsSection
            showReport={showReport}
            testType={testType}
            furnaceId={furnaceId}
            testDate={testDate}
            setpoint={setpoint}
            reportMeta={reportMeta}
            itemRows={itemRows}
            onToggle={() => setShowReport(v => !v)}
            onInheritFromTus={inheritFromTus}
            onSetReportMeta={setReportMeta}
            onSetItemRows={setItemRows}
            onUpdateItemRow={updateItemRow}
          />

          {testType === 'TUS' && (
            <TusSection
              tusPoints={tusPoints}
              setpoint={setpoint}
              tolerance={tolerance}
              chartData={chartData}
              rangeStart={rangeStart}
              rangeEnd={rangeEnd}
              showDetail={showDetail}
              timeLabels={timeLabels}
              onFileUpload={file => handleFileUpload(file, 'recorder')}
              onRangeStartChange={setRangeStart}
              onRangeEndChange={setRangeEnd}
              onApplyRangeTus={applyRangeTus}
              onToggleDetail={() => setShowDetail(v => !v)}
              onUpdateTus={updateTus}
              onApplyCorrections={() => applyCorrections('TUS')}
            />
          )}

          {testType === 'SAT' && (
            <SatSection
              satPoints={satPoints}
              activeZone={activeZone}
              setpoint={setpoint}
              tolerance={tolerance}
              satChartData={satChartData}
              satRangeStart={satRangeStart}
              satRangeEnd={satRangeEnd}
              satTimeLabels={satTimeLabels}
              showSatDetail={showSatDetail}
              furnaceSection={furnaceSection}
              onSatFileUpload={file => handleFileUpload(file, 'sat')}
              onFurnaceFileUpload={file => handleFileUpload(file, 'furnace')}
              onSatRangeStartChange={setSatRangeStart}
              onSatRangeEndChange={setSatRangeEnd}
              onApplyRangeSat={applyRangeSat}
              onToggleSatDetail={() => setShowSatDetail(v => !v)}
              onActiveZoneChange={setActiveZone}
              onUpdateSatField={updateSatField}
              onUpdateSatReading={updateSatReading}
              onAddSatReading={addSatReading}
              onRemoveSatReading={removeSatReading}
              onApplyCorrections={() => applyCorrections('SAT')}
            />
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
