import { useState } from 'react';

import type { MsaBlindTask } from '../../types/msa';

import type { MsaObservation } from '../../types/msa';

export interface MsaMatrixCell {
  /** 目前有效觀測的識別碼；尚未輸入時為 null */
  observationId: number | null;
  requestedOrder: number;
  partBlindCode: string;
  appraiserBlindCode: string;
  trialNo: number;
  value: string | null;
  source: string | null;
  enteredBy: string | null;
  enteredAt: string | null;
  /** 修正鏈：由最早到最新，最後一筆才是目前有效值 */
  history: Array<{
    value: string; enteredBy: string | null; enteredAt: string | null;
    reason: string | null;
  }>;
}

interface MsaObservationMatrixProps {
  cells: MsaMatrixCell[];
  isSaving?: boolean;
  onCorrect: (input: {
    observationId: number; requestedOrder: number;
    value: string; reason: string;
  }) => void;
}

/**
 * 管理矩陣只給具 msa.manage 的人使用；呼叫端負責權限判斷，
 * 這裡專注在「目前值 + 修正歷程」的呈現。
 */
export default function MsaObservationMatrix({
  cells, isSaving = false, onCorrect,
}: MsaObservationMatrixProps) {
  const [editing, setEditing] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const startEdit = (cell: MsaMatrixCell) => {
    setEditing(cell.requestedOrder);
    setValue(cell.value ?? '');
    setReason('');
    setError(null);
  };

  const submit = () => {
    if (!reason.trim()) {
      setError('請填寫修正理由');
      return;
    }
    if (!value.trim()) {
      setError('請填寫新讀值');
      return;
    }
    const target = cells.find((cell) => cell.requestedOrder === editing);
    if (!target?.observationId) {
      setError('找不到要修正的觀測紀錄，請重新載入');
      return;
    }
    setError(null);
    onCorrect({
      observationId: target.observationId,
      requestedOrder: target.requestedOrder,
      value: value.trim(),
      reason: reason.trim(),
    });
    setEditing(null);
  };

  return (
    <div className="msa-panel">
      <h2>觀測矩陣</h2>
      <p>修正一律以新增後繼紀錄表達，原始讀值永遠保留在歷程中。</p>
      <table className="msa-review-table" aria-label="MSA 觀測矩陣">
        <caption>MSA 觀測矩陣與修正歷程</caption>
        <thead>
          <tr>
            <th scope="col">順序</th>
            <th scope="col">零件</th>
            <th scope="col">評價人</th>
            <th scope="col">試驗</th>
            <th scope="col">目前值</th>
            <th scope="col">來源</th>
            <th scope="col">輸入者</th>
            <th scope="col">操作</th>
          </tr>
        </thead>
        <tbody>
          {cells.map((cell) => (
            <tr key={cell.requestedOrder}>
              <td className="msa-num">{cell.requestedOrder}</td>
              <td>{cell.partBlindCode}</td>
              <td>{cell.appraiserBlindCode}</td>
              <td className="msa-num">{cell.trialNo}</td>
              <td className="msa-num">
                {cell.value ?? '未輸入'}
                {cell.history.length > 1 && (
                  <button
                    type="button"
                    aria-label={
                      `查看 ${cell.partBlindCode} 第 ${cell.trialNo} 次修正歷程`
                    }
                    onClick={() => setExpanded(
                      expanded === cell.requestedOrder
                        ? null : cell.requestedOrder,
                    )}
                  >
                    ⟲ 已修正
                  </button>
                )}
              </td>
              <td>{cell.source ?? '—'}</td>
              <td>
                {cell.enteredBy ?? '—'}
                {cell.enteredAt && (
                  <small className="msa-num">{cell.enteredAt.slice(0, 16)}</small>
                )}
              </td>
              <td>
                {cell.value != null && (
                  <button
                    type="button"
                    onClick={() => startEdit(cell)}
                  >
                    {`修正 ${cell.partBlindCode} 第 ${cell.trialNo} 次`}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {expanded != null && (
        <section aria-label="修正歷程">
          <h3>修正歷程</h3>
          <ol className="msa-queue">
            {(cells.find((cell) => cell.requestedOrder === expanded)?.history
              ?? []).map((entry, index) => (
                <li key={`${entry.value}-${index}`} className="msa-queue__item">
                  <span className="msa-num">{entry.value}</span>
                  <span className="msa-queue__body">
                    <span>{entry.enteredBy ?? '未知輸入者'}</span>
                    <span className="msa-num">{entry.enteredAt ?? ''}</span>
                    <span>{entry.reason ?? '原始輸入'}</span>
                  </span>
                </li>
              ))}
          </ol>
        </section>
      )}

      {editing != null && (
        <form
          className="msa-panel"
          aria-label="修正觀測"
          onSubmit={(event) => { event.preventDefault(); submit(); }}
        >
          <h3>修正讀值</h3>
          <label>
            新讀值
            <input value={value} onChange={(e) => setValue(e.target.value)} />
          </label>
          <label>
            修正理由
            <textarea
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          {error && <p className="msa-inline-error" role="alert">{error}</p>}
          <button type="submit" disabled={isSaving}>確認修正</button>
          <button type="button" onClick={() => setEditing(null)}>取消</button>
        </form>
      )}
    </div>
  );
}

const readingOf = (observation: MsaObservation) =>
  observation.numeric_value ?? observation.attribute_value ?? '';

/**
 * 由盲測任務與管理觀測視圖組出矩陣。修正鏈以 supersedes_id 串接，
 * 由最早的原始輸入排到目前有效值。
 */
export const buildMatrixCells = (
  tasks: MsaBlindTask[],
  observations: MsaObservation[],
): MsaMatrixCell[] => {
  const byOrder = new Map<number, MsaObservation[]>();
  for (const observation of observations) {
    const bucket = byOrder.get(observation.requested_order) ?? [];
    bucket.push(observation);
    byOrder.set(observation.requested_order, bucket);
  }

  return tasks.map((task) => {
    const rows = [...(byOrder.get(task.requested_order) ?? [])].sort(
      (left, right) => left.actual_entry_order - right.actual_entry_order,
    );
    const current = rows.find((row) => row.is_effective) ?? null;
    return {
      observationId: current?.id ?? null,
      requestedOrder: task.requested_order,
      partBlindCode: task.part_blind_code ?? '',
      appraiserBlindCode: task.appraiser_blind_code ?? '',
      trialNo: task.trial_no,
      value: current ? readingOf(current) : null,
      source: current?.source ?? null,
      enteredBy: current ? String(current.entered_by_id) : null,
      enteredAt: current?.measured_at ?? null,
      history: rows.map((row) => ({
        value: readingOf(row),
        enteredBy: String(row.entered_by_id),
        enteredAt: row.measured_at,
        reason: row.correction_reason,
      })),
    };
  });
};
