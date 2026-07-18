import { Badge, Button } from 'react-bootstrap';
import type { SpcStudyResult } from '../../types';
import type { SpcWorkflowAction } from './SpcBaselineApprovalModal';

interface SpcStudyWorkflowBarProps {
  version: SpcStudyResult | null;
  canView: boolean;
  canManage: boolean;
  canApprove: boolean;
  analyzing?: boolean;
  onAnalyze: () => void;
  onAction: (action: SpcWorkflowAction) => void;
  onShowHistory: () => void;
}

const stages = [
  { status: 'draft', label: '候選' },
  { status: 'submitted', label: '送審' },
  { status: 'active', label: '生效' },
];

const stageIndex = (status: SpcStudyResult['status'] | undefined) => {
  if (status === 'active' || status === 'retired') return 2;
  if (status === 'submitted') return 1;
  return status ? 0 : -1;
};

const SpcStudyWorkflowBar = ({
  version, canView, canManage, canApprove, analyzing = false,
  onAnalyze, onAction, onShowHistory,
}: SpcStudyWorkflowBarProps) => {
  const current = stageIndex(version?.status);
  const candidate = version?.time_model.candidate;
  const canConfirmTimeModel = version?.status === 'draft'
    && !version.time_model.confirmed
    && (candidate === 'A1' || candidate === 'A2');

  return (
    <div className="spc-workflow">
      <div className="spc-lifecycle" aria-label="SPC 基準生命週期">
        {stages.map((stage, index) => (
          <div key={stage.status} className={`spc-stage ${index <= current ? 'is-complete' : ''} ${index === current ? 'is-current' : ''}`}>
            <span className="spc-stage-dot">{index < current ? '✓' : index + 1}</span>
            <span>{stage.label}</span>
          </div>
        ))}
        {version?.status === 'rejected' && <Badge bg="danger">已退回</Badge>}
        {version?.status === 'retired' && <Badge bg="secondary">已停用</Badge>}
      </div>
      <div className="d-flex gap-2 flex-wrap justify-content-end">
        <Button size="sm" variant="outline-secondary" onClick={onShowHistory} disabled={!version}>版本歷程</Button>
        {canView && (
          <Button size="sm" variant="outline-primary" onClick={onAnalyze} disabled={analyzing}>
            {analyzing ? '建立中…' : version ? '重建候選' : '建立候選'}
          </Button>
        )}
        {canManage && canConfirmTimeModel && (
          <Button size="sm" variant="outline-primary" onClick={() => onAction('time-model')}>
            確認 {candidate}
          </Button>
        )}
        {canManage && version?.status === 'draft' && (
          <Button size="sm" variant="primary" onClick={() => onAction('submit')}>送審</Button>
        )}
        {canApprove && version?.status === 'submitted' && (
          <>
            <Button size="sm" variant="outline-danger" onClick={() => onAction('reject')}>退回</Button>
            <Button size="sm" variant="success" onClick={() => onAction('approve')}>核准生效</Button>
          </>
        )}
        {canApprove && version?.status === 'active' && (
          <Button size="sm" variant="outline-danger" onClick={() => onAction('retire')}>停用／重建</Button>
        )}
      </div>
    </div>
  );
};

export default SpcStudyWorkflowBar;
