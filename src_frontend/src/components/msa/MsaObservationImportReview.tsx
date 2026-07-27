import type { MsaObservationImportBatch } from '../../types/msa';

interface MsaObservationImportReviewProps {
  fileName: string | null;
  fileSize: number | null;
  batch: MsaObservationImportBatch | null;
  isPreviewing: boolean;
  isConfirming: boolean;
  errorMessage: string | null;
  onFileSelect: (file: File | null) => void;
  onPreview: () => void;
  onConfirm: () => void;
}

const COLUMN_MAPPING = [
  { column: 'A', field: '任務順序' },
  { column: 'B', field: '零件盲碼' },
  { column: 'C', field: '評價人盲碼' },
  { column: 'D', field: '讀值' },
  { column: 'E', field: '量測時間' },
];

/**
 * 前端只顯示檔名與大小，解析與判定一律以後端回應為準；
 * 絕不在前端重新解析 Excel 當作正式依據。
 */
export default function MsaObservationImportReview({
  fileName, fileSize, batch, isPreviewing, isConfirming, errorMessage,
  onFileSelect, onPreview, onConfirm,
}: MsaObservationImportReviewProps) {
  const issues = batch?.issues ?? [];
  const stats = (batch?.stats ?? {}) as Record<string, number>;
  const blocking = issues.length;
  const confirmed = batch?.status === 'confirmed';

  return (
    <section className="msa-panel" aria-labelledby="msa-import-title">
      <h2 id="msa-import-title">Excel 匯入</h2>

      <table className="msa-review-table" aria-label="欄位對應">
        <caption>Excel 欄位對應</caption>
        <thead>
          <tr><th scope="col">欄</th><th scope="col">對應欄位</th></tr>
        </thead>
        <tbody>
          {COLUMN_MAPPING.map((row) => (
            <tr key={row.column}>
              <td className="msa-num">{row.column}</td>
              <td>{row.field}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <label>
        觀測資料檔（.xlsx）
        <input
          type="file"
          accept=".xlsx"
          onChange={(event) => onFileSelect(event.target.files?.[0] ?? null)}
        />
      </label>
      {fileName && (
        <p>
          已選擇 {fileName}
          {fileSize != null && (
            <span className="msa-num">（{Math.ceil(fileSize / 1024)} KB）</span>
          )}
        </p>
      )}

      <button
        type="button"
        onClick={onPreview}
        disabled={!fileName || isPreviewing}
      >
        {isPreviewing ? '解析中…' : '預覽匯入'}
      </button>

      {errorMessage && (
        <p className="msa-inline-error" role="alert">{errorMessage}</p>
      )}

      {batch && (
        <>
          <dl className="msa-review-grid">
            <div>
              <dt>可寫入列數</dt>
              <dd className="msa-num">{stats.clean_rows ?? 0}</dd>
            </div>
            <div>
              <dt>有問題列數</dt>
              <dd className="msa-num">{stats.issue_rows ?? 0}</dd>
            </div>
            <div>
              <dt>批次狀態</dt>
              <dd>{confirmed ? '已確認' : '已預覽'}</dd>
            </div>
            <div>
              <dt>檔案指紋</dt>
              <dd className="msa-num">{batch.file_sha256.slice(0, 12)}</dd>
            </div>
            {confirmed && (
              <div>
                <dt>實際寫入</dt>
                <dd className="msa-num">{stats.written ?? 0}</dd>
              </div>
            )}
          </dl>

          {issues.length > 0 && (
            <table className="msa-review-table" aria-label="匯入問題">
              <caption>匯入問題逐格清單</caption>
              <thead>
                <tr>
                  <th scope="col">工作表</th>
                  <th scope="col">儲存格</th>
                  <th scope="col">問題碼</th>
                  <th scope="col">說明</th>
                </tr>
              </thead>
              <tbody>
                {issues.map((issue) => (
                  <tr key={`${issue.sheet}-${issue.cell}-${issue.code}`}>
                    <td>{issue.sheet}</td>
                    <td className="msa-num">{issue.cell}</td>
                    <td><code>{issue.code}</code></td>
                    <td>{issue.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {!confirmed && (
            <>
              {blocking > 0 && (
                <p className="msa-inline-error">
                  仍有 {blocking} 個儲存格問題；確認後這些列不會被寫入。
                </p>
              )}
              <button
                type="button"
                onClick={onConfirm}
                disabled={isConfirming || (stats.clean_rows ?? 0) === 0}
              >
                {isConfirming ? '寫入中…' : '確認匯入'}
              </button>
            </>
          )}
        </>
      )}
    </section>
  );
}
