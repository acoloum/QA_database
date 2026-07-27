import type { MsaDisposition, MsaResultVersion } from '../../types/msa';

const DISPOSITION_META: Record<
  MsaDisposition, { label: string; icon: string; tone: string }
> = {
  acceptable: { label: '可接受', icon: '✓', tone: 'ok' },
  conditionally_acceptable: { label: '條件接受', icon: '!', tone: 'warning' },
  unacceptable: { label: '不可接受', icon: '×', tone: 'danger' },
  indeterminate: { label: '無法判定', icon: '?', tone: 'neutral' },
};

const STATUS_LABELS: Record<MsaResultVersion['status'], string> = {
  analyzed: '已分析',
  submitted: '待核准',
  approved: '已核准',
  rejected: '已退回',
  voided: '已作廢',
  superseded: '已被取代',
};

interface MsaResultHeroProps {
  result: MsaResultVersion;
  studyNo: string;
  characteristic: string;
}

/**
 * 結論區刻意把「系統處置」與「人工工程判斷」並列呈現：
 * 讀者一眼就能看出哪些是統計得到的，哪些是人加上去的。
 */
export default function MsaResultHero({
  result, studyNo, characteristic,
}: MsaResultHeroProps) {
  const disposition = result.conclusion.system_disposition;
  const meta = DISPOSITION_META[disposition]
    ?? DISPOSITION_META.indeterminate;

  return (
    <section
      className="msa-result-hero"
      data-tone={meta.tone}
      aria-label={`判定結果：${meta.label}`}
    >
      <div className="msa-result-hero__verdict">
        <span className="msa-result-hero__icon" aria-hidden="true">
          {meta.icon}
        </span>
        <div>
          <p className="msa-eyebrow">系統處置</p>
          <strong>{meta.label}</strong>
        </div>
      </div>

      <dl className="msa-review-grid">
        <div>
          <dt>研究</dt>
          <dd>{studyNo}｜{characteristic}</dd>
        </div>
        <div>
          <dt>結果版本</dt>
          <dd className="msa-num">v{result.result_version_no}</dd>
        </div>
        <div>
          <dt>結果狀態</dt>
          <dd>{STATUS_LABELS[result.status]}</dd>
        </div>
        <div>
          <dt>百分比口徑</dt>
          <dd>{result.conclusion.percent_basis ?? '未指定'}</dd>
        </div>
        <div>
          <dt>人工工程判斷</dt>
          <dd>
            {result.conclusion.engineering_judgment ?? '未附加'}
          </dd>
        </div>
      </dl>

      {result.conclusion.reasons.length > 0 && (
        <div className="msa-result-hero__reasons">
          <h3>判定理由</h3>
          <ul>
            {result.conclusion.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {result.blockers.length > 0 && (
        <div className="msa-state msa-state--error" role="alert">
          <p>阻擋條件</p>
          <ul>
            {result.blockers.map((blocker) => (
              <li key={blocker.code}>{blocker.message}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
