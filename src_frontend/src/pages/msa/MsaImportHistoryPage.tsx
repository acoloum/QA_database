import { useState } from 'react';

import EquipmentImportReview from '../../components/msa/EquipmentImportReview';
import type { IssueMap, ResolutionMap } from '../../components/msa/EquipmentImportReview';
import { useAuth } from '../../context/useAuth';
import {
  useConfirmMsaEquipmentImport,
  useMsaImportBatch,
  useMsaImportHistory,
  usePreviewMsaEquipmentImport,
} from '../../hooks/useMsaImports';
import type {
  EquipmentImportBatch,
  EquipmentImportBatchSummary,
  EquipmentImportResolution,
} from '../../types/msa';
import '../equipment/measurementEquipment.css';

export default function MsaImportHistoryPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('msa.manage');
  const canViewCalibration = hasPermission('calibration.view');
  const [page, setPage] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [currentBatch, setCurrentBatch] = useState<EquipmentImportBatch | null>(null);
  const [historyBatchId, setHistoryBatchId] = useState<number | null>(null);
  const [rowPage, setRowPage] = useState(1);
  const [resolutions, setResolutions] = useState<ResolutionMap>({});
  const [resolutionIssues, setResolutionIssues] = useState<IssueMap>({});
  const history = useMsaImportHistory({ page, page_size: 20 });
  const historyBatch = useMsaImportBatch(historyBatchId, {
    row_page: rowPage,
    row_page_size: 100,
  });
  const preview = usePreviewMsaEquipmentImport();
  const confirm = useConfirmMsaEquipmentImport();
  const shownBatch = currentBatch ?? historyBatch.data ?? null;

  const handleResolutionChange = (
    rowId: number,
    issueCodes: string[],
    patch: Partial<EquipmentImportResolution>,
  ) => {
    setResolutionIssues((current) => ({ ...current, [rowId]: issueCodes }));
    setResolutions((current) => ({
      ...current,
      [rowId]: { ...current[rowId], ...patch },
    }));
  };

  const confirmBatch = async (
    resolutions: Record<number, EquipmentImportResolution>,
  ) => {
    if (!shownBatch) return;
    const confirmed = await confirm.mutateAsync({
      batchId: shownBatch.id,
      resolutions,
    });
    setRowPage(1);
    setCurrentBatch(confirmed);
  };

  return (
    <main className="msa-page" aria-labelledby="import-title">
      <header className="msa-page__header">
        <div>
          <p className="msa-eyebrow">MSA / 受控設備匯入</p>
          <h1 id="import-title">設備匯入與稽核紀錄</h1>
          <p>先保存預覽與逐列差異；所有 blocking issue 解除後才建立正式設備。</p>
        </div>
        <a
          className="msa-button msa-button--outline"
          href={canViewCalibration ? '/measurement-equipment' : '/msa'}
        >
          {canViewCalibration ? '返回設備清單' : '返回 MSA 工作台'}
        </a>
      </header>

      {canManage && (
        <section className="msa-upload-strip" aria-labelledby="upload-title">
          <div>
            <h2 id="upload-title">上傳與解析</h2>
            <p>接受 CSV，預覽只建立批次與逐列證據，不建立正式設備。</p>
          </div>
          <label>
            設備清單檔案
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button
            type="button"
            className="msa-button msa-button--primary"
            disabled={!file || preview.isPending}
            onClick={() => {
              if (!file) return;
              void preview.mutateAsync({ file }).then((batch: EquipmentImportBatch) => {
                setHistoryBatchId(null);
                setRowPage(1);
                setCurrentBatch(batch);
              });
            }}
          >
            預覽匯入
          </button>
        </section>
      )}

      {(preview.error != null || confirm.error != null) && (
        <div className="msa-state msa-state--error" role="alert">
          {preview.error instanceof Error
            ? preview.error.message
            : confirm.error instanceof Error
              ? confirm.error.message
              : '匯入操作未完成。'}
        </div>
      )}

      {shownBatch && (
        <EquipmentImportReview
          batch={shownBatch}
          resolutions={resolutions}
          resolutionIssues={resolutionIssues}
          onResolutionChange={handleResolutionChange}
          onConfirm={canManage && shownBatch.status === 'previewed' ? confirmBatch : undefined}
          isConfirming={confirm.isPending}
          onRowPageChange={(nextPage) => {
            setRowPage(nextPage);
            if (currentBatch) {
              setHistoryBatchId(currentBatch.id);
              setCurrentBatch(null);
            }
          }}
        />
      )}

      <section className="msa-history" aria-labelledby="history-title">
        <header>
          <div>
            <p className="msa-eyebrow">不可變來源指紋與確認計數</p>
            <h2 id="history-title">匯入稽核歷程</h2>
          </div>
          <span>共 {history.data?.total ?? 0} 批</span>
        </header>
        {history.isLoading && <p role="status">正在讀取匯入歷程…</p>}
        {history.isError && <p role="alert">無法載入匯入歷程。</p>}
        {!history.isLoading && !history.isError && (history.data?.items.length ?? 0) === 0 && (
          <p className="msa-state">尚無設備匯入批次。</p>
        )}
        {(history.data?.items.length ?? 0) > 0 && (
          <table>
            <caption>設備匯入批次稽核歷程</caption>
            <thead>
              <tr>
                <th>批次</th>
                <th>檔名</th>
                <th>狀態</th>
                <th>列數</th>
                <th>來源指紋</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {history.data?.items.map((batch: EquipmentImportBatchSummary) => (
                <tr key={batch.id}>
                  <td className="msa-mono">#{batch.id}</td>
                  <td>{batch.original_filename}</td>
                  <td>{batch.status === 'confirmed' ? '已確認' : '已預覽'}</td>
                  <td className="msa-mono">{batch.total_rows}</td>
                  <td><code>{batch.file_sha256.slice(0, 12)}</code></td>
                  <td>
                    <button
                      type="button"
                      className="msa-button msa-button--quiet"
                      onClick={() => {
                        setCurrentBatch(null);
                        setHistoryBatchId(batch.id);
                        setRowPage(1);
                      }}
                    >
                      檢視逐列證據
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {(history.data?.total ?? 0) > 20 && (
          <nav className="msa-pagination" aria-label="匯入歷程分頁">
            <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一頁</button>
            <span>第 {page} 頁</span>
            <button
              type="button"
              disabled={(page * 20) >= (history.data?.total ?? 0)}
              onClick={() => setPage((value) => value + 1)}
            >
              下一頁
            </button>
          </nav>
        )}
      </section>
    </main>
  );
}
