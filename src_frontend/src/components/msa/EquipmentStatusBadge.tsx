import type {
  CalibrationStatus,
  EquipmentStatus,
} from '../../types/msa';

type Status = CalibrationStatus | EquipmentStatus;

const STATUS_META: Record<Status, { icon: string; label: string; tone: string }> = {
  active: { icon: '✓', label: '使用中', tone: 'ok' },
  pending_review: { icon: '…', label: '待確認', tone: 'warning' },
  maintenance: { icon: '⚒', label: '維修', tone: 'warning' },
  inactive: { icon: '−', label: '停用', tone: 'neutral' },
  scrapped: { icon: '×', label: '報廢', tone: 'danger' },
  valid: { icon: '✓', label: '有效', tone: 'ok' },
  due_soon: { icon: '◷', label: '30 日內到期', tone: 'warning' },
  expired: { icon: '!', label: '逾期', tone: 'danger' },
  failed: { icon: '×', label: '失敗', tone: 'danger' },
  missing: { icon: '?', label: '缺少證據', tone: 'danger' },
  exempt: { icon: '◇', label: '免校', tone: 'neutral' },
};

interface EquipmentStatusBadgeProps {
  status: Status;
}

export default function EquipmentStatusBadge({
  status,
}: EquipmentStatusBadgeProps) {
  const meta = STATUS_META[status];
  return (
    <span
      className={`msa-status msa-status--${meta.tone}`}
      aria-label={`狀態：${meta.label}`}
    >
      <span className="msa-status__icon" aria-hidden="true">{meta.icon}</span>
      {meta.label}
    </span>
  );
}
