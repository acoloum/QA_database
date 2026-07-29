import { useState } from 'react';

import CriteriaVersionTimeline from '../../components/msa/CriteriaVersionTimeline';
import { useAuth } from '../../context/useAuth';
import {
  useApproveMsaCriteriaVersion,
  useCreateMsaCriteriaVersion,
  useMsaCriteria,
} from '../../hooks/useMsaCriteria';
import type {
  MsaCriteriaListParams,
  MsaCriteriaProfile,
  MsaCriteriaVersion,
} from '../../types/msa';
import '../equipment/measurementEquipment.css';

/** 研究類型代碼對應的中文名稱；未列出的代碼直接顯示代碼本身。 */
const STUDY_TYPE_LABELS: Record<string, string> = {
  range: '全距法',
  xbar_r: 'Xbar-R',
  crossed_anova: '交叉式 ANOVA',
  bias: '偏倚',
  linearity: '線性',
  stability: '穩定性',
  attribute: '計數型',
  nonreplicable: '不可重複',
};

const errorText = (error: unknown, fallback: string) => (
  error instanceof Error ? error.message : fallback
);

const studyTypeText = (types: string[]) => (
  types.length === 0
    ? '未限定研究類型'
    : types.map((type) => STUDY_TYPE_LABELS[type] ?? type).join('、')
);

function ProfileScope({ profile }: { profile: MsaCriteriaProfile }) {
  return (
    <dl className="msa-definition-grid">
      <div>
        <dt>適用顧客</dt>
        <dd>{profile.customer_scope || '全部顧客'}</dd>
      </div>
      <div>
        <dt>適用產品</dt>
        <dd>{profile.product_scope || '全部產品'}</dd>
      </div>
      <div>
        <dt>適用產品族</dt>
        <dd>{profile.product_family_scope || '全部產品族'}</dd>
      </div>
      <div>
        <dt>品質特性</dt>
        <dd>{profile.characteristic_scope || '全部特性'}</dd>
      </div>
      <div>
        <dt>特性重要度</dt>
        <dd>{profile.characteristic_importance || '未分級'}</dd>
      </div>
      <div>
        <dt>適用研究類型</dt>
        <dd>{studyTypeText(profile.applicable_study_types)}</dd>
      </div>
    </dl>
  );
}

export default function MsaCriteriaPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('msa.manage');
  const canApprove = hasPermission('msa.approve');
  const [params] = useState<MsaCriteriaListParams>({
    page: 1,
    page_size: 25,
    sort: 'name',
    order: 'asc',
  });
  const query = useMsaCriteria(params);
  const approveVersion = useApproveMsaCriteriaVersion();
  const createVersion = useCreateMsaCriteriaVersion();

  const [pendingApproval, setPendingApproval] = useState<MsaCriteriaVersion | null>(null);
  const [reason, setReason] = useState('');
  const [approveError, setApproveError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const profiles: MsaCriteriaProfile[] = query.data?.items ?? [];

  const closeApproval = () => {
    setPendingApproval(null);
    setReason('');
    setApproveError(null);
  };

  const submitApproval = () => {
    if (!pendingApproval || reason.trim().length === 0) return;
    setApproveError(null);
    void approveVersion.mutateAsync({
      versionId: pendingApproval.id,
      // 送出畫面上實際看到的狀態，讓後端能偵測期間被他人更新
      expected_status: 'draft',
      reason: reason.trim(),
    }).then(closeApproval).catch((error: unknown) => {
      setApproveError(errorText(error, '核准未完成，請重新載入後再試。'));
    });
  };

  const currentVersionNo = (profile: MsaCriteriaProfile) => (
    profile.versions.find((version) => version.id === profile.current_version_id)?.version_no
  );

  return (
    <main className="msa-page" aria-labelledby="criteria-title">
      <header className="msa-page__header">
        <div>
          <p className="msa-eyebrow">MSA / 判定準則治理</p>
          <h1 id="criteria-title">判定準則</h1>
          <p>核准後的準則版本即成為不可修改的判定依據；要調整門檻請建立新版本。</p>
        </div>
      </header>

      {query.isLoading && (
        <div className="msa-state" role="status">正在讀取判定準則</div>
      )}
      {query.isError && (
        <div className="msa-state msa-state--error" role="alert">
          <p>無法載入判定準則</p>
          <button type="button" onClick={() => void query.refetch()}>重試</button>
        </div>
      )}
      {!query.isLoading && !query.isError && profiles.length === 0 && (
        <div className="msa-state">
          <strong>尚未建立任何判定準則</strong>
          <p>由具 msa.manage 權限的人員建立準則設定與第一個版本。</p>
        </div>
      )}

      {profiles.map((profile) => {
        const versionNo = currentVersionNo(profile);
        return (
          <section key={profile.id} className="msa-criteria-profile" aria-label={profile.name}>
            <header>
              <div>
                <h2>{profile.name}</h2>
                <p className="msa-mono">
                  {versionNo ? `目前版本 v${versionNo}` : '尚無已核准版本'}
                </p>
              </div>
              {canManage && (
                <button
                  type="button"
                  className="msa-button msa-button--outline"
                  disabled={createVersion.isPending}
                  onClick={() => {
                    setCreateError(null);
                    void createVersion.mutateAsync({ profileId: profile.id })
                      .catch((error: unknown) => {
                        setCreateError(errorText(error, '版本未建立，請稍後再試。'));
                      });
                  }}
                >
                  以目前預設新增版本
                </button>
              )}
            </header>

            <ProfileScope profile={profile} />

            <CriteriaVersionTimeline
              profile={profile}
              onApprove={canApprove ? (version) => {
                setReason('');
                setApproveError(null);
                setPendingApproval(version);
              } : undefined}
            />
          </section>
        );
      })}

      {createError && <p className="msa-inline-error" role="alert">{createError}</p>}

      {pendingApproval && (
        <div className="msa-dialog-backdrop">
          <div
            className="msa-create-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="approve-criteria-title"
          >
            <header>
              <h2 id="approve-criteria-title">
                核准 v{pendingApproval.version_no}
              </h2>
              <button
                type="button"
                className="msa-button msa-button--quiet"
                onClick={closeApproval}
              >
                取消
              </button>
            </header>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                submitApproval();
              }}
            >
              <p className="msa-help">
                核准後這個版本將成為目前判定依據，且不可再修改。
              </p>
              <label>
                核准理由
                <textarea
                  value={reason}
                  required
                  rows={3}
                  autoFocus
                  onChange={(event) => setReason(event.target.value)}
                />
              </label>
              {approveError && <p className="msa-inline-error" role="alert">{approveError}</p>}
              <button
                type="submit"
                className="msa-button msa-button--primary"
                disabled={reason.trim().length === 0 || approveVersion.isPending}
              >
                確認核准
              </button>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
