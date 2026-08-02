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
