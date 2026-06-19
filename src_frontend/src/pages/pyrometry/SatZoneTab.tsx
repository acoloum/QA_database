import { Button, Col, Form, Row, Table } from 'react-bootstrap';

import type { SatPoint, SatReading } from '../../types';

interface Props {
  point: SatPoint;
  tolerance: string;
  onUpdateField: (key: keyof SatPoint, value: string) => void;
  onUpdateReading: (readingIndex: number, key: keyof SatReading, value: string) => void;
  onAddReading: () => void;
  onRemoveReading: (readingIndex: number) => void;
}

const SatZoneTab = ({
  point,
  tolerance,
  onUpdateField,
  onUpdateReading,
  onAddReading,
  onRemoveReading,
}: Props) => {
  const tol = parseFloat(String(tolerance)) || 0;
  const corr = parseFloat(String(point.修正值 ?? 0)) || 0;

  const validReadings = point.readings.filter(
    reading => reading.校正測試讀值 !== '' && reading.校正測試讀值 !== null,
  );
  const passCount = validReadings.filter(reading => {
    const ctrl = parseFloat(String(reading.控制儀表讀值));
    const test = parseFloat(String(reading.校正測試讀值));
    if (isNaN(ctrl) || isNaN(test)) return false;
    const dev = Math.round((test - ctrl + corr) * 100) / 100;
    return Math.abs(dev) <= tol;
  }).length;

  return (
    <>
      <Row className="g-2 mb-2 align-items-end">
        <Col md={3}>
          <Form.Label className="mb-0" style={{ fontSize: 12 }}>控溫區名稱</Form.Label>
          <Form.Control
            size="sm"
            value={point.控溫區}
            aria-label="控溫區名稱"
            onChange={event => onUpdateField('控溫區', event.target.value)}
          />
        </Col>
        <Col md={1}>
          <Form.Label className="mb-0" style={{ fontSize: 12 }}>頻道</Form.Label>
          <Form.Control
            size="sm"
            type="number"
            min={1}
            max={99}
            value={point.頻道 ?? ''}
            aria-label="頻道"
            onChange={event => onUpdateField('頻道', event.target.value)}
          />
        </Col>
        <Col md={2}>
          <Form.Label className="mb-0" style={{ fontSize: 12 }}>修正值 (°C)</Form.Label>
          <Form.Control
            size="sm"
            value={String(point.修正值 ?? '')}
            aria-label="修正值"
            onChange={event => onUpdateField('修正值', event.target.value)}
          />
        </Col>
        <Col md="auto">
          <Button size="sm" variant="outline-success" onClick={onAddReading}>＋ 新增讀值</Button>
        </Col>
        <Col md="auto" className="ms-auto text-end">
          <span className="text-muted" style={{ fontSize: 12 }}>
            有效讀值 {validReadings.length} 筆，合格 {passCount} / {validReadings.length}
          </span>
        </Col>
      </Row>

      <Table bordered size="sm" className="text-center align-middle">
        <thead className="table-secondary">
          <tr>
            <th style={{ width: 36 }}>#</th>
            <th>控制儀表讀值</th>
            <th>校正測試讀值</th>
            <th style={{ minWidth: 50 }}>差值</th>
            <th style={{ minWidth: 50 }}>偏差</th>
            <th style={{ width: 42 }}>合格</th>
            <th style={{ width: 36 }}></th>
          </tr>
        </thead>
        <tbody>
          {point.readings.map((reading, readingIndex) => {
            const ctrl = parseFloat(String(reading.控制儀表讀值));
            const test = parseFloat(String(reading.校正測試讀值));
            const diff = (!isNaN(ctrl) && !isNaN(test)) ? Math.round((test - ctrl) * 100) / 100 : null;
            const dev = diff !== null ? Math.round((diff + corr) * 100) / 100 : null;
            const pass = dev !== null ? Math.abs(dev) <= tol : null;
            const devColor = dev === null ? undefined : Math.abs(dev) > tol ? '#842029' : '#0a3622';
            return (
              <tr key={readingIndex} style={pass === false ? { background: '#fff5f5' } : undefined}>
                <td className="text-muted" style={{ fontSize: 11 }}>{readingIndex + 1}</td>
                <td>
                  <Form.Control
                    size="sm"
                    value={String(reading.控制儀表讀值 ?? '')}
                    aria-label={`控制儀表讀值 ${readingIndex + 1}`}
                    onChange={event => onUpdateReading(readingIndex, '控制儀表讀值', event.target.value)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={String(reading.校正測試讀值 ?? '')}
                    aria-label={`校正測試讀值 ${readingIndex + 1}`}
                    onChange={event => onUpdateReading(readingIndex, '校正測試讀值', event.target.value)}
                  />
                </td>
                <td className="text-muted">{diff ?? '—'}</td>
                <td style={{ fontWeight: dev !== null ? 600 : undefined, color: devColor }}>
                  {dev ?? '—'}
                </td>
                <td>
                  {pass === null ? '—' : pass
                    ? <span style={{ color: '#198754', fontWeight: 700 }}>✓</span>
                    : <span style={{ color: '#dc3545', fontWeight: 700 }}>✗</span>}
                </td>
                <td>
                  <Button
                    size="sm"
                    variant="outline-danger"
                    style={{ padding: '1px 5px', fontSize: 11, lineHeight: 1.2 }}
                    disabled={point.readings.length <= 1}
                    onClick={() => onRemoveReading(readingIndex)}
                  >
                    ✕
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </>
  );
};

export default SatZoneTab;
