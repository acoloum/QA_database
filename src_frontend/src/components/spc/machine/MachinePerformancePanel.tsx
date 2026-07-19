import { Alert, Badge, Card, Table } from 'react-bootstrap';
import type { MachinePerformanceResult } from '../../../types';

interface MachinePerformancePanelProps {
  result: MachinePerformanceResult | null;
}

const value = (item: number | null) => item == null ? '—' : item.toFixed(3);
const sourceLabel = (source: string | null) => source === 'patrol_min_max_observations'
  ? '巡檢 min/max 原始觀測值' : source || '未保存來源語意';

const MachinePerformancePanel = ({ result }: MachinePerformancePanelProps) => {
  if (!result) return <Alert variant="light" className="mb-0">固定巡檢條件後建立機器績效研究；系統不會以預設資料替代結果。</Alert>;
  const { evidence, targets } = result;
  const numericalTargetsMet = result.pm != null && result.pmk != null
    && result.pm >= targets.pm && result.pmk >= targets.pmk;
  const targetMet = result.available && !result.preliminary && result.approvable
    && numericalTargetsMet;
  const dateSpan = `${evidence.date_span.start ?? '—'} ～ ${evidence.date_span.end ?? '—'}`;

  return <Card><Card.Body>
    <div className="d-flex justify-content-between gap-2 flex-wrap mb-3"><div><h2 className="h5 mb-1">機器績效研究</h2><div className="small text-muted">G 法 0.135%／50%／99.865% 分位數；僅供固定巡檢機台研究。</div></div><Badge bg={result.preliminary ? 'warning' : result.available ? 'primary' : 'secondary'} text={result.preliminary ? 'dark' : undefined}>{result.preliminary ? '初步結果' : result.available ? '可判讀結果' : '不可用結果'}</Badge></div>
    {result.reason_code && <Alert variant={result.preliminary ? 'warning' : 'secondary'}>原因碼：<code>{result.reason_code}</code>{result.preliminary && '；樣本未達 50 筆，不得宣告正式達標或核准。'}</Alert>}
    {targetMet ? <Alert variant="success">正式達標：Pm {value(result.pm)} ≥ {value(targets.pm)}，Pmk {value(result.pmk)} ≥ {value(targets.pmk)}；仍須由具核准權限者完成研究核准。</Alert> : numericalTargetsMet && !result.approvable ? <Alert variant="warning">數值達目標，但證據/資格未完成。</Alert> : <Alert variant="info">尚未宣告正式達標：必須同時具可用、非初步結果、核准資格完整，且 Pm 與 Pmk 分別達到目標。</Alert>}
    <Table responsive size="sm" aria-label="機器績效與證據"><tbody>
      <tr><th>可用性</th><td>{result.available ? '可用' : '不可用'}</td><th>有效觀測 N</th><td>{result.n}</td></tr>
      <tr><th>規格 LSL／USL</th><td>{value(result.lsl)}／{value(result.usl)}</td><th>重要度／目標</th><td>{targets.class}；Pm {value(targets.pm)}、Pmk {value(targets.pmk)}</td></tr>
      <tr><th>分位數 0.135%／50%／99.865%</th><td colSpan={3}>{value(result.quantiles.q_0_135)}／{value(result.quantiles.q_50)}／{value(result.quantiles.q_99_865)}</td></tr>
      <tr><th>Pm</th><td>Pm {value(result.pm)}／目標 {value(targets.pm)}</td><th>Pmk</th><td>Pmk {value(result.pmk)}／目標 {value(targets.pmk)}</td></tr>
      <tr><th>Pmu</th><td>{value(result.pmu)}</td><th>Pml</th><td>{value(result.pml)}</td></tr>
      <tr><th>來源觀測語意</th><td>{sourceLabel(evidence.source_semantics)} <span className="text-muted small">({evidence.source_semantics ?? '未保存'})</span></td><th>日期範圍</th><td>{dateSpan}</td></tr>
      <tr><th>實際操作者</th><td>{evidence.operators.join('、') || '未保存'}</td><th>研究條件</th><td>{evidence.conditions_confirmed ? '已確認受控' : '未確認'}；{evidence.condition_reason ?? '未保存理由'}</td></tr>
    </tbody></Table>
  </Card.Body></Card>;
};

export default MachinePerformancePanel;
