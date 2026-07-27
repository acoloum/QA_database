import type { MsaCriteriaProfile, MsaCriteriaVersion } from '../../types/msa';

/** 門檻代碼對應的人類可讀名稱與單位；未列出的代碼以原代碼呈現。 */
const THRESHOLD_META: Record<string, { label: string; unit?: string }> = {
  grr_accept_max: { label: 'GRR 允收上限', unit: '%' },
  grr_conditional_max: { label: 'GRR 條件接受上限', unit: '%' },
  ndc_min: { label: 'ndc 最低值' },
  alpha: { label: '顯著水準 alpha' },
  kappa_min: { label: 'Kappa 最低值' },
  effectiveness_min: { label: '有效性最低值', unit: '%' },
  false_accept_max: { label: '誤收率上限', unit: '%' },
  false_reject_max: { label: '誤拒率上限', unit: '%' },
};

/** 門檻固定依此順序呈現，讓不同版本可以逐列對照。 */
const THRESHOLD_ORDER = [
  'grr_accept_max',
  'grr_conditional_max',
  'ndc_min',
  'kappa_min',
  'effectiveness_min',
  'false_accept_max',
  'false_reject_max',
  'alpha',
];

type VersionRole = 'draft' | 'current' | 'history';

const ROLE_META: Record<VersionRole, { label: string; icon: string; tone: string }> = {
  draft: { label: '草稿', icon: '✎', tone: 'warning' },
  current: { label: '目前版本', icon: '✓', tone: 'ok' },
  history: { label: '歷史版本', icon: '⌛', tone: 'neutral' },
};

const versionRole = (
  version: MsaCriteriaVersion,
  currentVersionId: number | null,
): VersionRole => {
  if (version.status === 'draft') return 'draft';
  return version.id === currentVersionId ? 'current' : 'history';
};

const orderedThresholds = (thresholds: Record<string, number>) => {
  const known = THRESHOLD_ORDER.filter((key) => key in thresholds);
  const extra = Object.keys(thresholds).filter((key) => !THRESHOLD_ORDER.includes(key));
  return [...known, ...extra];
};

interface CriteriaVersionTimelineProps {
  profile: MsaCriteriaProfile;
  /** 具備 msa.approve 時才會傳入；draft 版本才會呈現核准入口。 */
  onApprove?: (version: MsaCriteriaVersion) => void;
}

export default function CriteriaVersionTimeline({
  profile,
  onApprove,
}: CriteriaVersionTimelineProps) {
  // 版本由新到舊排列，讓待處理的草稿排在最前面
  const versions = [...profile.versions].sort((a, b) => b.version_no - a.version_no);

  return (
    <ol className="msa-timeline" aria-label={`${profile.name} 的版本歷程`}>
      {versions.map((version) => {
        const role = versionRole(version, profile.current_version_id);
        const meta = ROLE_META[role];
        return (
          <li key={version.id} className={`msa-criteria-version is-${role}`}>
            <header>
              <div>
                <strong className="msa-mono">v{version.version_no}</strong>
                <span
                  className={`msa-status msa-status--${meta.tone}`}
                  aria-label={`版本狀態：${meta.label}`}
                >
                  <span className="msa-status__icon" aria-hidden="true">{meta.icon}</span>
                  {meta.label}
                </span>
              </div>
              {role === 'draft' && onApprove && (
                <button
                  type="button"
                  className="msa-button msa-button--primary"
                  onClick={() => onApprove(version)}
                >
                  核准 v{version.version_no}
                </button>
              )}
            </header>

            <dl className="msa-definition-grid">
              <div>
                <dt>方法版本</dt>
                <dd className="msa-mono">{version.method_version}</dd>
              </div>
              <div>
                <dt>生效日</dt>
                <dd><time className="msa-mono">{version.effective_date}</time></dd>
              </div>
              <div>
                <dt>方法依據</dt>
                <dd>{version.basis || '未填依據'}</dd>
              </div>
              <div>
                <dt>穩定性判定規則</dt>
                <dd className="msa-mono">
                  {String(version.stability_rules.rule_set ?? '未設定')}
                  {' · 規則 '}
                  {Array.isArray(version.stability_rules.enabled_rules)
                    ? version.stability_rules.enabled_rules.join('、')
                    : '未設定'}
                </dd>
              </div>
            </dl>

            <table className="msa-criteria-thresholds">
              <caption>v{version.version_no} 的判定門檻</caption>
              <tbody>
                {orderedThresholds(version.thresholds).map((key) => {
                  const threshold = THRESHOLD_META[key];
                  return (
                    <tr key={key}>
                      <th scope="row">{threshold?.label ?? key}</th>
                      <td className="msa-mono">
                        {threshold?.unit
                          ? `${version.thresholds[key]} ${threshold.unit}`
                          : version.thresholds[key]}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {version.conditional_actions.length > 0 && (
              <div className="msa-criteria-actions">
                <h4>條件接受時的必要措施</h4>
                <ul>
                  {version.conditional_actions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
              </div>
            )}

            <p className="msa-help">
              {version.status === 'approved'
                ? `已於 ${version.approved_at?.slice(0, 10) ?? '未知日期'} 核准，核准後不可修改。`
                : '草稿版本尚未成為判定依據。'}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
