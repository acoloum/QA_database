import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import MsaRiskCard, { type MsaSeverity } from '../../components/msa/MsaRiskCard';
import MsaWorkQueue, {
  type MsaWorkItem,
} from '../../components/msa/MsaWorkQueue';
import { useAuth } from '../../context/useAuth';
import { useMsaEquipment } from '../../hooks/useMsaEquipment';
import {
  useMsaRestudyRequests,
  useMsaStudies,
} from '../../hooks/useMsaStudies';
import type {
  MeasurementEquipment,
  MsaRestudyRequest,
  MsaStudy,
} from '../../types/msa';
import './msa.css';

const STUDY_PARAMS = {
  page: 1, page_size: 100, sort: 'updated_at', order: 'desc',
} as const;

const EQUIPMENT_PARAMS = {
  page: 1, page_size: 100, sort: 'risk', order: 'asc',
} as const;

const today = () => new Date().toISOString().slice(0, 10);

const blockingEquipment = (item: MeasurementEquipment) =>
  item.calibration_status === 'failed'
  || item.calibration_status === 'expired'
  || item.calibration_status === 'missing';

const studyWorkItems = (studies: MsaStudy[]): MsaWorkItem[] => studies.flatMap(
  (study): MsaWorkItem[] => {
    if (study.status === 'submitted') {
      return [{
        id: `study-${study.id}-approval`,
        category: 'approval' as const,
        severity: 'warning' as MsaSeverity,
        title: '待核准',
        subject: `${study.study_no}｜${study.characteristic}`,
        owner: null,
        dueDate: null,
        nextStep: '由未參與本研究的人員核准或退回',
        href: `/msa/studies/${study.id}`,
      }];
    }
    if (study.status === 'rejected') {
      return [{
        id: `study-${study.id}-rejected`,
        category: 'study_progress' as const,
        severity: 'warning' as MsaSeverity,
        title: '已退回，需重新分析',
        subject: `${study.study_no}｜${study.characteristic}`,
        owner: null,
        dueDate: null,
        nextStep: '修正資料後重新分析並再次送審',
        href: `/msa/studies/${study.id}`,
      }];
    }
    if (
      study.status === 'collecting' || study.status === 'ready'
      || study.status === 'ready_for_analysis'
    ) {
      return [{
        id: `study-${study.id}-progress`,
        category: 'study_progress' as const,
        severity: 'info' as MsaSeverity,
        title: study.status === 'ready_for_analysis' ? '可進行分析' : '資料收集中',
        subject: `${study.study_no}｜${study.characteristic}`,
        owner: null,
        dueDate: study.next_due_date,
        nextStep: study.status === 'ready_for_analysis'
          ? '執行分析並確認判定'
          : '完成剩餘盲測讀值',
        href: `/msa/studies/${study.id}`,
      }];
    }
    return [];
  },
);

const equipmentWorkItems = (
  equipment: MeasurementEquipment[],
  canViewCalibration: boolean,
): MsaWorkItem[] => equipment.filter(blockingEquipment).map((item) => ({
  id: `equipment-${item.id}`,
  category: 'equipment_block' as const,
  severity: 'critical' as MsaSeverity,
  title: item.calibration_status === 'failed' ? '校驗失敗' : '校驗逾期',
  subject: `${item.equipment_no}｜${item.name}`,
  owner: item.custodian,
  dueDate: item.next_calibration_date,
  nextStep: '完成校驗並核准後才可用於正式研究',
  href: canViewCalibration ? '/measurement-equipment' : null,
}));

const restudyWorkItems = (
  requests: MsaRestudyRequest[],
): MsaWorkItem[] => requests
  .filter((request) => request.status === 'open')
  .map((request) => ({
    id: `restudy-${request.id}`,
    category: 'restudy' as const,
    severity: (
      request.due_date && request.due_date < today() ? 'critical' : 'info'
    ) as MsaSeverity,
    title: request.due_date && request.due_date < today()
      ? '再研究逾期' : '再研究要求',
    subject: `研究 #${request.source_study_id}｜${request.trigger_type}`,
    owner: null,
    dueDate: request.due_date,
    nextStep: '由再研究要求建立新研究',
    href: '/msa/studies',
  }));

export default function MsaWorkspacePage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('msa.manage');
  const canViewCalibration = hasPermission('calibration.view');
  const studies = useMsaStudies(STUDY_PARAMS);
  const equipment = useMsaEquipment(EQUIPMENT_PARAMS);
  const restudies = useMsaRestudyRequests({ page: 1, page_size: 100 });

  const isLoading =
    studies.isLoading || equipment.isLoading || restudies.isLoading;
  const isError = studies.isError || equipment.isError || restudies.isError;

  const items = useMemo(() => [
    ...equipmentWorkItems(
      equipment.data?.items ?? [],
      canViewCalibration,
    ),
    ...studyWorkItems(studies.data?.items ?? []),
    ...restudyWorkItems(restudies.data?.items ?? []),
  ], [
    equipment.data,
    studies.data,
    restudies.data,
    canViewCalibration,
  ]);

  const counts = useMemo(() => {
    const studyItems = studies.data?.items ?? [];
    const equipmentItems = equipment.data?.items ?? [];
    const restudyItems = restudies.data?.items ?? [];
    return {
      mine: studyItems.filter((study) => [
        'draft', 'ready', 'collecting', 'ready_for_analysis', 'rejected',
      ].includes(study.status)).length,
      approval: studyItems.filter((study) => study.status === 'submitted').length,
      blocked: equipmentItems.filter(blockingEquipment).length,
      overdue: restudyItems.filter(
        (request) => request.status === 'open'
          && request.due_date != null && request.due_date < today(),
      ).length,
    };
  }, [studies.data, equipment.data, restudies.data]);

  return (
    <main className="msa-shell" aria-labelledby="msa-title">
      <header className="msa-shell__header">
        <div>
          <p className="msa-eyebrow">量測系統分析 / 受控證據入口</p>
          <h1 id="msa-title">MSA 工作台</h1>
          <p>先處理會擋住正式判定的風險，再往下推進研究。</p>
        </div>
        {canManage && (
          <Link className="msa-side-action" to="/msa/studies/new">
            建立研究
          </Link>
        )}
      </header>

      {isLoading && (
        <div className="msa-state" role="status">正在讀取 MSA 工作</div>
      )}
      {isError && (
        <div className="msa-state msa-state--error" role="alert">
          <p>無法載入 MSA 工作台</p>
          <button
            type="button"
            onClick={() => {
              void studies.refetch();
              void equipment.refetch();
              void restudies.refetch();
            }}
          >
            重試
          </button>
        </div>
      )}

      {!isLoading && !isError && (
        <>
          <section className="msa-risk-grid" aria-label="MSA 風險總覽">
            <MsaRiskCard
              label="我的研究工作"
              count={counts.mine}
              hint="草稿、收集中與待重新分析的研究"
              severity={counts.mine > 0 ? 'info' : 'normal'}
            />
            <MsaRiskCard
              label="待核准"
              count={counts.approval}
              hint="已送審、等待獨立人員核准"
              severity={counts.approval > 0 ? 'warning' : 'normal'}
            />
            <MsaRiskCard
              label="設備阻擋"
              count={counts.blocked}
              hint="校驗失敗、逾期或缺少證據的設備"
              severity={counts.blocked > 0 ? 'critical' : 'normal'}
            />
            <MsaRiskCard
              label="再研究逾期"
              count={counts.overdue}
              hint="已過期限仍未承接的再研究要求"
              severity={counts.overdue > 0 ? 'critical' : 'normal'}
            />
          </section>

          <div className="msa-layout">
            <section className="msa-panel" aria-labelledby="msa-queue-title">
              <h2 id="msa-queue-title">工作佇列</h2>
              <p>依阻擋風險與期限排序，先顯示會讓研究無法放行的項目。</p>
              <MsaWorkQueue items={items} />
            </section>

            <nav className="msa-side" aria-label="MSA 捷徑">
              {canManage && (
                <Link to="/msa/studies/new">
                  <strong>建立研究</strong>
                  <small>選擇方法並產生盲測設計</small>
                </Link>
              )}
              <Link to="/msa/studies">
                <strong>研究清單</strong>
                <small>查詢所有 MSA 研究與結果版本</small>
              </Link>
              {canViewCalibration && (
                <Link to="/measurement-equipment">
                  <strong>設備清單</strong>
                  <small>檢查校驗失敗、逾期與待確認設備</small>
                </Link>
              )}
              <Link to="/msa/criteria">
                <strong>判定準則</strong>
                <small>檢視版本化門檻與核准歷程</small>
              </Link>
              <Link to="/msa/imports">
                <strong>設備匯入紀錄</strong>
                <small>追查批次來源指紋與逐列處置</small>
              </Link>
            </nav>
          </div>
        </>
      )}
    </main>
  );
}
