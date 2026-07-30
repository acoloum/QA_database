import { useMemo, useState } from 'react';
import { useParams } from 'react-router';

import MsaAttributeCharts from '../../components/msa/charts/MsaAttributeCharts';
import MsaBiasLinearityCharts from '../../components/msa/charts/MsaBiasLinearityCharts';
import MsaGrrCharts from '../../components/msa/charts/MsaGrrCharts';
import MsaNonrepeatableCharts from '../../components/msa/charts/MsaNonrepeatableCharts';
import MsaStabilityCharts from '../../components/msa/charts/MsaStabilityCharts';
import MsaDecisionModal from '../../components/msa/MsaDecisionModal';
import MsaEvidenceLayers, {
  MsaMethodEvidence,
  flattenStatistics,
  type MsaEvidenceLayer,
} from '../../components/msa/MsaEvidenceLayers';
import MsaResultHero from '../../components/msa/MsaResultHero';
import MsaWorkflowBar, {
  type MsaWorkflowAction,
} from '../../components/msa/MsaWorkflowBar';
import { useAuth } from '../../context/useAuth';
import {
  useApproveMsaResult,
  useDownloadMsaReport,
  useMsaStudy,
  useRejectMsaResult,
  useSubmitMsaResult,
  useVoidMsaResult,
} from '../../hooks/useMsaStudies';
import type { MsaResultVersion } from '../../types/msa';
import './msa.css';

const chartsFor = (result: MsaResultVersion) => {
  switch (result.method_code) {
    case 'MSA4_GRR_RANGE_1_0':
    case 'MSA4_GRR_XBAR_R_1_0':
    case 'MSA4_GRR_ANOVA_1_0':
      return <MsaGrrCharts result={result} />;
    case 'MSA4_BIAS_1_0':
    case 'MSA4_LINEARITY_1_0':
      return <MsaBiasLinearityCharts result={result} />;
    case 'MSA4_STABILITY_1_0':
      return <MsaStabilityCharts result={result} />;
    case 'MSA4_ATTRIBUTE_1_0':
      return <MsaAttributeCharts result={result} />;
    case 'MSA4_NONREPEATABLE_1_0':
      return <MsaNonrepeatableCharts result={result} />;
    default:
      return <p>這個方法尚未提供圖表。</p>;
  }
};

interface MsaResultPageProps {
  /** 由呼叫端提供結果版本；頁面本身不重新分析。 */
  result: MsaResultVersion;
  isParticipant?: boolean;
}

export default function MsaResultPage({
  result, isParticipant = false,
}: MsaResultPageProps) {
  const { studyId } = useParams<{ studyId: string }>();
  const { hasPermission } = useAuth();
  const study = useMsaStudy(studyId ? Number(studyId) : result.study_id);
  const submit = useSubmitMsaResult();
  const approve = useApproveMsaResult();
  const reject = useRejectMsaResult();
  const voidResult = useVoidMsaResult();
  const download = useDownloadMsaReport();

  const [action, setAction] = useState<MsaWorkflowAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const mutations = {
    submit, approve, reject, void: voidResult,
  } as const;
  const isBusy = Object.values(mutations).some(
    (mutation) => mutation.isPending,
  );

  const layers: MsaEvidenceLayer[] = useMemo(() => [
    {
      id: 'charts',
      title: '圖表與摘要',
      question: '這個量測系統的表現長什麼樣子？',
      content: chartsFor(result),
    },
    {
      id: 'method',
      title: '方法與統計證據',
      question: '這個結論是用什麼方法、什麼數字算出來的？',
      content: <MsaMethodEvidence result={result} />,
    },
    {
      id: 'criteria',
      title: '判定準則快照',
      question: '當時是用哪一版準則判定的？',
      content: (
        <table className="msa-review-table">
          <caption>判定準則快照</caption>
          <thead>
            <tr><th scope="col">項目</th><th scope="col">值</th></tr>
          </thead>
          <tbody>
            {flattenStatistics(result.criteria_snapshot).map((row) => (
              <tr key={row.path}>
                <td>{row.path}</td>
                <td className="msa-num">{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ),
    },
    {
      id: 'audit',
      title: '稽核指紋',
      question: '這份結果能不能被追溯與驗證？',
      content: (
        <dl className="msa-review-grid">
          <div><dt>結果版本ID</dt><dd className="msa-num">{result.id}</dd></div>
          <div><dt>資料雜湊</dt><dd className="msa-num">{result.data_hash}</dd></div>
          <div><dt>方法代碼</dt><dd>{result.method_code}</dd></div>
          <div><dt>方法版本</dt><dd>{result.method_version}</dd></div>
          <div><dt>程式版本</dt><dd>{result.code_version}</dd></div>
          <div>
            <dt>建立時間</dt>
            <dd className="msa-num">{result.created_at.slice(0, 19)}</dd>
          </div>
        </dl>
      ),
    },
  ], [result]);

  const requiresConditionalPlan =
    action === 'submit'
    && result.conclusion.system_disposition === 'conditionally_acceptable';

  const runAction = (payload: {
    reason: string; actions?: string[]; due_date?: string;
  }) => {
    if (!action) return;
    setActionError(null);
    void mutations[action].mutateAsync({
      resultId: result.id,
      expected_status: result.status,
      ...payload,
    }).then(() => setAction(null))
      .catch((error: unknown) => setActionError(
        error instanceof Error ? error.message : '動作未完成，請重新載入。',
      ));
  };

  return (
    <main className="msa-shell" aria-labelledby="msa-result-title">
      <header className="msa-shell__header">
        <div>
          <p className="msa-eyebrow">量測系統分析 / 結果</p>
          <h1 id="msa-result-title">分析結果</h1>
          <p>報告與畫面讀的是同一份已保存的結果版本，不會重新計算。</p>
        </div>
      </header>

      <MsaResultHero
        result={result}
        studyNo={study.data?.study_no ?? `研究 #${result.study_id}`}
        characteristic={study.data?.characteristic ?? ''}
      />

      <MsaWorkflowBar
        result={result}
        canManage={hasPermission('msa.manage')}
        canApprove={hasPermission('msa.approve')}
        isParticipant={isParticipant}
        isBusy={isBusy}
        onAction={(next) => { setActionError(null); setAction(next); }}
        onDownload={(format) => void download.mutateAsync({
          resultId: result.id, format, studyNo: study.data?.study_no,
        })}
      />

      {result.warnings.length > 0 && (
        <div className="msa-state" role="note">
          <p>分析警告</p>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        </div>
      )}

      <MsaEvidenceLayers layers={layers} />

      {action && (
        <MsaDecisionModal
          action={action}
          expectedStatus={result.status}
          requiresConditionalPlan={requiresConditionalPlan}
          isBusy={isBusy}
          errorMessage={actionError}
          onCancel={() => { setAction(null); setActionError(null); }}
          onConfirm={runAction}
        />
      )}
    </main>
  );
}
