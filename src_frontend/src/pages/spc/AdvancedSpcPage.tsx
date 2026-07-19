import { useState } from 'react';
import { Alert, Badge, Button, Card, Col, Form, Row } from 'react-bootstrap';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  useAnalyzeSpcStudy, useApproveSpcResearch, useApproveSpcStudy, useRejectSpcStudy,
  useRetireSpcLimit, useSubmitSpcStudy,
} from '../../hooks/useSpcStudies';
import type { SpcStudyResult } from '../../types';
import { isMachinePerformanceResult } from '../../types/spc';
import AttributeStudyPanel from '../../components/spc/attribute/AttributeStudyPanel';
import MachineConditionForm, { type MachineConditionInput } from '../../components/spc/machine/MachineConditionForm';
import MachinePerformancePanel from '../../components/spc/machine/MachinePerformancePanel';
import SpcBaselineApprovalModal, { type SpcWorkflowAction } from '../../components/spc/SpcBaselineApprovalModal';
import SpcStudyHistoryOffcanvas from '../../components/spc/SpcStudyHistoryOffcanvas';
import SpcStudyWorkflowBar from '../../components/spc/SpcStudyWorkflowBar';

type Source = 'shipping' | 'patrol';
type Family = 'attribute' | 'machine';
type Interval = 'day' | 'week' | 'month';
type AttributeChartType = 'p' | 'np';
type FilterKey = 'vendor' | 'material' | 'spec' | 'customer' | 'item' | 'position'
  | 'start_date' | 'end_date' | 's_date' | 'e_date' | 'm_id' | 'op_id';

interface AdvancedQuery {
  family: Family;
  source: Source;
  interval: Interval;
  chartType: AttributeChartType;
  filters: Record<FilterKey, string>;
  conditionsConfirmed: boolean;
  conditionReason: string;
}

const FILTER_KEYS: FilterKey[] = [
  'vendor', 'material', 'spec', 'customer', 'item', 'position', 'start_date', 'end_date',
  's_date', 'e_date', 'm_id', 'op_id',
];
const ATTRIBUTE_FILTERS = new Set<FilterKey>(FILTER_KEYS.filter(key => !['customer', 'op_id'].includes(key)));
const MACHINE_FILTERS: FilterKey[] = ['m_id', 'material', 'spec', 'item', 'position'];
const TEXT_LIMIT = 120;
const REASON_LIMIT = 500;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const NUMBER_FILTERS = new Set<FilterKey>(['customer', 'm_id', 'op_id']);
const DATE_FILTERS = new Set<FilterKey>(['start_date', 'end_date', 's_date', 'e_date']);

const safeText = (value: string | null) => (value ?? '').trim().slice(0, TEXT_LIMIT);
const safeInteger = (value: string | null) => /^\d+$/.test(value ?? '') ? value as string : '';
const safeDate = (value: string | null) => DATE_PATTERN.test(value ?? '') ? value as string : '';
const safeFilter = (key: FilterKey, value: string | null) => NUMBER_FILTERS.has(key)
  ? safeInteger(value) : DATE_FILTERS.has(key) ? safeDate(value) : safeText(value);
const safeReason = (value: string | null) => (value ?? '').trim().slice(0, REASON_LIMIT);

const parseQuery = (search: URLSearchParams): AdvancedQuery => {
  const family: Family = search.get('family') === 'machine' ? 'machine' : 'attribute';
  const source = family === 'machine' ? 'patrol' : search.get('source') === 'patrol' ? 'patrol' : 'shipping';
  const filters = FILTER_KEYS.reduce<Record<FilterKey, string>>((result, key) => {
    result[key] = safeFilter(key, search.get(key));
    return result;
  }, {} as Record<FilterKey, string>);
  return {
    family, source,
    interval: ['day', 'week', 'month'].includes(search.get('interval') ?? '') ? search.get('interval') as Interval : 'day',
    chartType: ['p', 'np'].includes(search.get('chart_type') ?? '') ? search.get('chart_type') as AttributeChartType : 'p',
    filters,
    conditionsConfirmed: search.get('conditions_confirmed') === 'true',
    conditionReason: safeReason(search.get('condition_reason')),
  };
};

const queryToSearch = (query: AdvancedQuery) => {
  const params = new URLSearchParams({ family: query.family, source: query.family === 'machine' ? 'patrol' : query.source });
  if (query.family === 'machine') {
    MACHINE_FILTERS.forEach(key => { if (query.filters[key]) params.set(key, query.filters[key]); });
    if (query.conditionsConfirmed) params.set('conditions_confirmed', 'true');
    if (query.conditionReason) params.set('condition_reason', query.conditionReason);
  } else {
    params.set('interval', query.interval);
    params.set('chart_type', query.chartType);
    ATTRIBUTE_FILTERS.forEach(key => { if (query.filters[key]) params.set(key, query.filters[key]); });
  }
  return params.toString();
};

const apiError = (error: unknown) => {
  const response = error as { response?: { data?: { message?: string } }; message?: string };
  return response.response?.data?.message ?? response.message ?? '無法建立研究，請確認篩選條件與資料可用性。';
};

const AdvancedSpcPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = parseQuery(searchParams);
  const [result, setResult] = useState<SpcStudyResult | null>(null);
  const [action, setAction] = useState<SpcWorkflowAction | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const { hasPermission } = useAuth();
  const analyze = useAnalyzeSpcStudy();
  const submit = useSubmitSpcStudy();
  const approve = useApproveSpcStudy();
  const approveResearch = useApproveSpcResearch();
  const reject = useRejectSpcStudy();
  const retire = useRetireSpcLimit();
  const canView = hasPermission('spc.view');
  const canManage = hasPermission('spc.manage');
  const canApprove = hasPermission('spc.approve');
  const visibleResult = result?.analysis_family === query.family ? result : null;

  const updateQuery = (next: AdvancedQuery) => setSearchParams(new URLSearchParams(queryToSearch(next)));
  const changeFamily = (family: Family) => {
    setResult(null);
    setAction(null);
    setShowHistory(false);
    updateQuery(family === 'machine'
      ? { ...query, family, source: 'patrol', filters: FILTER_KEYS.reduce((value, key) => ({ ...value, [key]: '' }), {} as Record<FilterKey, string>), conditionsConfirmed: false, conditionReason: '' }
      : { ...query, family, source: 'shipping', filters: FILTER_KEYS.reduce((value, key) => ({ ...value, [key]: '' }), {} as Record<FilterKey, string>), conditionsConfirmed: false, conditionReason: '' });
  };
  const setFilter = (key: FilterKey, value: string) => updateQuery({ ...query, filters: { ...query.filters, [key]: safeFilter(key, value) } });
  const machineValue: MachineConditionInput = {
    m_id: query.filters.m_id, mat: query.filters.material, spec: query.filters.spec,
    item: query.filters.item, pos: query.filters.position,
    conditions_confirmed: query.conditionsConfirmed, condition_reason: query.conditionReason,
  };
  const setMachineValue = (next: MachineConditionInput) => updateQuery({
    ...query, filters: { ...query.filters, m_id: next.m_id, material: next.mat, spec: next.spec, item: next.item, position: next.pos },
    conditionsConfirmed: next.conditions_confirmed, conditionReason: safeReason(next.condition_reason),
  });
  const attributeFilters = (): Record<string, unknown> => query.source === 'shipping'
    ? { vendor: query.filters.vendor, material: query.filters.material, spec: query.filters.spec, field: query.filters.item || '外徑', start_date: query.filters.start_date, end_date: query.filters.end_date }
    : { cust_id: query.filters.customer || null, mat: query.filters.material, spec: query.filters.spec, item: query.filters.item || '厚度', pos: query.filters.position, s_date: query.filters.s_date, e_date: query.filters.e_date, m_id: query.filters.m_id || null, op_id: query.filters.op_id || null };
  const analyzeAttribute = async () => setResult(await analyze.mutateAsync({ source: query.source, filters: attributeFilters(), analysis_family: 'attribute', options: { interval: query.interval, chart_type: query.chartType } }));
  const analyzeMachine = async (request: Parameters<NonNullable<React.ComponentProps<typeof MachineConditionForm>['onAnalyze']>>[0]) => setResult(await analyze.mutateAsync({ source: 'patrol', analysis_family: 'machine', ...request }));

  const handleAction = async (reason: string) => {
    if (!visibleResult || !action) return;
    if (action === 'submit') setResult({ ...visibleResult, ...await submit.mutateAsync({ versionId: visibleResult.id, studyId: visibleResult.study_id, reason }), samples: visibleResult.samples });
    else if (action === 'approve') {
      const limit = await approve.mutateAsync({ versionId: visibleResult.id, studyId: visibleResult.study_id, reason });
      setResult({ ...visibleResult, status: 'active', limit_versions: [{ ...limit, events: limit.events ?? [] }] });
    } else if (action === 'approve-research') setResult({ ...visibleResult, ...await approveResearch.mutateAsync({ versionId: visibleResult.id, studyId: visibleResult.study_id, reason }), samples: visibleResult.samples });
    else if (action === 'reject') setResult({ ...visibleResult, ...await reject.mutateAsync({ versionId: visibleResult.id, studyId: visibleResult.study_id, reason }), samples: visibleResult.samples });
    else if (action === 'retire') {
      const activeLimit = visibleResult.limit_versions?.find(limit => limit.status === 'active');
      if (!activeLimit) return;
      await retire.mutateAsync({ limitId: activeLimit.id, studyId: visibleResult.study_id, reason });
      setResult({ ...visibleResult, status: 'retired' });
    }
    setAction(null);
  };

  const actionPending = submit.isPending || approve.isPending || approveResearch.isPending || reject.isPending || retire.isPending;
  const machineResult = visibleResult && isMachinePerformanceResult(visibleResult.capability) ? visibleResult.capability : null;

  return <div className="container-fluid py-4">
    <div className="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4"><div><div className="text-uppercase small text-muted">受控分析工作區 · 方法 2026.2</div><h1 className="h3 mb-1">進階 SPC 分析</h1><p className="text-muted mb-0">屬性圖與固定巡檢機台績效研究均保存不可變條件、證據與版本。</p></div><Badge bg="primary">方法版本 2026.2</Badge></div>
    <Card className="mb-3"><Card.Body>
      <div className="d-flex gap-2 mb-3" role="tablist" aria-label="進階 SPC 工作區"><Button type="button" role="tab" aria-selected={query.family === 'attribute'} variant={query.family === 'attribute' ? 'primary' : 'outline-primary'} onClick={() => changeFamily('attribute')}>屬性管制圖</Button><Button type="button" role="tab" aria-selected={query.family === 'machine'} variant={query.family === 'machine' ? 'primary' : 'outline-primary'} onClick={() => changeFamily('machine')}>機器績效</Button></div>
      {query.family === 'attribute' ? <Form aria-label="進階 SPC 屬性研究條件"><Row className="g-3">
        <Col md={3}><Form.Label>分析族別</Form.Label><Form.Select aria-label="分析族別" value="attribute" disabled><option value="attribute">屬性分析（p／np）</option></Form.Select></Col>
        <Col md={3}><Form.Label>資料來源</Form.Label><Form.Select aria-label="資料來源" value={query.source} onChange={event => updateQuery({ ...query, source: event.target.value as Source })}><option value="shipping">出貨檢驗</option><option value="patrol">現場巡檢</option></Form.Select></Col>
        <Col md={3}><Form.Label>子組區間</Form.Label><Form.Select aria-label="子組區間" value={query.interval} onChange={event => updateQuery({ ...query, interval: event.target.value as Interval })}><option value="day">每日</option><option value="week">每週</option><option value="month">每月</option></Form.Select></Col>
        <Col md={3}><Form.Label>圖表類型</Form.Label><Form.Select aria-label="圖表類型" value={query.chartType} onChange={event => updateQuery({ ...query, chartType: event.target.value as AttributeChartType })}><option value="p">p 圖（子組大小可變）</option><option value="np">np 圖（固定子組大小）</option></Form.Select></Col>
        {query.source === 'shipping' ? <><Col md={3}><Form.Label>廠商</Form.Label><Form.Control aria-label="廠商" value={query.filters.vendor} onChange={event => setFilter('vendor', event.target.value)} /></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col><Col md={2}><Form.Label>檢驗特性</Form.Label><Form.Control aria-label="檢驗特性" value={query.filters.item} onChange={event => setFilter('item', event.target.value)} /></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.start_date} onChange={event => setFilter('start_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.end_date} onChange={event => setFilter('end_date', event.target.value)} /></Col></> : <><Col md={2}><Form.Label>客戶 ID</Form.Label><Form.Control aria-label="客戶 ID" inputMode="numeric" value={query.filters.customer} onChange={event => setFilter('customer', event.target.value)} /></Col><Col md={2}><Form.Label>機台 ID</Form.Label><Form.Control aria-label="機台 ID" inputMode="numeric" value={query.filters.m_id} onChange={event => setFilter('m_id', event.target.value)} /></Col><Col md={2}><Form.Label>操作員 ID</Form.Label><Form.Control aria-label="操作員 ID" inputMode="numeric" value={query.filters.op_id} onChange={event => setFilter('op_id', event.target.value)} /></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col><Col md={2}><Form.Label>項目</Form.Label><Form.Control aria-label="項目" value={query.filters.item} onChange={event => setFilter('item', event.target.value)} /></Col><Col md={3}><Form.Label>位置</Form.Label><Form.Control aria-label="位置" value={query.filters.position} onChange={event => setFilter('position', event.target.value)} /></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.s_date} onChange={event => setFilter('s_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.e_date} onChange={event => setFilter('e_date', event.target.value)} /></Col></>}
      </Row><div className="d-flex justify-content-end mt-3"><Button type="button" onClick={() => void analyzeAttribute()} disabled={!canView || analyze.isPending}>{analyze.isPending ? '分析中…' : '建立屬性研究'}</Button></div></Form> : <><div className="mb-3"><Form.Label>分析族別</Form.Label><Form.Select aria-label="分析族別" value="machine" disabled><option value="machine">機器績效（Pm／Pmk）</option></Form.Select><Form.Text>資料來源固定為現場巡檢；出貨資料不可用於機器績效研究。</Form.Text></div><MachineConditionForm value={machineValue} onChange={setMachineValue} onAnalyze={request => void analyzeMachine(request)} disabled={!canView || analyze.isPending} disabledReason={!canView ? '目前帳號沒有 SPC 檢視權限。' : analyze.isPending ? '分析執行中。' : undefined} /></>}
      {!canView && <Alert variant="warning" className="mt-3 mb-0">目前帳號沒有 SPC 檢視權限，無法送出分析。</Alert>}
      {analyze.isError && <Alert variant="danger" className="mt-3 mb-0">API 驗證或分析失敗：{apiError(analyze.error)}</Alert>}
    </Card.Body></Card>
    {visibleResult && <Card className="mb-3"><Card.Body><SpcStudyWorkflowBar version={visibleResult} canView={canView} canManage={canManage} canApprove={canApprove} analyzing={analyze.isPending} onAnalyze={() => void (query.family === 'machine' ? analyzeMachine({ filters: { m_id: Number(machineValue.m_id), mat: machineValue.mat.trim(), spec: machineValue.spec.trim(), item: machineValue.item.trim(), pos: machineValue.pos.trim() }, options: { conditions_confirmed: machineValue.conditions_confirmed, condition_reason: machineValue.condition_reason.trim() } }) : analyzeAttribute())} onAction={setAction} onShowHistory={() => setShowHistory(true)} /></Card.Body></Card>}
    {query.family === 'machine' ? <MachinePerformancePanel result={machineResult} /> : <AttributeStudyPanel result={visibleResult} />}
    {visibleResult && action && <SpcBaselineApprovalModal show action={action} source={visibleResult.source} filters={visibleResult.filters} version={visibleResult} pending={actionPending} onHide={() => setAction(null)} onConfirm={reason => void handleAction(reason)} />}
    {visibleResult && showHistory && <SpcStudyHistoryOffcanvas show studyId={visibleResult.study_id} onHide={() => setShowHistory(false)} />}
  </div>;
};

export default AdvancedSpcPage;
