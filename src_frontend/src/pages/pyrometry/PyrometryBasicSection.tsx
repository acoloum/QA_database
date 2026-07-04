import { Col, Form, Row } from 'react-bootstrap';
import type { Furnace, Inspector } from '../../types';

interface PyrometryBasicSectionProps {
  furnaces: Furnace[];
  inspectors: Inspector[];
  furnaceId: string;
  testType: 'TUS' | 'SAT';
  testDate: string;
  quarter: string;
  setpoint: string;
  tolerance: string;
  testerId: string;
  testInstrument: string;
  stdInstrument: string;
  calDueDate: string;
  note: string;
  onFurnaceChange: (value: string) => void;
  onTestTypeChange: (value: 'TUS' | 'SAT') => void;
  onTestDateChange: (value: string) => void;
  onQuarterChange: (value: string) => void;
  onSetpointChange: (value: string) => void;
  onToleranceChange: (value: string) => void;
  onTesterIdChange: (value: string) => void;
  onTestInstrumentChange: (value: string) => void;
  onStdInstrumentChange: (value: string) => void;
  onCalDueDateChange: (value: string) => void;
  onNoteChange: (value: string) => void;
}

const PyrometryBasicSection = ({
  furnaces,
  inspectors,
  furnaceId,
  testType,
  testDate,
  quarter,
  setpoint,
  tolerance,
  testerId,
  testInstrument,
  stdInstrument,
  calDueDate,
  note,
  onFurnaceChange,
  onTestTypeChange,
  onTestDateChange,
  onQuarterChange,
  onSetpointChange,
  onToleranceChange,
  onTesterIdChange,
  onTestInstrumentChange,
  onStdInstrumentChange,
  onCalDueDateChange,
  onNoteChange,
}: PyrometryBasicSectionProps) => (
  <Row className="g-2 mb-3">
    <Col md={3}>
      <Form.Label>爐子 *</Form.Label>
      <Form.Select size="sm" value={furnaceId} onChange={e => onFurnaceChange(e.target.value)}>
        <option value="">請選擇</option>
        {furnaces.map(furnace => (
          <option key={furnace.識別碼} value={furnace.識別碼}>{furnace.爐號} {furnace.名稱}</option>
        ))}
      </Form.Select>
    </Col>
    <Col md={2}>
      <Form.Label>類型 *</Form.Label>
      <Form.Select size="sm" value={testType} onChange={e => onTestTypeChange(e.target.value as 'TUS' | 'SAT')}>
        <option value="TUS">TUS</option>
        <option value="SAT">SAT</option>
      </Form.Select>
    </Col>
    <Col md={2}>
      <Form.Label>測試日期 *</Form.Label>
      <Form.Control size="sm" type="date" value={testDate} onChange={e => onTestDateChange(e.target.value)} />
    </Col>
    <Col md={2}>
      <Form.Label>季別</Form.Label>
      <Form.Control size="sm" value={quarter} onChange={e => onQuarterChange(e.target.value)} />
    </Col>
    <Col md={2}>
      <Form.Label>設定溫度(°C) *</Form.Label>
      <Form.Control size="sm" value={setpoint} onChange={e => onSetpointChange(e.target.value)} />
    </Col>
    <Col md={2}>
      <Form.Label>允許公差(±°C)</Form.Label>
      <Form.Control size="sm" value={tolerance} onChange={e => onToleranceChange(e.target.value)} />
    </Col>
    <Col md={3}>
      <Form.Label>測試人員</Form.Label>
      <Form.Select size="sm" value={testerId} onChange={e => onTesterIdChange(e.target.value)}>
        <option value="">請選擇</option>
        {inspectors.map(inspector => <option key={inspector.id} value={inspector.id}>{inspector.name}</option>)}
      </Form.Select>
    </Col>
    <Col md={3}>
      <Form.Label>測試儀器編號</Form.Label>
      <Form.Control size="sm" value={testInstrument} onChange={e => onTestInstrumentChange(e.target.value)} />
    </Col>
    <Col md={3}>
      <Form.Label>標準校正儀器編號</Form.Label>
      <Form.Control size="sm" value={stdInstrument} onChange={e => onStdInstrumentChange(e.target.value)} />
    </Col>
    <Col md={2}>
      <Form.Label>儀器校正到期日</Form.Label>
      <Form.Control size="sm" type="date" value={calDueDate} onChange={e => onCalDueDateChange(e.target.value)} />
    </Col>
    <Col md={12}>
      <Form.Label>備註</Form.Label>
      <Form.Control as="textarea" rows={2} size="sm" value={note} onChange={e => onNoteChange(e.target.value)} />
    </Col>
  </Row>
);

export default PyrometryBasicSection;
