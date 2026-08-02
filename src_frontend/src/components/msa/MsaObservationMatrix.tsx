import { useState } from 'react';

import type { MsaMatrixCell } from './msaObservationMatrixCells';

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


