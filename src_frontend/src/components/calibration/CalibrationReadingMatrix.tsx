import { useState, type ClipboardEvent, type KeyboardEvent } from 'react';

import {
  CalibrationMatrixPasteError,
  parseCalibrationMatrixPaste,
} from './calibrationMatrixPaste';

export interface CalibrationMatrixPoint {
  id: number;
  point_code: string;
  measurement_mode: string;
  unit: string;
  reference_input_mode: 'certified_value' | 'paired_reading';
  required_repetitions: number;
  reference_value: string | null;
  uncertainty_required?: boolean;
}

export type CalibrationMatrixValues = Record<string, string>;

interface CalibrationReadingMatrixProps {
  points: CalibrationMatrixPoint[];
  values: CalibrationMatrixValues;
  onChange: (values: CalibrationMatrixValues) => void;
  readOnly?: boolean;
}

const valueKey = (
  pointCode: string,
  trialNo: number,
  field: 'standard' | 'indicated',
) => `${pointCode}:${trialNo}:${field}`;

export default function CalibrationReadingMatrix({
  points,
  values,
  onChange,
  readOnly = false,
}: CalibrationReadingMatrixProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});

  const moveFocus = (
    event: KeyboardEvent<HTMLInputElement>,
    row: number,
    column: number,
    rowCount: number,
    columnCount: number,
  ) => {
    let nextRow = row;
    let nextColumn = column;
    if (event.key === 'ArrowRight') nextColumn += 1;
    else if (event.key === 'ArrowLeft') nextColumn -= 1;
    else if (event.key === 'ArrowDown' || event.key === 'Enter') nextRow += 1;
    else if (event.key === 'ArrowUp') nextRow -= 1;
    else return;
    if (
      nextRow < 0 || nextRow >= rowCount
      || nextColumn < 0 || nextColumn >= columnCount
    ) return;
    event.preventDefault();
    const table = event.currentTarget.closest('table');
    table?.querySelector<HTMLInputElement>(
      `[data-matrix-row="${nextRow}"][data-matrix-column="${nextColumn}"]`,
    )?.focus();
  };

  const pastePoint = (
    event: ClipboardEvent<HTMLInputElement>,
    point: CalibrationMatrixPoint,
  ) => {
    event.preventDefault();
    const columnCount = point.reference_input_mode === 'paired_reading' ? 2 : 1;
    try {
      const matrix = parseCalibrationMatrixPaste(
        event.clipboardData.getData('text'),
        point.required_repetitions,
        columnCount,
      );
      const next = { ...values };
      matrix.forEach((row, rowIndex) => {
        const trialNo = rowIndex + 1;
        if (point.reference_input_mode === 'paired_reading') {
          next[valueKey(point.point_code, trialNo, 'standard')] = row[0];
          next[valueKey(point.point_code, trialNo, 'indicated')] = row[1];
        } else {
          next[valueKey(point.point_code, trialNo, 'indicated')] = row[0];
        }
      });
      setErrors((current) => ({ ...current, [point.point_code]: '' }));
      onChange(next);
    } catch (error) {
      const message = error instanceof CalibrationMatrixPasteError
        ? error.message
        : '無法解析貼上資料';
      setErrors((current) => ({ ...current, [point.point_code]: message }));
    }
  };

  return (
    <div className="cal-reading-matrices">
      {points.map((point) => {
        const paired = point.reference_input_mode === 'paired_reading';
        const columns = paired ? 2 : 1;
        const errorId = `matrix-${point.id}-error`;
        return (
          <section className="cal-reading-matrix" key={point.id}>
            <header>
              <div>
                <h3>{point.point_code} · {point.measurement_mode}</h3>
                {!paired && (
                  <label>
                    {point.point_code} 認證參考值
                    <input
                      aria-label={`${point.point_code} 認證參考值`}
                      inputMode="decimal"
                      value={
                        values[`${point.point_code}:reference`]
                        ?? point.reference_value
                        ?? ''
                      }
                      disabled={readOnly}
                      onChange={(event) => onChange({
                        ...values,
                        [`${point.point_code}:reference`]: event.target.value,
                        [`${point.point_code}:reference-confirmed`]: '',
                      })}
                    />
                    <small>{point.unit}</small>
                  </label>
                )}
              </div>
              <small>可從 Excel 貼上完整 {point.required_repetitions} 列</small>
            </header>
            {!paired && (
              <label className="cal-check cal-check--panel">
                <input
                  type="checkbox"
                  checked={
                    values[`${point.point_code}:reference-confirmed`] === 'true'
                  }
                  disabled={readOnly}
                  onChange={(event) => onChange({
                    ...values,
                    [`${point.point_code}:reference-confirmed`]:
                      event.target.checked ? 'true' : '',
                  })}
                />
                {point.point_code} 已確認認證參考值
              </label>
            )}
            {point.uncertainty_required && (
              <div className="cal-inline-fields">
                <label>
                  {point.point_code} 擴充不確定度
                  <input
                    inputMode="decimal"
                    value={values[`${point.point_code}:uncertainty`] ?? ''}
                    disabled={readOnly}
                    onChange={(event) => onChange({
                      ...values,
                      [`${point.point_code}:uncertainty`]: event.target.value,
                    })}
                  />
                </label>
                <label>
                  {point.point_code} 涵蓋因子
                  <input
                    inputMode="decimal"
                    value={values[`${point.point_code}:coverage`] ?? ''}
                    disabled={readOnly}
                    onChange={(event) => onChange({
                      ...values,
                      [`${point.point_code}:coverage`]: event.target.value,
                    })}
                  />
                </label>
              </div>
            )}
            {errors[point.point_code] && (
              <p id={errorId} className="cal-inline-error" role="alert">
                {errors[point.point_code]}
              </p>
            )}
            <div className="cal-point-table-wrap">
              <table className="cal-reading-table">
                <caption>{point.point_code} 原始讀值</caption>
                <thead>
                  <tr>
                    <th scope="col">試驗</th>
                    {paired && <th scope="col">標準器讀值</th>}
                    <th scope="col">受校件器示值</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from(
                    { length: point.required_repetitions },
                    (_, index) => index + 1,
                  ).map((trialNo, rowIndex) => (
                    <tr key={trialNo}>
                      <th scope="row">試驗 {trialNo}</th>
                      {paired && (
                        <td data-label="標準器讀值">
                          <label className="visually-hidden" htmlFor={
                            `matrix-${point.id}-${trialNo}-standard`
                          }>
                            {point.point_code} 試驗 {trialNo} 標準器讀值
                          </label>
                          <input
                            id={`matrix-${point.id}-${trialNo}-standard`}
                            inputMode="decimal"
                            data-matrix-row={rowIndex}
                            data-matrix-column={0}
                            data-point-code={point.point_code}
                            value={values[valueKey(
                              point.point_code,
                              trialNo,
                              'standard',
                            )] ?? ''}
                            disabled={readOnly}
                            aria-describedby={
                              errors[point.point_code] ? errorId : undefined
                            }
                            onChange={(event) => onChange({
                              ...values,
                              [valueKey(point.point_code, trialNo, 'standard')]:
                                event.target.value,
                            })}
                            onPaste={(event) => pastePoint(event, point)}
                            onKeyDown={(event) => moveFocus(
                              event,
                              rowIndex,
                              0,
                              point.required_repetitions,
                              columns,
                            )}
                          />
                        </td>
                      )}
                      <td data-label="受校件器示值">
                        <label className="visually-hidden" htmlFor={
                          `matrix-${point.id}-${trialNo}-indicated`
                        }>
                          {point.point_code} 試驗 {trialNo} 受校件器示值
                        </label>
                        <input
                          id={`matrix-${point.id}-${trialNo}-indicated`}
                          inputMode="decimal"
                          data-matrix-row={rowIndex}
                          data-matrix-column={paired ? 1 : 0}
                          data-point-code={point.point_code}
                          value={values[valueKey(
                            point.point_code,
                            trialNo,
                            'indicated',
                          )] ?? ''}
                          disabled={readOnly}
                          aria-describedby={
                            errors[point.point_code] ? errorId : undefined
                          }
                          onChange={(event) => onChange({
                            ...values,
                            [valueKey(point.point_code, trialNo, 'indicated')]:
                              event.target.value,
                          })}
                          onPaste={(event) => pastePoint(event, point)}
                          onKeyDown={(event) => moveFocus(
                            event,
                            rowIndex,
                            paired ? 1 : 0,
                            point.required_repetitions,
                            columns,
                          )}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
