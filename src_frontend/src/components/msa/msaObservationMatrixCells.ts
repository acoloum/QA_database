import type { MsaBlindTask, MsaObservation } from '../../types/msa';

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
