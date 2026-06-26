import { Button, Form } from 'react-bootstrap';

import { parseRangeIndex } from './pyrometryFormUtils';

interface Props {
  label: string;
  start: number;
  end: number;
  timeLabels: string[];
  applyLabel: string;
  startAriaLabel?: string;
  endAriaLabel?: string;
  onStartChange: (value: number) => void;
  onEndChange: (value: number) => void;
  onApply: () => void;
}

const ChartRangeControls = ({
  label,
  start,
  end,
  timeLabels,
  applyLabel,
  startAriaLabel,
  endAriaLabel,
  onStartChange,
  onEndChange,
  onApply,
}: Props) => {
  const count = end >= start ? end - start + 1 : 0;

  return (
    <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
      <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>{label}：</span>
      <div className="d-flex align-items-center gap-1">
        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
        <Form.Select
          size="sm"
          style={{ minWidth: 120 }}
          value={start}
          aria-label={startAriaLabel}
          onChange={event => onStartChange(parseRangeIndex(event.target.value))}
        >
          {timeLabels.map((time, index) => <option key={index} value={index}>{time}</option>)}
        </Form.Select>
      </div>
      <div className="d-flex align-items-center gap-1">
        <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
        <Form.Select
          size="sm"
          style={{ minWidth: 120 }}
          value={end}
          aria-label={endAriaLabel}
          onChange={event => onEndChange(parseRangeIndex(event.target.value))}
        >
          {timeLabels.map((time, index) => <option key={index} value={index}>{time}</option>)}
        </Form.Select>
      </div>
      <Button size="sm" variant="primary" onClick={onApply}>{applyLabel}</Button>
      <span className="text-muted" style={{ fontSize: 11 }}>
        共 {count} 筆
      </span>
    </div>
  );
};

export default ChartRangeControls;
