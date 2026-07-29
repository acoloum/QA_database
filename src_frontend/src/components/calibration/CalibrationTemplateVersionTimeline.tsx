import type { CalibrationTemplateVersion } from '../../types/calibration';

const STATUS_LABELS: Record<CalibrationTemplateVersion['status'], string> = {
  draft: '草稿',
  submitted: '已送審',
  approved: '已核准',
  rejected: '已退回',
  superseded: '已被取代',
};

interface CalibrationTemplateVersionTimelineProps {
  versions: CalibrationTemplateVersion[];
  selectedId: number;
  onSelect: (versionId: number) => void;
}

const formatEvidenceTime = (value: string | null) => (
  value ? new Date(value).toLocaleString('zh-TW') : '時間未記錄'
);

export default function CalibrationTemplateVersionTimeline({
  versions,
  selectedId,
  onSelect,
}: CalibrationTemplateVersionTimelineProps) {
  return (
    <nav className="cal-version-rail" aria-label="模板版本時間軸">
      <p className="cal-kicker">受控版本刻度</p>
      <ol>
        {versions.map((version) => (
          <li key={version.id} data-status={version.status}>
            <button
              type="button"
              aria-current={selectedId === version.id ? 'step' : undefined}
              onClick={() => onSelect(version.id)}
            >
              <span className="cal-version-mark" aria-hidden="true" />
              <span>
                <strong>V{version.version_no}</strong>
                <small>{STATUS_LABELS[version.status]}</small>
              </span>
              <code>r{version.row_version}</code>
            </button>
            <div className="cal-version-evidence">
              <p>{version.revision_reason || '未填修訂理由'}</p>
              <ul>
                <li>
                  建立 #{version.created_by} · {formatEvidenceTime(version.created_at)}
                </li>
                {version.submitted_by !== null && (
                  <li>
                    送審 #{version.submitted_by}
                    {' · '}{formatEvidenceTime(version.submitted_at)}
                  </li>
                )}
                {version.approved_by !== null && (
                  <li>
                    核准 #{version.approved_by}
                    {' · '}{formatEvidenceTime(version.approved_at)}
                  </li>
                )}
              </ul>
              {(version.approval_reason || version.rejection_reason) && (
                <small>
                  {version.approval_reason || version.rejection_reason}
                </small>
              )}
            </div>
          </li>
        ))}
      </ol>
    </nav>
  );
}
