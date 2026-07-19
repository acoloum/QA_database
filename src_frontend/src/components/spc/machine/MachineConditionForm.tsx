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
}

const MachineConditionForm = ({ value, onChange, onAnalyze, disabled, disabledReason }: MachineConditionFormProps) => {
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
      <Col md={3}><Form.Label>機台 ID</Form.Label><Form.Control aria-label="機台 ID" inputMode="numeric" value={value.m_id} onChange={event => update('m_id', event.target.value.replace(/\D/g, ''))} /></Col>
      <Col md={2}><Form.Label>材質</Form.Label><Form.Control aria-label="材質" value={value.mat} onChange={event => update('mat', event.target.value.slice(0, 120))} /></Col>
      <Col md={2}><Form.Label>規格</Form.Label><Form.Control aria-label="規格" value={value.spec} onChange={event => update('spec', event.target.value.slice(0, 120))} /></Col>
      <Col md={2}><Form.Label>項目</Form.Label><Form.Control aria-label="項目" value={value.item} onChange={event => update('item', event.target.value.slice(0, 120))} /></Col>
      <Col md={3}><Form.Label>位置</Form.Label><Form.Control aria-label="位置" value={value.pos} onChange={event => update('pos', event.target.value.slice(0, 120))} /></Col>
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
