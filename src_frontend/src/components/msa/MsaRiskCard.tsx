import type { ReactNode } from 'react';

export type MsaSeverity = 'critical' | 'warning' | 'info' | 'normal';

/** 每個嚴重度都同時給圖示與中文說明，狀態不單靠顏色傳達。 */
export const SEVERITY_META: Record<
  MsaSeverity, { icon: string; label: string }
> = {
  critical: { icon: '!', label: '重大風險' },
  warning: { icon: '◷', label: '需注意' },
  info: { icon: 'i', label: '待處理' },
  normal: { icon: '✓', label: '正常' },
};

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
