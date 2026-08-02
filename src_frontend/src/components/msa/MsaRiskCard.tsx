import type { ReactNode } from 'react';

import { SEVERITY_META, type MsaSeverity } from './msaRiskMeta';

interface MsaRiskCardProps {
  label: string;
  count: number;
  hint: string;
  severity: MsaSeverity;
  onSelect?: () => void;
  children?: ReactNode;
}

export default function MsaRiskCard({
  label, count, hint, severity, onSelect, children,
}: MsaRiskCardProps) {
  const meta = SEVERITY_META[severity];
  const content = (
    <>
      <span className="msa-risk-card__label">
        <span aria-hidden="true">{meta.icon}</span>
        {label}
      </span>
      <span className="msa-risk-card__count msa-num">{count}</span>
      <p className="msa-risk-card__hint">{hint}</p>
      {children}
    </>
  );

  if (!onSelect) {
    return (
      <div
        className="msa-risk-card"
        data-severity={severity}
        aria-label={`${meta.label}：${label} ${count} 件`}
      >
        {content}
      </div>
    );
  }

  return (
    <button
      type="button"
      className="msa-risk-card"
      data-severity={severity}
      aria-label={`${meta.label}：${label} ${count} 件`}
      onClick={onSelect}
    >
      {content}
    </button>
  );
}
