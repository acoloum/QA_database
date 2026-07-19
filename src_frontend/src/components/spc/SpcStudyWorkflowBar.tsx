import { Badge, Button } from 'react-bootstrap';
import type { SpcStudyResult } from '../../types';
import { isMachinePerformanceResult } from '../../types/spc';
import type { SpcWorkflowAction } from './SpcBaselineApprovalModal';

interface SpcStudyWorkflowBarProps {
  version: SpcStudyResult | null;
  canView: boolean;
  canManage: boolean;
  canApprove: boolean;
  analyzing?: boolean;
  canAnalyze?: boolean;
  analyzeDisabledReason?: string;
  showTimeModelAction?: boolean;
  onAnalyze: () => void;
  onAction: (action: SpcWorkflowAction) => void;
  onShowHistory: () => void;
}

const baselineStages = [
  { status: 'draft', label: '候選' },
  { status: 'submitted', label: '送審' },
  { status: 'active', label: '生效' },
];

const researchStages = [
  { status: 'draft', label: '候選' },
  { status: 'submitted', label: '送審' },
  { status: 'approved', label: '核准研究' },
];

const stageIndex = (status: SpcStudyResult['status'] | undefined, research: boolean) => {
  if (research && status === 'approved') return 2;
  if (status === 'active' || status === 'retired') return 2;
  if (status === 'submitted') return 1;
  return status ? 0 : -1;
};

const SpcStudyWorkflowBar = ({
  version, canView, canManage, canApprove, analyzing = false, canAnalyze = true, analyzeDisabledReason,
  showTimeModelAction = true, onAnalyze, onAction, onShowHistory,
}: SpcStudyWorkflowBarProps) => {
  const confirmedModel = version?.time_model.model;
  const research = version?.analysis_family === 'machine'
    || (version?.analysis_family === 'variable' && version.time_model.confirmed
      && confirmedModel != null && !['A1', 'A2'].includes(confirmedModel));
  const machineCapability = version && isMachinePerformanceResult(version.capability)
    ? version.capability : null;
  const researchApprovable = version?.analysis_family === 'machine'
    ? Boolean(machineCapability?.approvable) : research;
  const stages = research ? researchStages : baselineStages;
  const current = stageIndex(version?.status, research);
  const candidate = version?.time_model.candidate;
  const canConfirmTimeModel = version?.status === 'draft'
    && !version.time_model.confirmed
    && (candidate === 'A1' || candidate === 'A2');
  const variableTimeModelUnconfirmed = version?.analysis_family === 'variable'
    && version.status === 'draft' && version.time_model.confirmed !== true;

  return (
    <div className="spc-workflow">
      <div className="spc-lifecycle" aria-label={research ? '研究生命週期' : 'SPC 基準生命週期'}>
        {stages.map((stage, index) => (
          <div key={stage.status} className={`spc-stage ${index <= current ? 'is-complete' : ''} ${index === current ? 'is-current' : ''}`}>
            <span className="spc-stage-dot">{index < current ? '✓' : index + 1}</span>
            <span>{stage.label}</span>
          </div>
        ))}
        {version?.status === 'rejected' && <Badge bg="danger">已退回</Badge>}
        {version?.status === 'retired' && <Badge bg="secondary">已停用</Badge>}
        {version?.analysis_family === 'machine' && version.status === 'submitted' && !researchApprovable && (
          <Badge bg="warning" text="dark">目前不可核准：{machineCapability?.reason_code ?? '研究資格未完成'}</Badge>
        )}
      </div>
      <div className="d-flex gap-2 flex-wrap justify-content-end">
        <Button size="sm" variant="outline-secondary" onClick={onShowHistory} disabled={!version}>版本歷程</Button>
        {(research ? canManage : canView) && (
          <span title={!canAnalyze ? analyzeDisabledReason : undefined}>
          <Button size="sm" variant="outline-primary" onClick={onAnalyze} disabled={analyzing || !canAnalyze} aria-describedby={!canAnalyze && analyzeDisabledReason ? 'spc-rebuild-disabled-reason' : undefined}>
            {analyzing ? '建立中…' : version ? '重建候選' : '建立候選'}
          </Button>
          {!canAnalyze && analyzeDisabledReason && <span id="spc-rebuild-disabled-reason" className="visually-hidden">{analyzeDisabledReason}</span>}
          </span>
        )}
        {!research && canApprove && showTimeModelAction && canConfirmTimeModel && (
          <Button size="sm" variant="outline-primary" onClick={() => onAction('time-model')}>
            確認 {candidate}
          </Button>
        )}
        {canManage && version?.status === 'draft' && !variableTimeModelUnconfirmed && (
          <Button size="sm" variant="primary" onClick={() => onAction('submit')}>送審</Button>
        )}
        {canApprove && version?.status === 'submitted' && (!research || researchApprovable) && (
          <>
            <Button size="sm" variant="outline-danger" onClick={() => onAction('reject')}>退回</Button>
            <Button size="sm" variant="success" onClick={() => onAction(research ? 'approve-research' : 'approve')}>{research ? '核准研究結果' : '核准生效'}</Button>
          </>
        )}
        {!research && canApprove && version?.status === 'active' && (
          <Button size="sm" variant="outline-danger" onClick={() => onAction('retire')}>停用／重建</Button>
        )}
      </div>
      {variableTimeModelUnconfirmed && (
        <div className="small text-warning mt-2" role="status">
          請先由具核准權限者確認時間模型，再送交審查。
        </div>
      )}
    </div>
  );
};

export default SpcStudyWorkflowBar;
