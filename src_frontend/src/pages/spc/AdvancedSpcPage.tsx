import { useState } from 'react';
import { Alert, Badge, Button, Card, Col, Form, Row } from 'react-bootstrap';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  useAnalyzeSpcStudy, useApproveSpcStudy, useRejectSpcStudy, useRetireSpcLimit,
  useSubmitSpcStudy,
} from '../../hooks/useSpcStudies';
import type { SpcStudyResult } from '../../types';
import AttributeStudyPanel from '../../components/spc/attribute/AttributeStudyPanel';
import SpcBaselineApprovalModal, { type SpcWorkflowAction } from '../../components/spc/SpcBaselineApprovalModal';
import SpcStudyHistoryOffcanvas from '../../components/spc/SpcStudyHistoryOffcanvas';
import SpcStudyWorkflowBar from '../../components/spc/SpcStudyWorkflowBar';

type Source = 'shipping' | 'patrol';
type Interval = 'day' | 'week' | 'month';
type AttributeChartType = 'p' | 'np';
type FilterKey = 'vendor' | 'material' | 'spec' | 'customer' | 'item' | 'position';

interface AttributeQuery {
  source: Source;
  family: 'attribute';
  interval: Interval;
  chartType: AttributeChartType;
  filters: Record<FilterKey, string>;
}

const FILTER_KEYS: FilterKey[] = ['vendor', 'material', 'spec', 'customer', 'item', 'position'];
const VALID_SOURCES = new Set<Source>(['shipping', 'patrol']);
const VALID_INTERVALS = new Set<Interval>(['day', 'week', 'month']);
const VALID_CHART_TYPES = new Set<AttributeChartType>(['p', 'np']);
const TEXT_LIMIT = 120;

const safeText = (value: string | null) => (value ?? '').trim().slice(0, TEXT_LIMIT);
const safeCustomer = (value: string | null) => /^\d+$/.test(value ?? '') ? value as string : '';

const parseQuery = (search: URLSearchParams): AttributeQuery => {
  const sourceCandidate = search.get('source');
  const intervalCandidate = search.get('interval');
  const chartCandidate = search.get('chart_type');
  const filters = FILTER_KEYS.reduce<Record<FilterKey, string>>((result, key) => {
    result[key] = key === 'customer' ? safeCustomer(search.get(key)) : safeText(search.get(key));
    return result;
  }, {} as Record<FilterKey, string>);
  return {
    source: VALID_SOURCES.has(sourceCandidate as Source) ? sourceCandidate as Source : 'shipping',
    family: search.get('family') === 'attribute' ? 'attribute' : 'attribute',
    interval: VALID_INTERVALS.has(intervalCandidate as Interval) ? intervalCandidate as Interval : 'day',
    chartType: VALID_CHART_TYPES.has(chartCandidate as AttributeChartType) ? chartCandidate as AttributeChartType : 'p',
    filters,
  };
};

const apiError = (error: unknown) => {
  const response = error as { response?: { data?: { message?: string } }; message?: string };
  return response.response?.data?.message ?? response.message ?? '無法建立研究，請確認篩選條件與資料可用性。';
};

const AdvancedSpcPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState<AttributeQuery>(() => parseQuery(searchParams));
  const [result, setResult] = useState<SpcStudyResult | null>(null);
  const [action, setAction] = useState<SpcWorkflowAction | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const { hasPermission } = useAuth();
  const analyze = useAnalyzeSpcStudy();
  const submit = useSubmitSpcStudy();
  const approve = useApproveSpcStudy();
  const reject = useRejectSpcStudy();
  const retire = useRetireSpcLimit();
  const canView = hasPermission('spc.view');
  const canManage = hasPermission('spc.manage');
  const canApprove = hasPermission('spc.approve');

  const updateQuery = (next: AttributeQuery) => {
    setQuery(next);
    const params = new URLSearchParams({
      family: 'attribute', source: next.source, interval: next.interval, chart_type: next.chartType,
    });
    FILTER_KEYS.forEach(key => {
      if (next.filters[key]) params.set(key, next.filters[key]);
    });
    setSearchParams(params, { replace: true });
  };

  const setFilter = (key: FilterKey, value: string) => {
    const normalized = key === 'customer' ? safeCustomer(value) : safeText(value);
    updateQuery({ ...query, filters: { ...query.filters, [key]: normalized } });
  };

  const filtersForApi = (): Record<string, unknown> => query.source === 'shipping'
    ? { vendor: query.filters.vendor, material: query.filters.material, spec: query.filters.spec, field: query.filters.item || '外徑' }
    : {
      cust_id: query.filters.customer || null, mat: query.filters.material, spec: query.filters.spec,
      item: query.filters.item || '厚度', pos: query.filters.position,
    };

  const handleAnalyze = async () => {
    const created = await analyze.mutateAsync({
      source: query.source,
      filters: filtersForApi(),
      analysis_family: 'attribute',
      options: { interval: query.interval, chart_type: query.chartType },
    });
    setResult(created);
  };

  const handleAction = async (reason: string) => {
    if (!result || !action) return;
    if (action === 'submit') {
      const updated = await submit.mutateAsync({ versionId: result.id, studyId: result.study_id, reason });
      setResult({ ...result, ...updated, samples: result.samples });
    } else if (action === 'approve') {
      const limit = await approve.mutateAsync({ versionId: result.id, studyId: result.study_id, reason });
      setResult({ ...result, status: 'active', limit_versions: [{ ...limit, events: limit.events ?? [] }] });
    } else if (action === 'reject') {
      const updated = await reject.mutateAsync({ versionId: result.id, studyId: result.study_id, reason });
      setResult({ ...result, ...updated, samples: result.samples });
    } else if (action === 'retire') {
      const activeLimit = result.limit_versions?.find(limit => limit.status === 'active');
      if (!activeLimit) return;
      await retire.mutateAsync({ limitId: activeLimit.id, studyId: result.study_id, reason });
      setResult({ ...result, status: 'retired' });
    }
    setAction(null);
  };

  const actionPending = submit.isPending || approve.isPending || reject.isPending || retire.isPending;
  const resultError = analyze.isError ? apiError(analyze.error) : null;

  return (
    <div className="container-fluid py-4">
      <div className="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4">
        <div>
          <div className="text-uppercase small text-muted">受控分析工作區 · 方法 2026.2</div>
          <h1 className="h3 mb-1">進階 SPC 分析</h1>
          <p className="text-muted mb-0">目前僅開放 p／np 屬性圖；機台能力與 BCD 轉換尚未提供分析介面。</p>
        </div>
        <Badge bg="primary">方法版本 2026.2</Badge>
      </div>

      <Card className="mb-3">
        <Card.Body>
          <Form aria-label="進階 SPC 屬性研究條件">
            <Row className="g-3">
              <Col md={3}>
                <Form.Label htmlFor="advanced-spc-family">分析族別</Form.Label>
                <Form.Select id="advanced-spc-family" aria-label="分析族別" value={query.family} disabled>
                  <option value="attribute">屬性分析（p／np）</option>
                </Form.Select>
              </Col>
              <Col md={3}>
                <Form.Label htmlFor="advanced-spc-source">資料來源</Form.Label>
                <Form.Select id="advanced-spc-source" aria-label="資料來源" value={query.source} onChange={event => updateQuery({ ...query, source: event.target.value as Source })}>
                  <option value="shipping">出貨檢驗</option><option value="patrol">現場巡檢</option>
                </Form.Select>
              </Col>
              <Col md={3}>
                <Form.Label htmlFor="advanced-spc-interval">子組區間</Form.Label>
                <Form.Select id="advanced-spc-interval" aria-label="子組區間" value={query.interval} onChange={event => updateQuery({ ...query, interval: event.target.value as Interval })}>
                  <option value="day">每日</option><option value="week">每週</option><option value="month">每月</option>
                </Form.Select>
              </Col>
              <Col md={3}>
                <Form.Label htmlFor="advanced-spc-chart-type">圖表類型</Form.Label>
                <Form.Select id="advanced-spc-chart-type" aria-label="圖表類型" value={query.chartType} onChange={event => updateQuery({ ...query, chartType: event.target.value as AttributeChartType })}>
                  <option value="p">p 圖（子組大小可變）</option><option value="np">np 圖（固定子組大小）</option>
                </Form.Select>
              </Col>
              {query.source === 'shipping' ? (
                <>
                  <Col md={4}><Form.Label>廠商</Form.Label><Form.Control aria-label="廠商" value={query.filters.vendor} onChange={event => setFilter('vendor', event.target.value)} /></Col>
                  <Col md={4}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col>
                  <Col md={4}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col>
                </>
              ) : (
                <>
                  <Col md={3}><Form.Label>客戶 ID</Form.Label><Form.Control aria-label="客戶 ID" inputMode="numeric" value={query.filters.customer} onChange={event => setFilter('customer', event.target.value)} /></Col>
                  <Col md={3}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={query.filters.material} onChange={event => setFilter('material', event.target.value)} /></Col>
                  <Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={query.filters.spec} onChange={event => setFilter('spec', event.target.value)} /></Col>
                  <Col md={2}><Form.Label>項目</Form.Label><Form.Control aria-label="項目" value={query.filters.item} onChange={event => setFilter('item', event.target.value)} /></Col>
                  <Col md={2}><Form.Label>位置</Form.Label><Form.Control aria-label="位置" value={query.filters.position} onChange={event => setFilter('position', event.target.value)} /></Col>
                </>
              )}
            </Row>
            <div className="d-flex justify-content-end mt-3">
              <Button type="button" onClick={() => void handleAnalyze()} disabled={!canView || analyze.isPending}>
                {analyze.isPending ? '分析中…' : '建立屬性研究'}
              </Button>
            </div>
          </Form>
          {!canView && <Alert variant="warning" className="mt-3 mb-0">目前帳號沒有 SPC 檢視權限，無法送出分析。</Alert>}
          {resultError && <Alert variant="danger" className="mt-3 mb-0">API 驗證或分析失敗：{resultError}</Alert>}
        </Card.Body>
      </Card>

      <div className="mb-3" aria-disabled="true"><Button variant="outline-secondary" disabled>機台能力（尚未開放）</Button>{' '}<Button variant="outline-secondary" disabled>BCD 轉換（尚未開放）</Button></div>
      {result && (
        <Card className="mb-3"><Card.Body>
          <SpcStudyWorkflowBar
            version={result} canView={canView} canManage={canManage} canApprove={canApprove}
            analyzing={analyze.isPending} onAnalyze={() => void handleAnalyze()} onAction={setAction}
            onShowHistory={() => setShowHistory(true)}
          />
        </Card.Body></Card>
      )}
      <AttributeStudyPanel result={result} />
      {result && action && <SpcBaselineApprovalModal show action={action} source={query.source} filters={filtersForApi()} version={result} pending={actionPending} onHide={() => setAction(null)} onConfirm={reason => void handleAction(reason)} />}
      {result && showHistory && <SpcStudyHistoryOffcanvas show studyId={result.study_id} onHide={() => setShowHistory(false)} />}
    </div>
  );
};

export default AdvancedSpcPage;
