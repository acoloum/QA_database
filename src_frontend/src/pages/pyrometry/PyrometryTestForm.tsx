import { useState, useEffect } from 'react';
import { Modal, Form, Button } from 'react-bootstrap';
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
  addSatReadingToPoint,
  applyParsedPyrometryData,
  emptyItemRow,
  emptySatPoint,
  emptyTusPoint,
  inheritReportFields,
  removeSatReadingFromPoint,
  type ChartData,
  type ItemRow,
  type PyrometryUploadDestination,
  type ReportFieldsResponse,
} from './pyrometryFormUtils';
import {
  updateItemRowAt,
  updateSatFieldAt,
  updateSatReadingAt,
  updateTusPointAt,
} from './pyrometryPointUpdates';
import PyrometryBasicSection from './PyrometryBasicSection';

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
    setTusPoints(prev => updateTusPointAt(prev, i, k, v));

  // SAT zone 欄位更新（控溫區、頻道、修正值）
  const updateSatField = (i: number, k: keyof SatPoint, v: string) =>
    setSatPoints(prev => updateSatFieldAt(prev, i, k, v));

  // SAT 單筆讀值更新
  const updateSatReading = (i: number, ri: number, k: keyof SatReading, v: string) =>
    setSatPoints(prev => updateSatReadingAt(prev, i, ri, k, v));

  const addSatReading = (i: number) =>
    setSatPoints(prev => prev.map((p, idx) =>
      idx === i ? addSatReadingToPoint(p) : p,
    ));

  const removeSatReading = (i: number, ri: number) =>
    setSatPoints(prev => prev.map((p, idx) =>
      idx === i ? removeSatReadingFromPoint(p, ri) : p,
    ));

  const updateItemRow = (idx: number, k: keyof ItemRow, v: string) =>
    setItemRows(prev => updateItemRowAt(prev, idx, k, v));

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
      const inheritedFields = inheritReportFields(reportMeta, itemRows, detail.報告欄位 || {});
      setReportMeta(inheritedFields.meta);
      setItemRows(inheritedFields.itemRows);
    } catch {
      toast.error('繼承失敗，請稍後再試');
    }
  };

  const handleFileUpload = async (file: File, dest: PyrometryUploadDestination) => {
    const r = await parseMutation.mutateAsync(file);
    if (!r.success) return;
    const result = applyParsedPyrometryData({
      destination: dest,
      parsedData: r.data,
      tusPoints,
      satPoints,
    });
    if (result.chartData) setChartData(result.chartData);
    if (result.rangeStart != null) setRangeStart(result.rangeStart);
    if (result.rangeEnd != null) setRangeEnd(result.rangeEnd);
    if (result.tusPoints) setTusPoints(result.tusPoints);
    if (result.satChartData) setSatChartData(result.satChartData);
    if (result.satRangeStart != null) setSatRangeStart(result.satRangeStart);
    if (result.satRangeEnd != null) setSatRangeEnd(result.satRangeEnd);
    if (result.furnaceChartData) setFurnaceChartData(result.furnaceChartData);
    if (result.furnaceRangeStart != null) setFurnaceRangeStart(result.furnaceRangeStart);
    if (result.furnaceRangeEnd != null) setFurnaceRangeEnd(result.furnaceRangeEnd);
    if (result.satPoints) setSatPoints(result.satPoints);
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
          <PyrometryBasicSection
            furnaces={furnaces || []}
            inspectors={inspectors || []}
            furnaceId={furnaceId}
            testType={testType}
            testDate={testDate}
            setpoint={setpoint}
            tolerance={tolerance}
            testerId={testerId}
            testInstrument={testInstrument}
            stdInstrument={stdInstrument}
            calDueDate={calDueDate}
            note={note}
            onFurnaceChange={value => { setFurnaceId(value); applyFurnaceDefaults(value, testType); }}
            onTestTypeChange={value => { setTestType(value); applyFurnaceDefaults(furnaceId, value); }}
            onTestDateChange={setTestDate}
            onSetpointChange={setSetpoint}
            onToleranceChange={setTolerance}
            onTesterIdChange={setTesterId}
            onTestInstrumentChange={setTestInstrument}
            onStdInstrumentChange={setStdInstrument}
            onCalDueDateChange={setCalDueDate}
            onNoteChange={setNote}
          />

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
