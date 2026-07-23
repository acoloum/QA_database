import { Button, Form } from 'react-bootstrap';

import type { MechanicalTraceNumber } from '../../types';

interface MechanicalTraceNumberPanelProps {
  idPrefix: 'extrusion' | 't4-furnace';
  title: '擠製編號' | 'T4爐號';
  addLabel: string;
  values: MechanicalTraceNumber[];
  duplicateIndexes: Set<number>;
  onChange: (index: number, value: string) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}

export default function MechanicalTraceNumberPanel({
  idPrefix,
  title,
  addLabel,
  values,
  duplicateIndexes,
  onChange,
  onAdd,
  onRemove,
}: MechanicalTraceNumberPanelProps) {
  return (
    <section
      className="border rounded p-3 h-100"
      aria-labelledby={`mechanical-${idPrefix}-title`}
    >
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3 id={`mechanical-${idPrefix}-title`} className="h6 mb-0">{title}</h3>
        <Button type="button" size="sm" variant="outline-primary" onClick={onAdd}>
          {addLabel}
        </Button>
      </div>
      <div className="d-grid gap-2">
        {values.map((value, index) => {
          const inputId = `mechanical-${idPrefix}-${value.序號}`;
          const errorId = `${inputId}-duplicate-error`;
          const isDuplicate = duplicateIndexes.has(index);
          return (
            <div key={value.序號}>
              <div className="d-flex gap-2 align-items-start">
                <span className="pt-2" aria-hidden="true">{value.序號}</span>
                <Form.Group className="flex-grow-1" controlId={inputId}>
                  <Form.Label className="visually-hidden">{`${title} ${value.序號}`}</Form.Label>
                  <Form.Control
                    maxLength={100}
                    value={value.編號}
                    aria-invalid={isDuplicate}
                    aria-describedby={isDuplicate ? errorId : undefined}
                    isInvalid={isDuplicate}
                    onChange={(event) => onChange(index, event.target.value)}
                  />
                  {isDuplicate && (
                    <Form.Control.Feedback id={errorId} type="invalid">
                      同一清單內的編號不可重複
                    </Form.Control.Feedback>
                  )}
                </Form.Group>
                <Button
                  type="button"
                  variant="outline-danger"
                  aria-label={`刪除${title} ${value.序號}`}
                  onClick={() => onRemove(index)}
                >
                  刪除
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
