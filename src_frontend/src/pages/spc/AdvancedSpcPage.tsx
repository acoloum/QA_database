import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Alert, Badge, Button, Card, Col, Form, Row } from 'react-bootstrap';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  useAnalyzeSpcStudy, useApproveSpcResearch, useApproveSpcStudy, useRejectSpcStudy,
  useConfirmSpcTimeModel, useConfirmSpcTransformation, useRetireSpcLimit, useSubmitSpcStudy,
} from '../../hooks/useSpcStudies';
import { useVendors } from '../../hooks/useShipping';
import { usePatrolOptions } from '../../hooks/usePatrol';
import type { SpcStudyResult, SpcTimeModelCode, SpcTransformationModel } from '../../types';
import { isMachinePerformanceResult, isVariableSpcStudyResult } from '../../types/spc';
import AttributeStudyPanel from '../../components/spc/attribute/AttributeStudyPanel';
import MachineConditionForm from '../../components/spc/machine/MachineConditionForm';
import {
  buildMachineStudyRequest, type MachineConditionInput, type MachineStudyRequest,
} from '../../components/spc/machine/machineStudyRequest';
import MachinePerformancePanel from '../../components/spc/machine/MachinePerformancePanel';
import TimeDiagnosticPanel from '../../components/spc/diagnostics/TimeDiagnosticPanel';
import TransformationPanel from '../../components/spc/distribution/TransformationPanel';
import SpcBaselineApprovalModal, { type SpcWorkflowAction } from '../../components/spc/SpcBaselineApprovalModal';
import SpcStudyHistoryOffcanvas from '../../components/spc/SpcStudyHistoryOffcanvas';
import SpcStudyWorkflowBar from '../../components/spc/SpcStudyWorkflowBar';

type Source = 'shipping' | 'patrol' | 'mechanical';
type Family = 'variable' | 'attribute' | 'machine';
type Interval = 'day' | 'week' | 'month';
type AttributeChartType = 'p' | 'np';
type FilterKey = 'vendor' | 'vendor_id' | 'material' | 'product_size' | 'spec' | 'customer'
  | 'item' | 'position' | 'start_date' | 'end_date' | 's_date' | 'e_date' | 'm_id' | 'op_id';

interface AdvancedQuery {
  family: Family;
  source: Source;
  interval: Interval;
  chartType: AttributeChartType;
  filters: Record<FilterKey, string>;
  conditionsConfirmed: boolean;
}

const FILTER_KEYS: FilterKey[] = [
  'vendor', 'vendor_id', 'material', 'product_size', 'spec', 'customer', 'item', 'position',
  'start_date', 'end_date', 's_date', 'e_date', 'm_id', 'op_id',
];
const ATTRIBUTE_FILTERS = new Set<FilterKey>(FILTER_KEYS.filter(key => !['customer', 'op_id'].includes(key)));
const TEXT_LIMIT = 120;
// 出貨檢驗可分析的量測特性（需與資料庫 ShippingMeasurement.量測項目 一致）
const SHIPPING_CHARACTERISTICS = [
  '外徑', '內徑', '厚度', '長度', '同心度', '真圓度', '真直度', '硬度', '韋伯氏硬度',
];
// 巡檢可分析的量測項目與量測位置（與巡檢頁面 PatrolCharts 一致）
const PATROL_ITEMS = ['外徑', '內徑', '厚度'];
const PATROL_POSITIONS = ['前段', '中段', '後段'];
// 機械性質可分析的力學特性與量測位置（EC 值不納入 SPC；爐門/爐頂分開監控）
const MECHANICAL_CHARACTERISTICS = ['硬度', '抗拉強度', '降伏強度', '伸長率'];
const MECHANICAL_POSITIONS = ['爐門', '爐頂'];

// 固定清單下拉：一律納入目前值，讓深連結帶入、但不在清單中的值仍能正確顯示
const withCurrent = (current: string, values: string[]) =>
  current && !values.includes(current) ? [current, ...values] : values;

// ID 型下拉（客戶/機台/操作員）：以 id 為值、名稱為顯示；目前值不在清單時補為選項
const idSelectOptions = (current: string, list?: { id: number; name: string }[]) => {
  const options = (list ?? []).map(item => ({ value: String(item.id), label: item.name }));
  if (current && !options.some(option => option.value === current)) {
    options.push({ value: current, label: current });
  }
  return options;
};
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const NUMBER_FILTERS = new Set<FilterKey>(['customer', 'm_id', 'op_id', 'vendor_id']);
const DATE_FILTERS = new Set<FilterKey>(['start_date', 'end_date', 's_date', 'e_date']);

const safeText = (value: string | null) => (value ?? '').trim().slice(0, TEXT_LIMIT);
const safeInteger = (value: string | null) => /^\d+$/.test(value ?? '') ? value as string : '';
const safeDate = (value: string | null) => DATE_PATTERN.test(value ?? '') ? value as string : '';
const safeFilter = (key: FilterKey, value: string | null) => NUMBER_FILTERS.has(key)
  ? safeInteger(value) : DATE_FILTERS.has(key) ? safeDate(value) : safeText(value);

const parseQuery = (search: URLSearchParams): AdvancedQuery => {
  const requestedFamily = search.get('family');
  const family: Family = requestedFamily === 'machine' ? 'machine' : requestedFamily === 'variable' ? 'variable' : 'attribute';
  const requestedSource = search.get('source');
  // 機械性質僅支援變數分析；機器績效固定巡檢；屬性僅出貨/巡檢。
  const source: Source = family === 'machine' ? 'patrol'
    : family === 'variable' && requestedSource === 'mechanical' ? 'mechanical'
    : requestedSource === 'patrol' ? 'patrol' : 'shipping';
  const filters = FILTER_KEYS.reduce<Record<FilterKey, string>>((result, key) => {
    const aliases: Partial<Record<FilterKey, string[]>> = {
      customer: ['cust_id'], material: ['mat'], position: ['pos'],
      start_date: [], end_date: [], s_date: ['s'], e_date: ['e'], item: ['field'],
    };
    const value = search.get(key) ?? aliases[key]?.map(alias => search.get(alias)).find(item => item != null) ?? null;
    result[key] = safeFilter(key, value);
    return result;
  }, {} as Record<FilterKey, string>);
  return {
    family, source,
    interval: ['day', 'week', 'month'].includes(search.get('interval') ?? '') ? search.get('interval') as Interval : 'day',
    chartType: ['p', 'np'].includes(search.get('chart_type') ?? '') ? search.get('chart_type') as AttributeChartType : 'p',
    filters,
    conditionsConfirmed: search.get('conditions_confirmed') === 'true',
  };
};

const queryToSearch = (query: AdvancedQuery) => {
  const params = new URLSearchParams({ family: query.family, source: query.family === 'machine' ? 'patrol' : query.source });
  if (query.family === 'machine') {
    const machineEntries: Array<[string, string]> = [
      ['m_id', query.filters.m_id], ['mat', query.filters.material],
      ['spec', query.filters.spec], ['item', query.filters.item],
      ['pos', query.filters.position], ['op_id', query.filters.op_id],
      ['cust_id', query.filters.customer], ['s_date', query.filters.s_date],
      ['e_date', query.filters.e_date],
    ];
    machineEntries.forEach(([key, value]) => { if (value) params.set(key, value); });
    if (query.conditionsConfirmed) params.set('conditions_confirmed', 'true');
  } else if (query.family === 'attribute') {
    params.set('interval', query.interval);
    params.set('chart_type', query.chartType);
    ATTRIBUTE_FILTERS.forEach(key => { if (query.filters[key]) params.set(key, query.filters[key]); });
  } else if (query.source === 'shipping') {
    const shippingEntries: Array<[string, string]> = [
      ['vendor', query.filters.vendor], ['material', query.filters.material],
      ['spec', query.filters.spec], ['field', query.filters.item],
      ['start_date', query.filters.start_date], ['end_date', query.filters.end_date],
    ];
    shippingEntries.forEach(([key, value]) => { if (value) params.set(key, value); });
  } else if (query.source === 'mechanical') {
    const mechanicalEntries: Array<[string, string]> = [
      ['vendor_id', query.filters.vendor_id], ['material', query.filters.material],
      ['product_size', query.filters.product_size], ['item', query.filters.item],
      ['position', query.filters.position],
      ['start_date', query.filters.start_date], ['end_date', query.filters.end_date],
    ];
    mechanicalEntries.forEach(([key, value]) => { if (value) params.set(key, value); });
  } else {
    const patrolEntries: Array<[string, string]> = [
      ['m_id', query.filters.m_id], ['op_id', query.filters.op_id],
      ['cust_id', query.filters.customer], ['mat', query.filters.material],
      ['spec', query.filters.spec], ['item', query.filters.item],
      ['pos', query.filters.position], ['s', query.filters.s_date], ['e', query.filters.e_date],
    ];
    patrolEntries.forEach(([key, value]) => { if (value) params.set(key, value); });
  }
  return params.toString();
};

interface ApiErrorDetail {
  status: number | null;
  code: string | null;
  message: string;
}

const apiError = (error: unknown): ApiErrorDetail => {
  const response = error as { response?: { status?: number; data?: { code?: string; message?: string; error?: string } }; message?: string };
  return {
    status: response.response?.status ?? null,
    code: response.response?.data?.code ?? null,
    message: response.response?.data?.message ?? response.response?.data?.error ?? response.message ?? '無法建立研究，請確認篩選條件與資料可用性。',
  };
};

const AdvancedSpcPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = parseQuery(searchParams);
  const [result, setResult] = useState<SpcStudyResult | null>(null);
  const [action, setAction] = useState<SpcWorkflowAction | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [machineConditionReason, setMachineConditionReason] = useState({ family: '' as Family | '', value: '' });
  const [actionError, setActionError] = useState<ApiErrorDetail | null>(null);
  const queryClient = useQueryClient();
  const { hasPermission } = useAuth();
  const vendorsQuery = useVendors();
  // 一律納入目前值作為選項，讓深連結帶入、但不在清單中的廠商仍能正確顯示
  const vendorOptions = Array.from(new Set(
    [query.filters.vendor, ...(vendorsQuery.data?.map(v => v.name) ?? [])].filter(Boolean),
  ));
  const patrolOptionsQuery = usePatrolOptions();
  const patrolOpts = patrolOptionsQuery.data;
  const customerOptions = idSelectOptions(query.filters.customer, patrolOpts?.customers);
  const machineOptions = idSelectOptions(query.filters.m_id, patrolOpts?.machines);
  const operatorOptions = idSelectOptions(query.filters.op_id, patrolOpts?.operators);
  const analyze = useAnalyzeSpcStudy();
  const submit = useSubmitSpcStudy();
  const approve = useApproveSpcStudy();
  const approveResearch = useApproveSpcResearch();
  const confirmTimeModel = useConfirmSpcTimeModel();
  const confirmTransformation = useConfirmSpcTransformation();
  const reject = useRejectSpcStudy();
  const retire = useRetireSpcLimit();
  const canView = hasPermission('spc.view');
  const canManage = hasPermission('spc.manage');
  const canApprove = hasPermission('spc.approve');
  const visibleResult = result?.analysis_family === query.family ? result : null;
  const machineCanManage = canManage;

  const updateQuery = (next: AdvancedQuery) => setSearchParams(new URLSearchParams(queryToSearch(next)));
  const changeFamily = (family: Family) => {
    setResult(null);
    setAction(null);
    setActionError(null);
    setShowHistory(false);
    setMachineConditionReason({ family: '', value: '' });
    updateQuery(family === 'machine'
      ? { ...query, family, source: 'patrol', filters: FILTER_KEYS.reduce((value, key) => ({ ...value, [key]: '' }), {} as Record<FilterKey, string>), conditionsConfirmed: false }
      : { ...query, family, source: 'shipping', filters: FILTER_KEYS.reduce((value, key) => ({ ...value, [key]: '' }), {} as Record<FilterKey, string>), conditionsConfirmed: false });
  };
  const setFilter = (key: FilterKey, value: string) => updateQuery({ ...query, filters: { ...query.filters, [key]: safeFilter(key, value) } });
  const machineValue: MachineConditionInput = {
    m_id: query.filters.m_id, mat: query.filters.material, spec: query.filters.spec,
    item: query.filters.item, pos: query.filters.position,
    conditions_confirmed: query.conditionsConfirmed,
    condition_reason: machineConditionReason.family === query.family ? machineConditionReason.value : '',
  };
  const setMachineValue = (next: MachineConditionInput) => {
    setMachineConditionReason({ family: query.family, value: next.condition_reason });
    updateQuery({
      ...query, filters: { ...query.filters, m_id: next.m_id, material: next.mat, spec: next.spec, item: next.item, position: next.pos },
      conditionsConfirmed: next.conditions_confirmed,
    });
  };
  const attributeFilters = (): Record<string, unknown> => query.source === 'shipping'
    ? { vendor: query.filters.vendor, material: query.filters.material, spec: query.filters.spec, field: query.filters.item || '外徑', start_date: query.filters.start_date, end_date: query.filters.end_date }
    : { cust_id: query.filters.customer || null, mat: query.filters.material, spec: query.filters.spec, item: query.filters.item || '厚度', pos: query.filters.position, s_date: query.filters.s_date, e_date: query.filters.e_date, m_id: query.filters.m_id || null, op_id: query.filters.op_id || null };
  const variableFilters = (): Record<string, unknown> => query.source === 'shipping'
    ? { vendor: query.filters.vendor, material: query.filters.material, spec: query.filters.spec, field: query.filters.item || '外徑', start_date: query.filters.start_date, end_date: query.filters.end_date }
    : query.source === 'mechanical'
    ? { vendor_id: query.filters.vendor_id || null, material: query.filters.material, product_size: query.filters.product_size, item: query.filters.item || '抗拉強度', position: query.filters.position || '爐門', start_date: query.filters.start_date, end_date: query.filters.end_date }
    : { cust_id: query.filters.customer || null, mat: query.filters.material, spec: query.filters.spec, item: query.filters.item || '厚度', pos: query.filters.position, s_date: query.filters.s_date, e_date: query.filters.e_date, m_id: query.filters.m_id || null, op_id: query.filters.op_id || null };
  const analyzeAttribute = async () => {
    setActionError(null);
    setResult(await analyze.mutateAsync({ source: query.source, filters: attributeFilters(), analysis_family: 'attribute', options: { interval: query.interval, chart_type: query.chartType } }));
  };
  const analyzeVariable = async () => {
    setActionError(null);
    setResult(await analyze.mutateAsync({ source: query.source, filters: variableFilters(), analysis_family: 'variable' }));
  };
  const machineRequest = buildMachineStudyRequest(machineValue);
  const analyzeMachine = async (request: MachineStudyRequest | null = machineRequest) => {
    if (!request || !machineCanManage) return;
    setActionError(null);
    setResult(await analyze.mutateAsync({ source: 'patrol', analysis_family: 'machine', ...request }));
  };

  const refreshWorkflowQueries = async (studyId: number) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['spcStudies'] }),
      queryClient.invalidateQueries({ queryKey: ['spcStudy', studyId] }),
      queryClient.invalidateQueries({ queryKey: ['spcStudyHistory', studyId] }),
    ]);
    await Promise.all([
      queryClient.refetchQueries({ queryKey: ['spcStudy', studyId] }),
      queryClient.refetchQueries({ queryKey: ['spcStudyHistory', studyId] }),
    ]);
  };

  const handleAction = async (reason: string, model?: 'A1' | 'A2') => {
    if (!visibleResult || !action) return;
    setActionError(null);
    try {
      if (action === 'time-model' && model) setResult({ ...visibleResult, ...await confirmTimeModel.mutateAsync({ versionId: visibleResult.id, studyId: visibleResult.study_id, model, reason }), samples: visibleResult.samples });
      else if (action === 'submit') setResult({ ...visibleResult, ...await submit.mutateAsync({ versionId: visibleResult.id, studyId: visibleResult.study_id, reason }), samples: visibleResult.samples });
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
    } catch (error) {
      const parsed = apiError(error);
      setActionError(parsed);
      if (parsed.status === 403 || parsed.status === 409) {
        const studyId = visibleResult.study_id;
        setAction(null);
        setResult(null);
        await refreshWorkflowQueries(studyId);
      }
      return;
    }
  };

  const handleSuccessorError = async (error: unknown, studyId: number) => {
    const parsed = apiError(error);
    setActionError(parsed);
    if (parsed.status === 403 || parsed.status === 409) {
      setResult(null);
      await refreshWorkflowQueries(studyId);
    }
  };

  const confirmDiagnostic = async (model: SpcTimeModelCode, reason: string) => {
    if (!visibleResult || query.family !== 'variable') return;
    const current = visibleResult;
    setActionError(null);
    try {
      const successor = await confirmTimeModel.mutateAsync({
        versionId: current.id, studyId: current.study_id, model, reason,
      });
      setResult(value => value?.id === current.id
        ? { ...value, ...successor, samples: value.samples } : value);
    } catch (error) {
      await handleSuccessorError(error, current.study_id);
    }
  };

  const confirmDistribution = async (model: SpcTransformationModel, reason: string) => {
    if (!visibleResult || query.family !== 'variable') return;
    const current = visibleResult;
    setActionError(null);
    try {
      const successor = await confirmTransformation.mutateAsync({
        versionId: current.id, studyId: current.study_id, model, reason,
      });
      setResult(value => value?.id === current.id
        ? { ...value, ...successor, samples: value.samples } : value);
    } catch (error) {
      await handleSuccessorError(error, current.study_id);
    }
  };

  const actionPending = submit.isPending || approve.isPending || approveResearch.isPending || reject.isPending || retire.isPending || confirmTimeModel.isPending || confirmTransformation.isPending;
  const machineResult = visibleResult && isMachinePerformanceResult(visibleResult.capability) ? visibleResult.capability : null;
  const variableResult = isVariableSpcStudyResult(visibleResult) ? visibleResult : null;

  return <div className="container-fluid py-4">
    <div className="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4"><div><div className="text-uppercase small text-muted">受控分析工作區 · 方法 2026.2</div><h1 className="h3 mb-1">進階 SPC 分析</h1><p className="text-muted mb-0">屬性圖、機器績效、時間診斷與分布轉換均保存不可變條件、證據與版本。</p></div><Badge bg="primary">方法版本 2026.2</Badge></div>
    <Card className="mb-3"><Card.Body>
      <div className="d-flex gap-2 mb-3 flex-wrap" role="tablist" aria-label="進階 SPC 工作區"><Button id="advanced-spc-variable-tab" type="button" role="tab" aria-controls="advanced-spc-workspace" aria-selected={query.family === 'variable'} variant={query.family === 'variable' ? 'primary' : 'outline-primary'} onClick={() => changeFamily('variable')}>變數診斷與轉換</Button><Button id="advanced-spc-attribute-tab" type="button" role="tab" aria-controls="advanced-spc-workspace" aria-selected={query.family === 'attribute'} variant={query.family === 'attribute' ? 'primary' : 'outline-primary'} onClick={() => changeFamily('attribute')}>屬性管制圖</Button><Button id="advanced-spc-machine-tab" type="button" role="tab" aria-controls="advanced-spc-workspace" aria-selected={query.family === 'machine'} variant={query.family === 'machine' ? 'primary' : 'outline-primary'} onClick={() => changeFamily('machine')}>機器績效</Button></div>
      <div id="advanced-spc-workspace" role="tabpanel" aria-labelledby={`advanced-spc-${query.family}-tab`}>
      {query.family === 'attribute' ? <Form aria-label="進階 SPC 屬性研究條件"><Row className="g-3">
        <Col md={3}><Form.Label>分析族別</Form.Label><Form.Select aria-label="分析族別" value="attribute" disabled><option value="attribute">屬性分析（p／np）</option></Form.Select></Col>
        <Col md={3}><Form.Label>資料來源</Form.Label><Form.Select aria-label="資料來源" value={query.source} onChange={event => updateQuery({ ...query, source: event.target.value as Source })}><option value="shipping">出貨檢驗</option><option value="patrol">現場巡檢</option></Form.Select></Col>
        <Col md={3}><Form.Label>子組區間</Form.Label><Form.Select aria-label="子組區間" value={query.interval} onChange={event => updateQuery({ ...query, interval: event.target.value as Interval })}><option value="day">每日</option><option value="week">每週</option><option value="month">每月</option></Form.Select></Col>
        <Col md={3}><Form.Label>圖表類型</Form.Label><Form.Select aria-label="圖表類型" value={query.chartType} onChange={event => updateQuery({ ...query, chartType: event.target.value as AttributeChartType })}><option value="p">p 圖（子組大小可變）</option><option value="np">np 圖（固定子組大小）</option></Form.Select></Col>
        {query.source === 'mechanical' ? <><Col md={3}><Form.Label>廠商</Form.Label><Form.Select aria-label="廠商" value={query.filters.vendor_id} onChange={event => setFilter('vendor_id', event.target.value)}><option value="">不限廠商</option>{idSelectOptions(query.filters.vendor_id, vendorsQuery.data).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>產品尺寸</Form.Label><Form.Control aria-label="產品尺寸" value={query.filters.product_size} onChange={event => setFilter('product_size', event.target.value)} /></Col><Col md={2}><Form.Label>特性</Form.Label><Form.Select aria-label="特性" value={query.filters.item || '抗拉強度'} onChange={event => setFilter('item', event.target.value)}>{MECHANICAL_CHARACTERISTICS.map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={3}><Form.Label>位置</Form.Label><Form.Select aria-label="位置" value={query.filters.position || '爐門'} onChange={event => setFilter('position', event.target.value)}>{MECHANICAL_POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}</Form.Select></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.start_date} onChange={event => setFilter('start_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.end_date} onChange={event => setFilter('end_date', event.target.value)} /></Col></> : query.source === 'shipping' ? <><Col md={3}><Form.Label>廠商</Form.Label><Form.Select aria-label="廠商" value={query.filters.vendor} onChange={event => setFilter('vendor', event.target.value)}><option value="">不限廠商</option>{vendorOptions.map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col><Col md={2}><Form.Label>檢驗特性</Form.Label><Form.Select aria-label="檢驗特性" value={query.filters.item || '外徑'} onChange={event => setFilter('item', event.target.value)}>{SHIPPING_CHARACTERISTICS.map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.start_date} onChange={event => setFilter('start_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.end_date} onChange={event => setFilter('end_date', event.target.value)} /></Col></> : <><Col md={2}><Form.Label>客戶 ID</Form.Label><Form.Select aria-label="客戶 ID" value={query.filters.customer} onChange={event => setFilter('customer', event.target.value)}><option value="">不限客戶</option>{customerOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>機台 ID</Form.Label><Form.Select aria-label="機台 ID" value={query.filters.m_id} onChange={event => setFilter('m_id', event.target.value)}><option value="">不限機台</option>{machineOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>操作員 ID</Form.Label><Form.Select aria-label="操作員 ID" value={query.filters.op_id} onChange={event => setFilter('op_id', event.target.value)}><option value="">不限操作員</option>{operatorOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col><Col md={2}><Form.Label>項目</Form.Label><Form.Select aria-label="項目" value={query.filters.item || '厚度'} onChange={event => setFilter('item', event.target.value)}>{withCurrent(query.filters.item, PATROL_ITEMS).map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={3}><Form.Label>位置</Form.Label><Form.Select aria-label="位置" value={query.filters.position || '前段'} onChange={event => setFilter('position', event.target.value)}>{withCurrent(query.filters.position, PATROL_POSITIONS).map(p => <option key={p} value={p}>{p}</option>)}</Form.Select></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.s_date} onChange={event => setFilter('s_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.e_date} onChange={event => setFilter('e_date', event.target.value)} /></Col></>}
      </Row><div className="d-flex justify-content-end mt-3"><Button type="button" onClick={() => void analyzeAttribute()} disabled={!canView || analyze.isPending}>{analyze.isPending ? '分析中…' : '建立屬性研究'}</Button></div></Form> : query.family === 'variable' ? <Form aria-label="進階 SPC 變數研究條件"><Row className="g-3">
        <Col md={3}><Form.Label>分析族別</Form.Label><Form.Select aria-label="分析族別" value="variable" disabled><option value="variable">變數分析（時間／分布）</option></Form.Select></Col>
        <Col md={3}><Form.Label>資料來源</Form.Label><Form.Select aria-label="資料來源" value={query.source} onChange={event => updateQuery({ ...query, source: event.target.value as Source })}><option value="shipping">出貨檢驗</option><option value="patrol">現場巡檢</option><option value="mechanical">機械性質</option></Form.Select></Col>
        {query.source === 'mechanical' ? <><Col md={3}><Form.Label>廠商</Form.Label><Form.Select aria-label="廠商" value={query.filters.vendor_id} onChange={event => setFilter('vendor_id', event.target.value)}><option value="">不限廠商</option>{idSelectOptions(query.filters.vendor_id, vendorsQuery.data).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>產品尺寸</Form.Label><Form.Control aria-label="產品尺寸" value={query.filters.product_size} onChange={event => setFilter('product_size', event.target.value)} /></Col><Col md={2}><Form.Label>特性</Form.Label><Form.Select aria-label="特性" value={query.filters.item || '抗拉強度'} onChange={event => setFilter('item', event.target.value)}>{MECHANICAL_CHARACTERISTICS.map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={3}><Form.Label>位置</Form.Label><Form.Select aria-label="位置" value={query.filters.position || '爐門'} onChange={event => setFilter('position', event.target.value)}>{MECHANICAL_POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}</Form.Select></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.start_date} onChange={event => setFilter('start_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.end_date} onChange={event => setFilter('end_date', event.target.value)} /></Col></> : query.source === 'shipping' ? <><Col md={3}><Form.Label>廠商</Form.Label><Form.Select aria-label="廠商" value={query.filters.vendor} onChange={event => setFilter('vendor', event.target.value)}><option value="">不限廠商</option>{vendorOptions.map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col><Col md={2}><Form.Label>檢驗特性</Form.Label><Form.Select aria-label="檢驗特性" value={query.filters.item || '外徑'} onChange={event => setFilter('item', event.target.value)}>{SHIPPING_CHARACTERISTICS.map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.start_date} onChange={event => setFilter('start_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.end_date} onChange={event => setFilter('end_date', event.target.value)} /></Col></> : <><Col md={2}><Form.Label>客戶 ID</Form.Label><Form.Select aria-label="客戶 ID" value={query.filters.customer} onChange={event => setFilter('customer', event.target.value)}><option value="">不限客戶</option>{customerOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>機台 ID</Form.Label><Form.Select aria-label="機台 ID" value={query.filters.m_id} onChange={event => setFilter('m_id', event.target.value)}><option value="">不限機台</option>{machineOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>操作員 ID</Form.Label><Form.Select aria-label="操作員 ID" value={query.filters.op_id} onChange={event => setFilter('op_id', event.target.value)}><option value="">不限操作員</option>{operatorOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col><Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col><Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col><Col md={2}><Form.Label>項目</Form.Label><Form.Select aria-label="項目" value={query.filters.item || '厚度'} onChange={event => setFilter('item', event.target.value)}>{withCurrent(query.filters.item, PATROL_ITEMS).map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col><Col md={3}><Form.Label>位置</Form.Label><Form.Select aria-label="位置" value={query.filters.position || '前段'} onChange={event => setFilter('position', event.target.value)}>{withCurrent(query.filters.position, PATROL_POSITIONS).map(p => <option key={p} value={p}>{p}</option>)}</Form.Select></Col><Col md={3}><Form.Label>開始日期</Form.Label><Form.Control aria-label="開始日期" type="date" value={query.filters.s_date} onChange={event => setFilter('s_date', event.target.value)} /></Col><Col md={3}><Form.Label>結束日期</Form.Label><Form.Control aria-label="結束日期" type="date" value={query.filters.e_date} onChange={event => setFilter('e_date', event.target.value)} /></Col></>}
      </Row><div className="d-flex justify-content-end mt-3"><Button type="button" onClick={() => void analyzeVariable()} disabled={!canView || analyze.isPending}>{analyze.isPending ? '分析中…' : '建立變數研究'}</Button></div></Form> : <><div className="mb-3"><Form.Label>分析族別</Form.Label><Form.Select aria-label="分析族別" value="machine" disabled><option value="machine">機器績效（Pm／Pmk）</option></Form.Select><Form.Text>資料來源固定為現場巡檢；出貨資料不可用於機器績效研究。</Form.Text></div><Row className="g-2 mb-3" aria-label="巡檢來源上下文"><Col md={3}><Form.Label>來源操作員 ID</Form.Label><Form.Control aria-label="來源操作員 ID" value={query.filters.op_id} readOnly /></Col><Col md={3}><Form.Label>來源客戶 ID</Form.Label><Form.Control aria-label="來源客戶 ID" value={query.filters.customer} readOnly /></Col><Col md={3}><Form.Label>來源開始日期</Form.Label><Form.Control aria-label="來源開始日期" value={query.filters.s_date} readOnly /></Col><Col md={3}><Form.Label>來源結束日期</Form.Label><Form.Control aria-label="來源結束日期" value={query.filters.e_date} readOnly /></Col><Col xs={12}><Form.Text>以上欄位只保留深層連結的來源追溯情境，不會送入機器績效分析 API。</Form.Text></Col></Row><MachineConditionForm value={machineValue} onChange={setMachineValue} onAnalyze={request => void analyzeMachine(request)} disabled={!machineCanManage || analyze.isPending} disabledReason={!machineCanManage ? '機器研究需要 SPC 管理權限。' : analyze.isPending ? '分析執行中。' : undefined} machines={patrolOpts?.machines} /></>}
      {!canView && <Alert variant="warning" className="mt-3 mb-0">目前帳號沒有 SPC 檢視權限，無法送出分析。</Alert>}
      {analyze.isError && <Alert variant="danger" className="mt-3 mb-0">API 驗證或分析失敗：{apiError(analyze.error).message}</Alert>}
      </div>
    </Card.Body></Card>
    {actionError && <Alert variant="danger" className="mb-3" role="alert" aria-live="assertive"><strong>{actionError.status === 403 ? '權限不足：' : actionError.status === 409 ? '研究狀態已變更：' : '流程操作失敗：'}</strong>{actionError.code ? `${actionError.code}；` : ''}{actionError.message}{(actionError.status === 403 || actionError.status === 409) && <div>請重新分析或開啟版本歷程後再操作。</div>}</Alert>}
    {visibleResult && <Card className="mb-3"><Card.Body><SpcStudyWorkflowBar version={visibleResult} canView={canView} canManage={canManage} canApprove={canApprove} showTimeModelAction={query.family !== 'variable'} analyzing={analyze.isPending} canAnalyze={query.family !== 'machine' || (machineCanManage && machineRequest != null)} analyzeDisabledReason={query.family === 'machine' && machineRequest == null ? '重建候選前必須重新完成固定機台與受控條件。' : undefined} onAnalyze={() => void (query.family === 'machine' ? analyzeMachine() : query.family === 'variable' ? analyzeVariable() : analyzeAttribute())} onAction={setAction} onShowHistory={() => setShowHistory(true)} /></Card.Body></Card>}
    {query.family === 'machine' ? <MachinePerformancePanel result={machineResult} /> : query.family === 'variable' ? variableResult && <><TimeDiagnosticPanel version={variableResult} canApprove={canApprove} pending={confirmTimeModel.isPending} onConfirm={(model, reason) => void confirmDiagnostic(model, reason)} /><TransformationPanel version={variableResult} canApprove={canApprove} pending={confirmTransformation.isPending} onConfirm={(model, reason) => void confirmDistribution(model, reason)} /></> : <AttributeStudyPanel result={visibleResult} />}
    {visibleResult && action && <SpcBaselineApprovalModal show action={action} source={visibleResult.source} filters={visibleResult.filters} version={visibleResult} pending={actionPending} onHide={() => setAction(null)} onConfirm={(reason, model) => void handleAction(reason, model)} />}
    {visibleResult && showHistory && <SpcStudyHistoryOffcanvas show studyId={visibleResult.study_id} onHide={() => setShowHistory(false)} />}
  </div>;
};

export default AdvancedSpcPage;
