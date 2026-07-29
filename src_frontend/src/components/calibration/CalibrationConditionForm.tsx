export interface EnvironmentRule {
  label?: string;
  required?: boolean;
  minimum?: string | number | null;
  maximum?: string | number | null;
  unit?: string | null;
  instruction?: string | null;
}

export interface EnvironmentValue {
  value: string;
  unit: string | null;
  instruction: string | null;
}

interface CalibrationConditionFormProps {
  requirements: Record<string, unknown>;
  values: Record<string, EnvironmentValue>;
  onChange: (values: Record<string, EnvironmentValue>) => void;
  disabled?: boolean;
}

export default function CalibrationConditionForm({
  requirements,
  values,
  onChange,
  disabled = false,
}: CalibrationConditionFormProps) {
  const entries = Object.entries(requirements);
  if (entries.length === 0) {
    return <p className="cal-state">此模板未要求環境條件。</p>;
  }
  return (
    <div className="cal-condition-grid">
      {entries.map(([key, rawRule]) => {
        const rule = (
          typeof rawRule === 'object' && rawRule !== null ? rawRule : {}
        ) as EnvironmentRule;
        const label = `${rule.label || key}${
          rule.unit ? ` (${rule.unit})` : ''
        }`;
        const current = values[key]?.value ?? '';
        return (
          <label key={key}>
            {label}
            {rule.required && <span aria-hidden="true"> *</span>}
            <input
              id={`environment-${key}`}
              data-environment-key={key}
              aria-label={label}
              inputMode="decimal"
              required={rule.required}
              min={rule.minimum == null ? undefined : String(rule.minimum)}
              max={rule.maximum == null ? undefined : String(rule.maximum)}
              value={current}
              disabled={disabled}
              onChange={(event) => onChange({
                ...values,
                [key]: {
                  value: event.target.value,
                  unit: rule.unit ?? null,
                  instruction: rule.instruction ?? null,
                },
              })}
            />
            <small>
              {rule.instruction || '依現場實際條件登錄'}
              {(rule.minimum != null || rule.maximum != null) && (
                <> · 範圍 {rule.minimum ?? '—'}–{rule.maximum ?? '—'}</>
              )}
            </small>
          </label>
        );
      })}
    </div>
  );
}
