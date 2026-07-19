import { Alert, Badge, Card, Table } from 'react-bootstrap';
import type { SpcAttributeChartData, SpcStudyResult } from '../../../types';
import AttributeControlChart from './AttributeControlChart';

interface AttributeStudyPanelProps {
  result: SpcStudyResult | null;
}

const asAttributeChart = (value: unknown): SpcAttributeChartData | null => {
  if (!value || typeof value !== 'object') return null;
  const chart = value as Partial<SpcAttributeChartData>;
  if (
    (chart.chart_type !== 'p' && chart.chart_type !== 'np')
    || !Array.isArray(chart.values) || !Array.isArray(chart.cl)
    || !Array.isArray(chart.ucl) || !Array.isArray(chart.lcl)
    || !Array.isArray(chart.n) || !Array.isArray(chart.x)
    || chart.values.length === 0 || [chart.cl, chart.ucl, chart.lcl, chart.n, chart.x]
      .some(values => values.length !== chart.values?.length)
  ) return null;
  return chart as SpcAttributeChartData;
};

const AttributeStudyPanel = ({ result }: AttributeStudyPanelProps) => {
  if (!result) return <Alert variant="light" className="mb-0">設定條件後建立屬性研究，不會以預設資料替代分析結果。</Alert>;

  const chart = asAttributeChart(result.charts);
  const reasons = result.applicability?.reasons ?? [];
  const reasonText = [
    result.applicability?.message,
    ...reasons.map(reason => reason.message),
  ].filter((value): value is string => Boolean(value));
  const eligibility = result.applicability?.eligibility ?? {};
  const excluded = typeof eligibility.excluded_record_count === 'number'
    ? eligibility.excluded_record_count
    : typeof eligibility.excluded === 'number' ? eligibility.excluded : 0;
  const warnings = chart?.warnings ?? {};
  const subgroupKeys = chart?.counts?.map(count => count.key)
    ?? result.samples?.map(sample => sample.key)
    ?? [];
  const hasTraceablePoints = Boolean(chart && subgroupKeys.length === chart.values.length);

  return (
    <Card>
      <Card.Body>
        <div className="d-flex justify-content-between gap-2 flex-wrap mb-3">
          <div>
            <h2 className="h5 mb-1">屬性管制圖</h2>
            <div className="text-muted small">研究方法版本 {result.method_version || '2026.2'}</div>
          </div>
          {chart && <Badge bg="primary">{chart.chart_type.toUpperCase()} 圖</Badge>}
        </div>

        {!result.applicability?.applicable && (
          <Alert variant="warning">
            <strong>此研究不適用，未繪製管制圖。</strong>{reasonText.length > 0 ? ` ${reasonText.join('；')}` : ''}
          </Alert>
        )}
        {result.applicability?.applicable && (!chart || !hasTraceablePoints) && (
          <Alert variant="danger">分析回傳缺少可驗證的逐點界限、計數或子組鍵，未繪製圖表。</Alert>
        )}
        {warnings.sample_size_variation && <Alert variant="warning">子組大小差異達警示門檻；p 圖仍以每一子組的精確界限呈現。</Alert>}
        {excluded > 0 && <Alert variant="secondary">已排除 {excluded} 筆無法判定符合性的資料</Alert>}
        {chart && hasTraceablePoints && result.applicability?.applicable && <AttributeControlChart chart={chart} subgroupKeys={subgroupKeys} />}

        {chart && hasTraceablePoints && (
          <Table responsive size="sm" className="mt-3 mb-0" aria-label="屬性子組證據">
            <thead><tr><th>子組鍵</th><th>x</th><th>n</th><th>比例</th><th>CL</th><th>LCL</th><th>UCL</th></tr></thead>
            <tbody>
              {chart.values.map((_value, index) => {
                const count = chart.counts?.[index];
                const inspected = count?.inspected ?? chart.n[index];
                const nonconforming = count?.nonconforming ?? chart.x[index];
                const proportion = count?.proportion ?? nonconforming / inspected;
                return <tr key={subgroupKeys[index]}>
                  <td>{subgroupKeys[index]}</td><td>{nonconforming}</td><td>{inspected}</td>
                  <td>{proportion.toFixed(4)}</td><td>{chart.cl[index]?.toFixed(4)}</td>
                  <td>{chart.lcl[index]?.toFixed(4)}</td><td>{chart.ucl[index]?.toFixed(4)}</td>
                </tr>;
              })}
            </tbody>
          </Table>
        )}
      </Card.Body>
    </Card>
  );
};

export default AttributeStudyPanel;
