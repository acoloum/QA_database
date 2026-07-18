import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from 'react-bootstrap';
import { useAuth } from '../../context/useAuth';
import {
  useAnalyzeSpcStudy, useApproveSpcStudy, useConfirmSpcTimeModel,
  useRejectSpcStudy, useRetireSpcLimit, useSaveSpcOcap, useSpcStudies,
  useSpcStudy, useSubmitSpcStudy,
} from '../../hooks/useSpcStudies';
import type { SpcChartData, SpcEventSummary, SpcStudyResult } from '../../types';
import SpcBaselineApprovalModal, { type SpcWorkflowAction } from './SpcBaselineApprovalModal';
import SpcStudyHistoryOffcanvas from './SpcStudyHistoryOffcanvas';
import SpcStudyWorkflowBar from './SpcStudyWorkflowBar';
import SpcOcapOffcanvas from './SpcOcapOffcanvas';
import './spcStudy.css';

interface SpcStudyPanelProps {
  source: 'shipping' | 'patrol';
  filters: Record<string, unknown>;
  preview?: SpcChartData | null;
  version: SpcStudyResult | null;
  studyType?: 'retrospective' | 'ongoing';
  onVersionChange: (version: SpcStudyResult) => void;
}

const stabilityBadge = (label: string, stable: boolean | null | undefined) => (
  <Badge className="spc-signal-badge" bg={stable === true ? 'success' : stable === false ? 'danger' : 'secondary'}>
    {label}{stable === true ? '穩定' : stable === false ? '失控' : '未判定'}
  </Badge>
);

const SpcStudyPanel = ({
  source, filters, preview, version, studyType = 'retrospective', onVersionChange,
}: SpcStudyPanelProps) => {
  const { hasPermission } = useAuth();
  const analyze = useAnalyzeSpcStudy();
  const submit = useSubmitSpcStudy();
  const confirmTimeModel = useConfirmSpcTimeModel();
  const approve = useApproveSpcStudy();
  const reject = useRejectSpcStudy();
  const retire = useRetireSpcLimit();
  const saveOcap = useSaveSpcOcap();
  const { data: studies = [] } = useSpcStudies();
  const matchingStudy = studies.find(study =>
    study.source === source && study.process_stream_key === preview?.process_stream_key);
  const { data: savedStudy } = useSpcStudy(matchingStudy?.id ?? null);
  const [modalAction, setModalAction] = useState<SpcWorkflowAction | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<SpcEventSummary | null>(null);

  useEffect(() => {
    if (version || !savedStudy?.versions?.length) return;
    onVersionChange(savedStudy.versions[savedStudy.versions.length - 1]);
  }, [onVersionChange, savedStudy, version]);

  const canManage = hasPermission('spc.manage');
  const canApprove = hasPermission('spc.approve');
  const canView = hasPermission('spc.view') || canManage || canApprove;
  const stability = version?.stability ?? preview?.stability;
  const distribution = version?.distribution ?? preview?.distribution;
  const timeModel = version?.time_model ?? preview?.time_model;
  const capability = version?.capability ?? preview?.capability;
  const applicability = version?.applicability ?? preview?.applicability;
  const pending = submit.isPending || confirmTimeModel.isPending || approve.isPending
    || reject.isPending || retire.isPending;
  const activeLimit = version?.limit_versions?.find(limit => limit.status === 'active');
  const effectiveStudyType = matchingStudy?.study_type ?? studyType;

  const handleAnalyze = async () => {
    const created = await analyze.mutateAsync({ source, filters });
    onVersionChange(created);
  };

  const handleAction = async (reason: string, model?: 'A1' | 'A2') => {
    if (!version || !modalAction) return;
    if (modalAction === 'time-model' && model) {
      const updated = await confirmTimeModel.mutateAsync({ versionId: version.id, studyId: version.study_id, model, reason });
      onVersionChange({ ...version, ...updated, samples: version.samples });
    } else if (modalAction === 'submit') {
      const updated = await submit.mutateAsync({ versionId: version.id, studyId: version.study_id, reason });
      onVersionChange({ ...version, ...updated, samples: version.samples });
    } else if (modalAction === 'reject') {
      const updated = await reject.mutateAsync({ versionId: version.id, studyId: version.study_id, reason });
      onVersionChange({ ...version, ...updated, samples: version.samples });
    } else if (modalAction === 'approve') {
      const limit = await approve.mutateAsync({ versionId: version.id, studyId: version.study_id, reason });
      onVersionChange({
        ...version,
        status: 'active',
        limit_versions: [{ ...limit, events: limit.events ?? [] }],
      });
    } else if (modalAction === 'retire' && activeLimit) {
      await retire.mutateAsync({ limitId: activeLimit.id, studyId: version.study_id, reason });
      onVersionChange({
        ...version,
        status: 'retired',
        limit_versions: version.limit_versions?.map(limit =>
          limit.id === activeLimit.id ? { ...limit, status: 'retired' } : limit),
      });
    }
    setModalAction(null);
  };

  const reasons = applicability?.reasons ?? [];
  return (
    <Card className="spc-study-panel mb-3">
      <Card.Body>
        <div className="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-3">
          <div>
            <div className="spc-eyebrow">AIAG &amp; VDA SPC · 2026.1</div>
            <div className="d-flex align-items-center gap-2 flex-wrap">
              <h5 className="mb-0">SPC 研究與基準</h5>
              <Badge bg={effectiveStudyType === 'ongoing' ? 'success' : 'secondary'}>
                {effectiveStudyType === 'ongoing' ? '持續 SPC' : '回溯研究'}
              </Badge>
              {version && <Badge bg="light" text="dark">研究 v{version.version_no}</Badge>}
            </div>
          </div>
          {version?.data_hash && <code className="spc-hash spc-hash-short" title={version.data_hash}>{version.data_hash.slice(0, 12)}…</code>}
        </div>

        <SpcStudyWorkflowBar
          version={version}
          canView={canView}
          canManage={canManage}
          canApprove={canApprove}
          analyzing={analyze.isPending}
          onAnalyze={handleAnalyze}
          onAction={setModalAction}
          onShowHistory={() => setShowHistory(true)}
        />

        {(stability || distribution || timeModel) && (
          <div className="spc-diagnostic-strip mt-3">
            {stabilityBadge('位置圖', stability?.location?.stable)}
            {stabilityBadge('變異圖', stability?.variation?.stable)}
            <Badge className="spc-signal-badge" bg={distribution?.accepted ? 'success' : 'warning'} text={distribution?.accepted ? undefined : 'dark'}>
              {distribution?.accepted ? `分布：${distribution.label}` : '分布尚未確認'}
            </Badge>
            <Badge className="spc-signal-badge" bg={timeModel?.confirmed ? 'success' : 'info'}>
              時間模型 {timeModel?.model ?? timeModel?.candidate ?? '未判定'}
            </Badge>
            {capability?.available && capability.applicable === 'capability' && (
              <Badge className="spc-signal-badge" bg="success">Cp/Cpk 可報告</Badge>
            )}
            {capability?.available && capability.applicable === 'performance' && (
              <Badge className="spc-signal-badge" bg="secondary">僅 Pp/Ppk</Badge>
            )}
          </div>
        )}

        {reasons.length > 0 && (
          <Alert variant="warning" className="mt-3 mb-0 py-2">
            <strong>目前資料不可建立正式基準：</strong>{reasons.map(reason => reason.message).join('；')}
          </Alert>
        )}

        {activeLimit?.events && activeLimit.events.length > 0 && (
          <div className="spc-event-list mt-3">
            <strong className="small">正式失控事件</strong>
            <div className="d-flex gap-2 flex-wrap mt-2">
              {activeLimit.events.map(event => (
                <Button key={event.id} size="sm" variant={event.status === 'closed' ? 'outline-success' : 'outline-danger'} onClick={() => setSelectedEvent(event)}>
                  事件 #{event.id} · {event.chart_kind === 'location' ? '位置圖' : '變異圖'} · {event.rule_code}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Card.Body>

      {version && modalAction && (
        <SpcBaselineApprovalModal
          show
          action={modalAction}
          source={source}
          filters={filters}
          version={version}
          pending={pending}
          onHide={() => setModalAction(null)}
          onConfirm={handleAction}
        />
      )}
      {version && showHistory && (
        <SpcStudyHistoryOffcanvas show studyId={version.study_id} onHide={() => setShowHistory(false)} />
      )}
      {selectedEvent && (
        <SpcOcapOffcanvas
          show
          eventId={selectedEvent.id}
          ocapId={selectedEvent.ocap?.id}
          initialValue={selectedEvent.ocap}
          pending={saveOcap.isPending}
          onHide={() => setSelectedEvent(null)}
          onSave={input => saveOcap.mutate(input, { onSuccess: () => setSelectedEvent(null) })}
        />
      )}
    </Card>
  );
};

export default SpcStudyPanel;
