import { Button, Col, Form, Row } from 'react-bootstrap';
import {
  buildMachineStudyRequest, hasFixedMachineStream, hasValidMachineConditions,
  type MachineConditionInput, type MachineStudyRequest,
} from './machineStudyRequest';

interface MachineConditionFormProps {
  value: MachineConditionInput;
  onChange: (next: MachineConditionInput) => void;
  onAnalyze: (request: MachineStudyRequest) => void;
  disabled: boolean;
  disabledReason?: string;
  machines?: { id: number; name: string }[];
}

// 巡檢可分析的量測項目與位置（與 PatrolCharts / AdvancedSpcPage 一致）
const ITEMS = ['外徑', '內徑', '厚度'];
const POSITIONS = ['前段', '中段', '後段'];

// 固定清單一律納入目前值，讓深連結帶入、但不在清單中的值仍能正確顯示
const withCurrent = (current: string, values: string[]) =>
  current && !values.includes(current) ? [current, ...values] : values;

// 機台下拉：以 id 為值、名稱為顯示；目前值不在清單時補為選項
const machineSelectOptions = (current: string, list?: { id: number; name: string }[]) => {
  const options = (list ?? []).map(machine => ({ value: String(machine.id), label: machine.name }));
  if (current && !options.some(option => option.value === current)) {
    options.push({ value: current, label: current });
  }
  return options;
};

const MachineConditionForm = ({ value, onChange, onAnalyze, disabled, disabledReason, machines }: MachineConditionFormProps) => {
  const request = buildMachineStudyRequest(value);
  const streamFixed = hasFixedMachineStream(value);
  const requirementReason = !streamFixed
    ? '必須鎖定單一機台、材質、規格、項目與位置。'
    : !value.conditions_confirmed
      ? '必須確認研究條件已受控。'
      : !hasValidMachineConditions(value)
        ? '研究條件理由必須為 2 至 500 個字元。'
        : disabledReason ?? '';
  const canAnalyze = request != null && !disabled;

  const update = <K extends keyof MachineConditionInput>(key: K, next: MachineConditionInput[K]) =>
    onChange({ ...value, [key]: next });

  return <Form aria-label="機器績效研究條件">
    <Row className="g-3">
      <Col md={3}><Form.Label>機台 ID</Form.Label><Form.Select aria-label="機台 ID" value={value.m_id} onChange={event => update('m_id', event.target.value)}><option value="">請選擇機台</option>{machineSelectOptions(value.m_id, machines).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</Form.Select></Col>
      <Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={value.mat} onChange={event => update('mat', event.target.value.slice(0, 120))} /></Col>
      <Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={value.spec} onChange={event => update('spec', event.target.value.slice(0, 120))} /></Col>
      <Col md={2}><Form.Label>項目</Form.Label><Form.Select aria-label="項目" value={value.item} onChange={event => update('item', event.target.value)}><option value="">請選擇項目</option>{withCurrent(value.item, ITEMS).map(name => <option key={name} value={name}>{name}</option>)}</Form.Select></Col>
      <Col md={3}><Form.Label>位置</Form.Label><Form.Select aria-label="位置" value={value.pos} onChange={event => update('pos', event.target.value)}><option value="">請選擇位置</option>{withCurrent(value.pos, POSITIONS).map(p => <option key={p} value={p}>{p}</option>)}</Form.Select></Col>
      <Col xs={12}><Form.Check id="machine-conditions-confirmed" label="已確認研究期間的機台、治具、設定與環境條件受控" checked={value.conditions_confirmed} onChange={event => update('conditions_confirmed', event.target.checked)} /></Col>
      <Col xs={12}><Form.Label>研究條件確認理由</Form.Label><Form.Control aria-label="研究條件確認理由" as="textarea" rows={3} maxLength={500} value={value.condition_reason} onChange={event => update('condition_reason', event.target.value)} /><Form.Text>必填，2 至 500 個字元；將保存於不可變研究版本。</Form.Text></Col>
    </Row>
    <div className="d-flex justify-content-end align-items-center gap-2 mt-3">
      {requirementReason && <span id="machine-analysis-disabled-reason" className="small text-muted" role="status">{requirementReason}</span>}
      <Button type="button" onClick={() => { if (request) onAnalyze(request); }} disabled={!canAnalyze} aria-describedby={!canAnalyze ? 'machine-analysis-disabled-reason' : undefined}>分析機器績效</Button>
    </div>
  </Form>;
};

export default MachineConditionForm;
