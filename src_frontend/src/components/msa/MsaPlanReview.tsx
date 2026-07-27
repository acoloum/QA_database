import type { ReactNode } from 'react';

export interface MsaPlanBlocker {
  code: string;
  message: string;
}

export interface MsaPlanReviewSummary {
  methodLabel: string;
  methodCode: string;
  partCount: number;
  appraiserCount: number;
  trialCount: number;
  randomSeed: number;
  percentBasis: string;
  criteriaProfileName: string | null;
  equipment: Array<{
    equipmentNo: string;
    name: string;
    role: string;
    calibrationStatus: string;
    blockReason: string | null;
  }>;
}

interface MsaPlanReviewProps {
  summary: MsaPlanReviewSummary;
  /**
   * 阻擋原因一律由後端資格判定提供，前端不自行判斷是否可用於正式研究。
   */
  blockers: MsaPlanBlocker[];
  isFreezing?: boolean;
  onFreeze?: () => void;
  children?: ReactNode;
}

export default function MsaPlanReview({
  summary, blockers, isFreezing = false, onFreeze, children,
}: MsaPlanReviewProps) {
  const blocked = blockers.length > 0;

  return (
    <section className="msa-panel" aria-labelledby="msa-plan-review-title">
      <h2 id="msa-plan-review-title">凍結前檢閱</h2>
      <p>
        凍結會固定設備快照、已核准準則與隨機盲測順序；凍結後計畫不可再修改。
      </p>

      <dl className="msa-review-grid">
        <div>
          <dt>方法</dt>
          <dd>{summary.methodLabel}（{summary.methodCode}）</dd>
        </div>
        <div>
          <dt>設計</dt>
          <dd className="msa-num">
            {summary.partCount} 零件 × {summary.appraiserCount} 評價人
            × {summary.trialCount} 試驗
          </dd>
        </div>
        <div>
          <dt>隨機種子</dt>
          <dd className="msa-num">{summary.randomSeed}</dd>
        </div>
        <div>
          <dt>百分比口徑</dt>
          <dd>{summary.percentBasis}</dd>
        </div>
        <div>
          <dt>判定準則</dt>
          <dd>{summary.criteriaProfileName ?? '尚未選擇'}</dd>
        </div>
      </dl>

      <h3>設備資格</h3>
      <table className="msa-review-table">
        <caption>設備資格與校驗狀態</caption>
        <thead>
          <tr>
            <th scope="col">角色</th>
            <th scope="col">設備編號</th>
            <th scope="col">名稱</th>
            <th scope="col">校驗狀態</th>
            <th scope="col">阻擋原因</th>
          </tr>
        </thead>
        <tbody>
          {summary.equipment.map((item) => (
            <tr key={`${item.role}-${item.equipmentNo}`}>
              <td>{item.role}</td>
              <td className="msa-num">{item.equipmentNo}</td>
              <td>{item.name}</td>
              <td>{item.calibrationStatus}</td>
              <td>{item.blockReason ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {blocked && (
        <div className="msa-state msa-state--error" role="alert">
          <p>以下條件未滿足，無法凍結計畫：</p>
          <ul>
            {blockers.map((blocker) => (
              <li key={blocker.code}>{blocker.message}</li>
            ))}
          </ul>
        </div>
      )}

      {children}

      <button
        type="button"
        className="msa-primary-action"
        disabled={blocked || isFreezing || !onFreeze}
        onClick={onFreeze}
      >
        {isFreezing ? '凍結中…' : '凍結研究計畫'}
      </button>
    </section>
  );
}
