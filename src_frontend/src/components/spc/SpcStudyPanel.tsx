import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Alert, Badge, Button, Card } from 'react-bootstrap';
import { useAuth } from '../../context/useAuth';
import {
  fetchSpcEvent, useAnalyzeSpcStudy, useApproveSpcStudy, useConfirmSpcTimeModel,
  useRejectSpcStudy, useRetireSpcLimit, useSaveSpcOcap, useSpcAssignees,
  useSpcStudies, useSpcStudy, useSubmitSpcStudy,
} from '../../hooks/useSpcStudies';
import type {
  SpcChartData, SpcEventSummary, SpcStudyResult,
} from '../../types';
import { replaceEvent, replaceEventOcap } from '../../utils/spcEventState';
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
  onVersionChange: (version: SpcStudyResult | null) => void;
}

const stabilityBadge = (label: string, stable: boolean | null | undefined) => (
  <Badge className="spc-signal-badge" bg={stable === true ? 'success' : stable === false ? 'danger' : 'secondary'}>
    {label}{stable === true ? '穩定' : stable === false ? '失控' : '未判定'}
  </Badge>
);

const SpcStudyPanel = ({
  source, filters, preview, version: selectedVersion, studyType = 'retrospective', onVersionChange,
}: SpcStudyPanelProps) => {
  const { hasPermission } = useAuth();
  const analyze = useAnalyzeSpcStudy();
  const submit = useSubmitSpcStudy();
  const confirmTimeModel = useConfirmSpcTimeModel();
  const approve = useApproveSpcStudy();
  const reject = useRejectSpcStudy();
  const retire = useRetireSpcLimit();
  const { data: studies = [] } = useSpcStudies();
  const matchingStudy = studies.find(study =>
    study.source === source
    && study.study_type === studyType
    && study.process_stream_key === preview?.process_stream_key);
  const versionMatchesPreview = !selectedVersion || Boolean(
    preview?.process_stream_key
    && selectedVersion.process_stream_key === preview.process_stream_key
    && (
      selectedVersion.study_type !== 'ongoing'
      || Boolean(preview.data_hash && selectedVersion.data_hash === preview.data_hash)
    )
  );
  const version = versionMatchesPreview ? selectedVersion : null;
  const detailStudyId = version?.study_id ?? matchingStudy?.id ?? null;
  const { data: savedStudy } = useSpcStudy(detailStudyId);
  const [modalAction, setModalAction] = useState<SpcWorkflowAction | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<SpcEventSummary | null>(null);
  const displayedVersionRef = useRef({
    studyId: version?.study_id ?? null,
    versionId: version?.id ?? null,
    processStreamKey: version?.process_stream_key ?? null,
  });
  const editingEventIdRef = useRef<number | null>(selectedEvent?.id ?? null);

  useLayoutEffect(() => {
    displayedVersionRef.current = {
      studyId: version?.study_id ?? null,
      versionId: version?.id ?? null,
      processStreamKey: version?.process_stream_key ?? null,
    };
    editingEventIdRef.current = selectedEvent?.id ?? null;
  }, [selectedEvent?.id, version?.id, version?.process_stream_key, version?.study_id]);

  useEffect(() => {
    if (!versionMatchesPreview) {
      onVersionChange(null);
      return;
    }
    if (version || !savedStudy?.versions?.length) return;
    const latest = savedStudy.versions[savedStudy.versions.length - 1];
    if (preview?.process_stream_key && latest.process_stream_key === preview.process_stream_key) {
      onVersionChange(latest);
    }
  }, [onVersionChange, preview?.process_stream_key, savedStudy, version, versionMatchesPreview]);

  const canManage = hasPermission('spc.manage');
  const saveOcap = useSaveSpcOcap();
  const assignees = useSpcAssignees(Boolean(selectedEvent && canManage));
  const canApprove = hasPermission('spc.approve');
  const canView = hasPermission('spc.view') || canManage || canApprove;
  const stability = version?.stability ?? preview?.stability;
  const distribution = version?.distribution ?? preview?.distribution;
  const timeModel = version?.time_model ?? preview?.time_model;
  const capability = version?.capability ?? preview?.capability;
  const applicability = version?.applicability ?? preview?.applicability;
  const pending = submit.isPending || confirmTimeModel.isPending || approve.isPending
    || reject.isPending || retire.isPending;
  const activeLimit = version?.monitoring_limit
    ?? version?.limit_versions?.find(limit => limit.status === 'active');
  const effectiveStudyType = version?.study_type ?? matchingStudy?.study_type ?? studyType;

  const handleSelectEvent = (event: SpcEventSummary) => {
    saveOcap.reset();
    setSelectedEvent(event);
  };

  const handleOcapHide = () => {
    if (saveOcap.isPending) return;
    saveOcap.reset();
    setSelectedEvent(null);
  };

  const isCurrentVersion = (studyId: number, versionId: number, processStreamKey: string) => {
    const current = displayedVersionRef.current;
    return current.studyId === studyId
      && current.versionId === versionId
      && current.processStreamKey === processStreamKey;
  };

  const handleAnalyze = async () => {
    const created = await analyze.mutateAsync({ source, filters, study_type: studyType });
    onVersionChange(created);
  };

  const handleOngoingAnalyze = async () => {
    const created = await analyze.mutateAsync({ source, filters, study_type: 'ongoing' });
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
          canManage={canManage && effectiveStudyType === 'retrospective'}
          canApprove={canApprove && effectiveStudyType === 'retrospective'}
          analyzing={analyze.isPending}
          onAnalyze={effectiveStudyType === 'ongoing' ? handleOngoingAnalyze : handleAnalyze}
          onAction={setModalAction}
          onShowHistory={() => setShowHistory(true)}
        />

        {canView && activeLimit && effectiveStudyType !== 'ongoing' && (
          <div className="d-flex justify-content-end mt-2">
            <Button
              size="sm"
              variant="outline-success"
              disabled={analyze.isPending}
              onClick={handleOngoingAnalyze}
            >
              以正式界限監控目前資料
            </Button>
          </div>
        )}

        {effectiveStudyType === 'ongoing' && (
          <div className="d-flex justify-content-end mt-2">
            <Button
              size="sm"
              variant="outline-secondary"
              onClick={() => onVersionChange(null)}
            >
              返回回溯基準
            </Button>
          </div>
        )}

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
                <Button key={event.id} size="sm" variant={event.status === 'closed' ? 'outline-success' : 'outline-danger'} onClick={() => handleSelectEvent(event)}>
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
          filters={version.filters}
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
          key={selectedEvent.id}
          show
          eventId={selectedEvent.id}
          ocapId={selectedEvent.ocap?.id}
          initialValue={selectedEvent.ocap}
          pending={saveOcap.isPending}
          saveError={saveOcap.isError}
          assignees={assignees.data ?? []}
          assigneesLoading={assignees.isLoading}
          assigneesError={assignees.isError}
          onHide={handleOcapHide}
          onSave={input => {
            if (!version) return;
            const savedVersion = version;
            const savedContext = {
              eventId: input.eventId,
              studyId: savedVersion.study_id,
              versionId: savedVersion.id,
              processStreamKey: savedVersion.process_stream_key,
            };
            saveOcap.mutate(input, {
              onSuccess: async ocap => {
                if (
                  ocap.event_id !== savedContext.eventId
                  || editingEventIdRef.current !== savedContext.eventId
                  || !isCurrentVersion(
                    savedContext.studyId,
                    savedContext.versionId,
                    savedContext.processStreamKey,
                  )
                ) return;

                const localVersion = replaceEventOcap(
                  savedVersion, savedContext.eventId, ocap,
                );
                onVersionChange(localVersion);
                setSelectedEvent(null);

                let serverEvent: SpcEventSummary;
                try {
                  serverEvent = await fetchSpcEvent(savedContext.eventId);
                } catch {
                  return;
                }
                if (!isCurrentVersion(
                  savedContext.studyId,
                  savedContext.versionId,
                  savedContext.processStreamKey,
                )) return;
                if (serverEvent.id !== savedContext.eventId) return;
                onVersionChange(replaceEvent(localVersion, serverEvent));
              },
            });
          }}
        />
      )}
    </Card>
  );
};

export default SpcStudyPanel;
