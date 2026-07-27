import type { MsaResultVersion } from '../../types/msa';

export type MsaWorkflowAction = 'submit' | 'approve' | 'reject' | 'void';

interface MsaWorkflowBarProps {
  result: MsaResultVersion;
  canManage: boolean;
  canApprove: boolean;
  /** 目前使用者是否參與過本研究；參與者不得核准 */
  isParticipant: boolean;
  isBusy?: boolean;
  onAction: (action: MsaWorkflowAction) => void;
  onDownload: (format: 'xlsx' | 'pdf') => void;
}

const ACTION_LABELS: Record<MsaWorkflowAction, string> = {
  submit: '送審',
  approve: '核准',
  reject: '退回',
  void: '作廢',
};

/** 依結果狀態決定可用動作；不在表內的組合不會出現按鈕。 */
const AVAILABLE_ACTIONS: Record<
  MsaResultVersion['status'], MsaWorkflowAction[]
> = {
  analyzed: ['submit'],
  submitted: ['approve', 'reject'],
  approved: ['void'],
  rejected: [],
  voided: [],
  superseded: [],
};

export default function MsaWorkflowBar({
  result, canManage, canApprove, isParticipant, isBusy = false,
  onAction, onDownload,
}: MsaWorkflowBarProps) {
  const actions = AVAILABLE_ACTIONS[result.status] ?? [];

  const permittedFor = (action: MsaWorkflowAction) =>
    action === 'submit' ? canManage : canApprove;

  return (
    <div className="msa-workflow-bar">
      <div className="msa-workflow-bar__actions">
        {actions.map((action) => {
          const needsIndependence = action !== 'submit';
          const blockedByDuty = needsIndependence && isParticipant;
          const disabled = isBusy || !permittedFor(action) || blockedByDuty;
          return (
            <span key={action} className="msa-workflow-bar__action">
              <button
                type="button"
                disabled={disabled}
                onClick={() => onAction(action)}
              >
                {ACTION_LABELS[action]}
              </button>
              {blockedByDuty && (
                <small className="msa-inline-error">
                  你參與過本研究，依職責分離不得{ACTION_LABELS[action]}
                </small>
              )}
              {!blockedByDuty && !permittedFor(action) && (
                <small>權限不足</small>
              )}
            </span>
          );
        })}
        {actions.length === 0 && (
          <p>目前狀態沒有可執行的工作流動作。</p>
        )}
      </div>

      <div className="msa-workflow-bar__downloads">
        <button type="button" onClick={() => onDownload('pdf')}>
          下載 PDF 報告
        </button>
        <button type="button" onClick={() => onDownload('xlsx')}>
          下載 Excel 報告
        </button>
        {result.status !== 'approved' && (
          <small>尚未核准，報告會帶「未核准」標示</small>
        )}
      </div>
    </div>
  );
}
