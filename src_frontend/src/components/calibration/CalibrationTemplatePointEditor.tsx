import type { TemplatePointDraft } from './calibrationTemplateDraft';

interface CalibrationTemplatePointEditorProps {
  versionNo: number;
  points: TemplatePointDraft[];
  readOnly: boolean;
  disabled?: boolean;
  invalidPath?: string | null;
  onChange: (index: number, point: TemplatePointDraft) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}

export default function CalibrationTemplatePointEditor({
  versionNo,
  points,
  readOnly,
  disabled = false,
  invalidPath,
  onChange,
  onAdd,
  onRemove,
}: CalibrationTemplatePointEditorProps) {
  const controlsDisabled = readOnly || disabled;
  const patch = (
    index: number,
    changes: Partial<TemplatePointDraft>,
  ) => onChange(index, { ...points[index], ...changes });
  const addPoint = () => {
    const nextIndex = points.length;
    onAdd();
    requestAnimationFrame(() => {
      document.getElementById(`template-point-${nextIndex}-code`)?.focus();
    });
  };
  const removePoint = (index: number) => {
    const focusId = points.length === 1
      ? 'add-template-point'
      : `template-point-${Math.max(0, index - 1)}-code`;
    onRemove(index);
    requestAnimationFrame(() => document.getElementById(focusId)?.focus());
  };

  return (
    <section className="cal-template-points" aria-labelledby="point-rules-title">
      <header>
        <div>
          <p className="cal-kicker">逐點判定規則</p>
          <h2 id="point-rules-title">校正點</h2>
        </div>
        {!readOnly && (
          <button
            className="cal-button cal-button--secondary"
            id="add-template-point"
            type="button"
            disabled={disabled}
            onClick={addPoint}
          >
            新增校正點
          </button>
        )}
      </header>
      <div className="cal-point-table-wrap">
        <table className="cal-point-table">
          <caption>V{versionNo} 校正點規則</caption>
          <thead>
            <tr>
              <th scope="col">識別與模式</th>
              <th scope="col">名目與參考</th>
              <th scope="col">誤差界限</th>
              <th scope="col">重複性</th>
              <th scope="col">資格範圍</th>
              <th scope="col">控制</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point, index) => {
              const id = `template-point-${index}`;
              const invalid = (field: string) => (
                invalidPath === `points[${index}].${field}` || undefined
              );
              const describedBy = invalidPath?.startsWith(`points[${index}].`)
                ? 'template-editor-error'
                : undefined;
              return (
                <tr key={`${point.point_order}-${index}`}>
                  <th scope="row">
                    <span className="visually-hidden">
                      校正點 {point.point_code || index + 1}
                    </span>
                    <label htmlFor={`${id}-code`}>
                      校正點代碼
                      <input
                        id={`${id}-code`}
                        value={point.point_code}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('point_code')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          point_code: event.target.value,
                        })}
                      />
                    </label>
                    <label htmlFor={`${id}-mode`}>
                      量測模式
                      <input
                        id={`${id}-mode`}
                        value={point.measurement_mode}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('measurement_mode')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          measurement_mode: event.target.value,
                        })}
                      />
                    </label>
                  </th>
                  <td>
                    <label htmlFor={`${id}-nominal`}>
                      名目值
                      <input
                        id={`${id}-nominal`}
                        inputMode="decimal"
                        value={point.nominal_value}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('nominal_value')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          nominal_value: event.target.value,
                        })}
                      />
                    </label>
                    <label htmlFor={`${id}-unit`}>
                      單位
                      <input
                        id={`${id}-unit`}
                        value={point.unit}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('unit')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          unit: event.target.value,
                        })}
                      />
                    </label>
                    <label htmlFor={`${id}-reference-mode`}>
                      參考輸入
                      <select
                        id={`${id}-reference-mode`}
                        value={point.reference_input_mode}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('reference_input_mode')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          reference_input_mode: event.target.value as (
                            TemplatePointDraft['reference_input_mode']
                          ),
                        })}
                      >
                        <option value="certified_value">認證值</option>
                        <option value="paired_reading">成對讀值</option>
                      </select>
                    </label>
                  </td>
                  <td>
                    <label htmlFor={`${id}-lower`}>
                      誤差下限
                      <input
                        id={`${id}-lower`}
                        inputMode="decimal"
                        value={point.error_lower_limit}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('error_lower_limit')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          error_lower_limit: event.target.value,
                        })}
                      />
                    </label>
                    <label htmlFor={`${id}-upper`}>
                      誤差上限
                      <input
                        id={`${id}-upper`}
                        inputMode="decimal"
                        value={point.error_upper_limit}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('error_upper_limit')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          error_upper_limit: event.target.value,
                        })}
                      />
                    </label>
                    <label htmlFor={`${id}-evaluation`}>
                      判定基礎
                      <select
                        id={`${id}-evaluation`}
                        value={point.evaluation_basis}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('evaluation_basis')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          evaluation_basis: event.target.value as (
                            TemplatePointDraft['evaluation_basis']
                          ),
                        })}
                      >
                        <option value="all_readings">每筆讀值</option>
                        <option value="mean_error">平均誤差</option>
                      </select>
                    </label>
                  </td>
                  <td>
                    <label htmlFor={`${id}-repetitions`}>
                      重複次數
                      <input
                        id={`${id}-repetitions`}
                        inputMode="numeric"
                        value={point.required_repetitions}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('required_repetitions')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          required_repetitions: event.target.value,
                        })}
                      />
                    </label>
                    <label htmlFor={`${id}-repeat-rule`}>
                      重複性規則
                      <select
                        id={`${id}-repeat-rule`}
                        value={point.repeatability_rule}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('repeatability_rule')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          repeatability_rule: event.target.value as (
                            TemplatePointDraft['repeatability_rule']
                          ),
                          repeatability_limit: event.target.value === 'none'
                            ? ''
                            : point.repeatability_limit,
                        })}
                      >
                        <option value="none">不判定</option>
                        <option value="range">極差</option>
                        <option value="stddev">標準差</option>
                      </select>
                    </label>
                    <label htmlFor={`${id}-repeat-limit`}>
                      重複性上限
                      <input
                        id={`${id}-repeat-limit`}
                        inputMode="decimal"
                        value={point.repeatability_limit}
                        disabled={
                          controlsDisabled || point.repeatability_rule === 'none'
                        }
                        aria-invalid={invalid('repeatability_limit')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          repeatability_limit: event.target.value,
                        })}
                      />
                    </label>
                  </td>
                  <td>
                    <label htmlFor={`${id}-scope`}>
                      資格範圍代碼
                      <input
                        id={`${id}-scope`}
                        value={point.qualification_scope_code}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('qualification_scope_code')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          qualification_scope_code: event.target.value,
                        })}
                      />
                    </label>
                    <div className="cal-inline-fields">
                      <label htmlFor={`${id}-range-start`}>
                        範圍起點
                        <input
                          id={`${id}-range-start`}
                          inputMode="decimal"
                          value={point.qualification_range_start}
                          disabled={controlsDisabled}
                          aria-invalid={invalid('qualification_range_start')}
                          aria-describedby={describedBy}
                          onChange={(event) => patch(index, {
                            qualification_range_start: event.target.value,
                          })}
                        />
                      </label>
                      <label htmlFor={`${id}-range-end`}>
                        範圍終點
                        <input
                          id={`${id}-range-end`}
                          inputMode="decimal"
                          value={point.qualification_range_end}
                          disabled={controlsDisabled}
                          aria-invalid={invalid('qualification_range_end')}
                          aria-describedby={describedBy}
                          onChange={(event) => patch(index, {
                            qualification_range_end: event.target.value,
                          })}
                        />
                      </label>
                    </div>
                    <label htmlFor={`${id}-instruction`}>
                      操作指示
                      <textarea
                        id={`${id}-instruction`}
                        rows={2}
                        value={point.instruction}
                        disabled={controlsDisabled}
                        aria-invalid={invalid('instruction')}
                        aria-describedby={describedBy}
                        onChange={(event) => patch(index, {
                          instruction: event.target.value,
                        })}
                      />
                    </label>
                  </td>
                  <td className="cal-point-controls">
                    <label className="cal-check" htmlFor={`${id}-required`}>
                      <input
                        id={`${id}-required`}
                        type="checkbox"
                        checked={point.required}
                        disabled={controlsDisabled}
                        onChange={(event) => patch(index, {
                          required: event.target.checked,
                        })}
                      />
                      必要點
                    </label>
                    <label className="cal-check" htmlFor={`${id}-uncertainty`}>
                      <input
                        id={`${id}-uncertainty`}
                        type="checkbox"
                        checked={point.uncertainty_required}
                        disabled={controlsDisabled}
                        onChange={(event) => patch(index, {
                          uncertainty_required: event.target.checked,
                        })}
                      />
                      需不確定度
                    </label>
                    {!readOnly && (
                      <button
                        className="cal-button cal-button--danger"
                        type="button"
                        disabled={disabled}
                        aria-label={`移除校正點 ${point.point_code || index + 1}`}
                        onClick={() => removePoint(index)}
                      >
                        移除
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {points.length === 0 && (
        <p className="cal-empty">尚未定義校正點。先新增必要點，才能送審版本。</p>
      )}
    </section>
  );
}
