import { useState } from 'react';

import type { MsaWorkflowAction } from './MsaWorkflowBar';

interface MsaDecisionModalProps {
  action: MsaWorkflowAction;
  expectedStatus: string;
  /** 條件接受的結果送審時必須附措施與期限 */
  requiresConditionalPlan: boolean;
  isBusy: boolean;
  errorMessage: string | null;
  onCancel: () => void;
  onConfirm: (payload: {
    reason: string; actions?: string[]; due_date?: string;
  }) => void;
}

const TITLES: Record<MsaWorkflowAction, string> = {
  submit: '送審結果版本',
  approve: '核准結果版本',
  reject: '退回結果版本',
  void: '作廢已核准結果',
};

export default function MsaDecisionModal({
  action, expectedStatus, requiresConditionalPlan, isBusy, errorMessage,
  onCancel, onConfirm,
}: MsaDecisionModalProps) {
  const [reason, setReason] = useState('');
  const [actionsText, setActionsText] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  const submit = () => {
    if (!reason.trim()) {
      setLocalError('請填寫理由');
      return;
    }
    if (requiresConditionalPlan) {
      const actions = actionsText.split('\n')
        .map((line) => line.trim()).filter(Boolean);
      if (actions.length === 0) {
        setLocalError('條件接受必須列出具體處置措施');
        return;
      }
      if (!dueDate) {
        setLocalError('條件接受必須訂定處置期限');
        return;
      }
      setLocalError(null);
      onConfirm({ reason: reason.trim(), actions, due_date: dueDate });
      return;
    }
    setLocalError(null);
    onConfirm({ reason: reason.trim() });
  };

  return (
    <div className="msa-dialog-backdrop">
      <div
        className="msa-create-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="msa-decision-title"
      >
        <h2 id="msa-decision-title">{TITLES[action]}</h2>
        <p>
          送出時會一併帶上畫面看到的狀態
          <code className="msa-num">{expectedStatus}</code>
          ，若期間被他人變更會被拒絕。
        </p>

        <form onSubmit={(event) => { event.preventDefault(); submit(); }}>
          <label>
            理由
            <textarea
              rows={3}
              autoFocus
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>

          {requiresConditionalPlan && (
            <>
              <label>
                處置措施（每行一項）
                <textarea
                  rows={3}
                  value={actionsText}
                  onChange={(event) => setActionsText(event.target.value)}
                />
              </label>
              <label>
                處置期限
                <input
                  type="date"
                  value={dueDate}
                  onChange={(event) => setDueDate(event.target.value)}
                />
              </label>
            </>
          )}

          {(localError || errorMessage) && (
            <p className="msa-inline-error" role="alert">
              {localError ?? errorMessage}
            </p>
          )}

          <div className="msa-dialog-actions">
            <button type="button" onClick={onCancel}>取消</button>
            <button type="submit" disabled={isBusy}>
              {isBusy ? '處理中…' : '確認'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
