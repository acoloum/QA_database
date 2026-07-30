import { useMemo, useState } from 'react';
import { useParams } from 'react-router';

import MsaBlindEntry from '../../components/msa/MsaBlindEntry';
import MsaObservationImportReview from '../../components/msa/MsaObservationImportReview';
import MsaObservationMatrix, {
  buildMatrixCells,
  type MsaMatrixCell,
} from '../../components/msa/MsaObservationMatrix';
import { useAuth } from '../../context/useAuth';
import {
  useConfirmMsaObservationImport,
  useCorrectMsaObservation,
  useMsaPlanObservations,
  useMsaPlanTasks,
  useMsaStudy,
  usePreviewMsaObservationImport,
  useRecordMsaObservation,
  useValidateMsaPlan,
} from '../../hooks/useMsaStudies';
import type {
  MsaBlindTask,
  MsaObservationImportBatch,
} from '../../types/msa';
import './msa.css';

type Mode = 'blind' | 'matrix' | 'import';

const errorText = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;

export default function MsaDataCollectionPage() {
  const { studyId } = useParams<{ studyId: string }>();
  const { hasPermission } = useAuth();
  const canManage = hasPermission('msa.manage');

  const study = useMsaStudy(studyId ? Number(studyId) : null);
  const planId = study.data?.current_plan_version_id ?? null;
  const tasks = useMsaPlanTasks(planId);
  // 管理視圖含已作廢紀錄，只有具管理權限時才查詢
  const observations = useMsaPlanObservations(planId, canManage);
  const record = useRecordMsaObservation();
  const correct = useCorrectMsaObservation();
  const validate = useValidateMsaPlan();
  const preview = usePreviewMsaObservationImport();
  const confirm = useConfirmMsaObservationImport();

  const [mode, setMode] = useState<Mode>('blind');
  const [entryError, setEntryError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [batch, setBatch] = useState<MsaObservationImportBatch | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  // 先固定 items 的參照，後續 useMemo 才不會每次 render 都失效
  const items: MsaBlindTask[] = useMemo(
    () => tasks.data?.items ?? [], [tasks.data],
  );
  const pending = useMemo(
    () => items.filter((task) => !task.recorded), [items],
  );
  const completed = items.length - pending.length;
  const currentTask = pending[0] ?? null;

  const cells: MsaMatrixCell[] = useMemo(
    () => buildMatrixCells(items, observations.data?.items ?? []),
    [items, observations.data],
  );

  const submitReading = (value: string) => {
    if (!planId || !currentTask) return;
    setEntryError(null);
    void record.mutateAsync({
      planId,
      task_order: currentTask.requested_order,
      numeric_value: value,
    }).catch((error: unknown) => {
      setEntryError(errorText(error, '讀值未儲存，請確認任務狀態後再試。'));
      void tasks.refetch();
    });
  };

  return (
    <main className="msa-shell" aria-labelledby="msa-collect-title">
      <header className="msa-shell__header">
        <div>
          <p className="msa-eyebrow">量測系統分析 / 盲測收集</p>
          <h1 id="msa-collect-title">量測資料收集</h1>
          <p>
            {study.data
              ? `${study.data.study_no}｜${study.data.characteristic}`
              : '正在讀取研究資訊'}
          </p>
        </div>
      </header>

      <nav className="msa-tabs" aria-label="收集方式">
        <button
          type="button"
          aria-pressed={mode === 'blind'}
          onClick={() => setMode('blind')}
        >
          逐筆盲測
        </button>
        {canManage && (
          <>
            <button
              type="button"
              aria-pressed={mode === 'matrix'}
              onClick={() => setMode('matrix')}
            >
              觀測矩陣
            </button>
            <button
              type="button"
              aria-pressed={mode === 'import'}
              onClick={() => setMode('import')}
            >
              Excel 匯入
            </button>
          </>
        )}
      </nav>

      {tasks.isLoading && (
        <div className="msa-state" role="status">正在讀取盲測任務</div>
      )}
      {tasks.isError && (
        <div className="msa-state msa-state--error" role="alert">
          <p>無法載入盲測任務</p>
          <button type="button" onClick={() => void tasks.refetch()}>重試</button>
        </div>
      )}

      {!tasks.isLoading && !tasks.isError && (
        <>
          <p className="msa-progress msa-num">
            進度 {completed} / {items.length} 件
          </p>

          {mode === 'blind' && (
            currentTask ? (
              <MsaBlindEntry
                task={currentTask}
                position={currentTask.requested_order}
                total={items.length}
                completed={completed}
                unit={study.data?.unit ?? ''}
                categories={[]}
                isSaving={record.isPending}
                errorMessage={entryError}
                onSubmit={submitReading}
              />
            ) : (
              <div className="msa-state">
                <strong>所有盲測任務都已完成</strong>
                <p>可以進行完整性驗證後開始分析。</p>
                <button
                  type="button"
                  disabled={!planId || validate.isPending}
                  onClick={() => planId && void validate.mutateAsync({ planId })}
                >
                  驗證資料完整性
                </button>
              </div>
            )
          )}

          {mode === 'matrix' && canManage && (
            <MsaObservationMatrix
              cells={cells}
              isSaving={correct.isPending}
              onCorrect={({ observationId, value, reason }) => {
                void correct.mutateAsync({
                  observationId, numeric_value: value, reason,
                }).then(() => {
                  void observations.refetch();
                  void tasks.refetch();
                });
              }}
            />
          )}

          {mode === 'import' && canManage && (
            <MsaObservationImportReview
              fileName={file?.name ?? null}
              fileSize={file?.size ?? null}
              batch={batch}
              isPreviewing={preview.isPending}
              isConfirming={confirm.isPending}
              errorMessage={importError}
              onFileSelect={(selected) => {
                setFile(selected);
                setBatch(null);
                setImportError(null);
              }}
              onPreview={() => {
                if (!planId || !file) return;
                setImportError(null);
                void preview.mutateAsync({ planId, file })
                  .then(setBatch)
                  .catch((error: unknown) => setImportError(
                    errorText(error, '匯入檔案未通過解析。'),
                  ));
              }}
              onConfirm={() => {
                if (!planId || !batch) return;
                setImportError(null);
                void confirm.mutateAsync({ planId, batchId: batch.id })
                  .then((result) => {
                    setBatch(result);
                    void tasks.refetch();
                  })
                  .catch((error: unknown) => setImportError(
                    errorText(error, '匯入未完成，請重新預覽。'),
                  ));
              }}
            />
          )}
        </>
      )}
    </main>
  );
}
