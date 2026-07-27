import { useMemo, useState } from 'react';

import type {
  CalibrationType,
  EquipmentImportBatch,
  EquipmentImportResolution,
} from '../../types/msa';

interface EquipmentImportReviewProps {
  batch: EquipmentImportBatch;
  onConfirm?: (
    resolutions: Record<number, EquipmentImportResolution>,
  ) => void | Promise<void>;
  isConfirming?: boolean;
  onRowPageChange?: (page: number) => void;
}

const REPAIRABLE_ISSUES = new Set([
  'MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE',
  'MSA_IMPORT_CALIBRATION_TYPE_INVALID',
  'MSA_IMPORT_EXEMPTION_REASON_MISSING',
  'MSA_IMPORT_RESOLUTION_MISSING',
  'MSA_IMPORT_RESOLUTION_INVALID',
  'MSA_IMPORT_MODEL_MISSING',
  'MSA_IMPORT_CUSTODIAN_MISSING',
  'MSA_IMPORT_UNIT_MISSING',
  'MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE',
  'MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX',
]);

const ISSUE_LABELS: Record<string, string> = {
  MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE: '校驗類別必須人工映射',
  MSA_IMPORT_CALIBRATION_TYPE_INVALID: '校驗類別無法辨識',
  MSA_IMPORT_EXEMPTION_REASON_MISSING: '免校設備缺少完整豁免理由',
  MSA_IMPORT_RESOLUTION_MISSING: '解析度缺漏',
  MSA_IMPORT_RESOLUTION_INVALID: '解析度格式無效',
  MSA_IMPORT_MODEL_MISSING: '型號缺漏',
  MSA_IMPORT_CUSTODIAN_MISSING: '保管人缺漏',
  MSA_IMPORT_UNIT_MISSING: '單位缺漏',
  MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE: '序號前綴後缺少序號',
  MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX: '序號前綴需人工確認',
};

const plainValue = (value: unknown) => {
  if (value == null) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
};

const isComplete = (
  issueCodes: string[],
  resolution: EquipmentImportResolution | undefined,
) => {
  if (issueCodes.length === 0) return true;
  if (!resolution?.action) return false;
  if (resolution.action === 'reject') return true;
  if (issueCodes.some((code) => !REPAIRABLE_ISSUES.has(code))) return false;
  if (
    issueCodes.some((code) => (
      code === 'MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE'
      || code === 'MSA_IMPORT_CALIBRATION_TYPE_INVALID'
    ))
    && !resolution.calibration_type
  ) return false;
  if (
    (
      resolution.calibration_type === 'exempt'
      || issueCodes.includes('MSA_IMPORT_EXEMPTION_REASON_MISSING')
    )
    && !resolution.calibration_exemption_reason?.trim()
  ) return false;
  if (
    issueCodes.some((code) => (
      code === 'MSA_IMPORT_RESOLUTION_MISSING'
      || code === 'MSA_IMPORT_RESOLUTION_INVALID'
    ))
    && !String(resolution.resolution ?? '').trim()
  ) return false;
  if (issueCodes.includes('MSA_IMPORT_MODEL_MISSING') && !resolution.model?.trim()) return false;
  if (issueCodes.includes('MSA_IMPORT_CUSTODIAN_MISSING') && !resolution.custodian?.trim()) return false;
  if (issueCodes.includes('MSA_IMPORT_UNIT_MISSING') && !resolution.unit?.trim()) return false;
  if (
    issueCodes.some((code) => (
      code === 'MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE'
      || code === 'MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX'
    ))
    && !resolution.serial_no?.trim()
  ) return false;
  return true;
};

export default function EquipmentImportReview({
  batch,
  onConfirm,
  isConfirming = false,
  onRowPageChange,
}: EquipmentImportReviewProps) {
  const [resolutions, setResolutions] = useState<
    Record<number, EquipmentImportResolution>
  >({});
  const [resolutionIssues, setResolutionIssues] = useState<
    Record<number, string[]>
  >({});
  const unresolvedCount = useMemo(
    () => Math.max(
      0,
      batch.pending_rows - Object.entries(resolutions).filter(
        ([rowId, resolution]) => isComplete(
          resolutionIssues[Number(rowId)] ?? [],
          resolution,
        ),
      ).length,
    ),
    [batch.pending_rows, resolutionIssues, resolutions],
  );

  const update = (
    rowId: number,
    issueCodes: string[],
    patch: Partial<EquipmentImportResolution>,
  ) => {
    setResolutionIssues((current) => ({
      ...current,
      [rowId]: issueCodes,
    }));
    setResolutions((current) => ({
      ...current,
      [rowId]: { ...current[rowId], ...patch },
    }));
  };

  return (
    <section className="msa-import-review" aria-labelledby={`import-review-${batch.id}`}>
      <header>
        <div>
          <p className="msa-eyebrow">批次 #{batch.id} · {batch.parser_version}</p>
          <h2 id={`import-review-${batch.id}`}>{batch.original_filename}</h2>
        </div>
        <code>{batch.file_sha256.slice(0, 12)}</code>
      </header>
      <ol className="msa-stepper" aria-label="設備匯入階段">
        <li className="is-complete"><span aria-hidden="true">✓</span>上傳與解析</li>
        <li className={batch.status === 'previewed' ? 'is-current' : 'is-complete'}>
          <span aria-hidden="true">{batch.status === 'previewed' ? '2' : '✓'}</span>
          差異與問題處置
        </li>
        <li className={batch.status === 'confirmed' ? 'is-complete' : ''}>
          <span aria-hidden="true">{batch.status === 'confirmed' ? '✓' : '3'}</span>
          確認與稽核結果
        </li>
      </ol>

      {batch.status === 'confirmed' ? (
        <div className="msa-import-result" role="status">
          <strong>批次已確認</strong>
          <span>建立 {batch.success_rows} 筆</span>
          <span>待確認 {batch.pending_rows} 筆</span>
          <span>拒絕 {batch.rejected_rows} 筆</span>
        </div>
      ) : (
        <p className="msa-import-pending">待人工確認 {batch.pending_rows} 筆</p>
      )}

      <div className="msa-import-table-wrap">
        <table className="msa-import-table">
          <caption>設備匯入逐列差異與問題處置</caption>
          <thead>
            <tr>
              <th scope="col">來源列</th>
              <th scope="col">設備編號</th>
              <th scope="col">原始值</th>
              <th scope="col">正規化值</th>
              <th scope="col">問題碼與說明</th>
              <th scope="col">處置</th>
            </tr>
          </thead>
          <tbody>
            {batch.rows.map((row) => {
              const resolution = resolutions[row.id] ?? {};
              return (
                <tr
                  key={row.id}
                  className={row.issue_codes.length ? 'has-issue' : 'is-clean'}
                  aria-label={`原始列 ${row.source_row_no}`}
                >
                  <th scope="row" className="msa-mono">原始列 {row.source_row_no}</th>
                  <td className="msa-mono">
                    {String(row.normalized?.equipment_no ?? row.raw['設備編號'] ?? '—')}
                  </td>
                  <td><pre>{plainValue(row.raw)}</pre></td>
                  <td><pre>{plainValue(row.normalized)}</pre></td>
                  <td>
                    {row.issue_codes.length === 0
                      ? <span className="msa-clean-row"><span aria-hidden="true">✓</span> 無問題</span>
                      : (
                        <ul className="msa-issue-list">
                          {row.issue_codes.map((code) => (
                            <li key={code}>
                              <code>{code}</code>
                              <span>{ISSUE_LABELS[code] || row.issue_description || '需要人工確認'}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                  </td>
                  <td>
                    {batch.status === 'previewed' && row.issue_codes.length > 0 ? (
                      <div className="msa-resolution-fields">
                        <label>
                          列 {row.source_row_no} 處置
                          <select
                            value={resolution.action ?? ''}
                            onChange={(event) => update(row.id, row.issue_codes, {
                              action: event.target.value as EquipmentImportResolution['action'],
                            })}
                          >
                            <option value="">請選擇</option>
                            {row.issue_codes.every((code) => REPAIRABLE_ISSUES.has(code)) && (
                              <>
                                <option value="accept">接受匯入</option>
                                <option value="pending_review">建立為待確認</option>
                              </>
                            )}
                            <option value="reject">拒絕此列</option>
                          </select>
                        </label>
                        {row.issue_codes.some((code) => (
                          code === 'MSA_IMPORT_AMBIGUOUS_CALIBRATION_TYPE'
                          || code === 'MSA_IMPORT_CALIBRATION_TYPE_INVALID'
                        )) && resolution.action !== 'reject' && (
                          <label>
                            列 {row.source_row_no} 校驗類別映射
                            <select
                              value={resolution.calibration_type ?? ''}
                              onChange={(event) => update(row.id, row.issue_codes, {
                                calibration_type: event.target.value as CalibrationType,
                              })}
                            >
                              <option value="">請明確映射</option>
                              <option value="internal">內校</option>
                              <option value="external">外校</option>
                              <option value="exempt">免校</option>
                            </select>
                          </label>
                        )}
                        {(
                          resolution.calibration_type === 'exempt'
                          || row.issue_codes.includes('MSA_IMPORT_EXEMPTION_REASON_MISSING')
                        ) && resolution.action !== 'reject' && (
                          <label>
                            列 {row.source_row_no} 免校理由
                            <input
                              value={resolution.calibration_exemption_reason ?? ''}
                              onChange={(event) => update(row.id, row.issue_codes, {
                                calibration_exemption_reason: event.target.value,
                              })}
                            />
                          </label>
                        )}
                        {row.issue_codes.some((code) => (
                          code === 'MSA_IMPORT_RESOLUTION_MISSING'
                          || code === 'MSA_IMPORT_RESOLUTION_INVALID'
                        )) && resolution.action !== 'reject' && (
                          <label>
                            列 {row.source_row_no} 解析度
                            <input
                              inputMode="decimal"
                              value={String(resolution.resolution ?? '')}
                              onChange={(event) => update(
                                row.id,
                                row.issue_codes,
                                { resolution: event.target.value },
                              )}
                            />
                          </label>
                        )}
                        {row.issue_codes.includes('MSA_IMPORT_UNIT_MISSING') && resolution.action !== 'reject' && (
                          <label>
                            列 {row.source_row_no} 單位
                            <input
                              value={resolution.unit ?? ''}
                              onChange={(event) => update(
                                row.id, row.issue_codes, { unit: event.target.value },
                              )}
                            />
                          </label>
                        )}
                        {row.issue_codes.includes('MSA_IMPORT_MODEL_MISSING') && resolution.action !== 'reject' && (
                          <label>
                            列 {row.source_row_no} 型號
                            <input
                              value={resolution.model ?? ''}
                              onChange={(event) => update(
                                row.id, row.issue_codes, { model: event.target.value },
                              )}
                            />
                          </label>
                        )}
                        {row.issue_codes.includes('MSA_IMPORT_CUSTODIAN_MISSING') && resolution.action !== 'reject' && (
                          <label>
                            列 {row.source_row_no} 保管人
                            <input
                              value={resolution.custodian ?? ''}
                              onChange={(event) => update(
                                row.id, row.issue_codes, { custodian: event.target.value },
                              )}
                            />
                          </label>
                        )}
                        {row.issue_codes.some((code) => (
                          code === 'MSA_IMPORT_SERIAL_PREFIX_WITHOUT_VALUE'
                          || code === 'MSA_IMPORT_SERIAL_UNSUPPORTED_PREFIX'
                        )) && resolution.action !== 'reject' && (
                          <label>
                            列 {row.source_row_no} 序號
                            <input
                              value={resolution.serial_no ?? ''}
                              onChange={(event) => update(
                                row.id, row.issue_codes, { serial_no: event.target.value },
                              )}
                            />
                          </label>
                        )}
                      </div>
                    ) : (
                      <span>{row.confirmed_at ? '已留存處置軌跡' : '自動解析'}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {batch.rows_total > batch.row_page_size && (
        <nav className="msa-pagination" aria-label="逐列證據分頁">
          <button
            type="button"
            aria-label="上一頁逐列證據"
            disabled={batch.row_page <= 1}
            onClick={() => onRowPageChange?.(batch.row_page - 1)}
          >
            上一頁
          </button>
          <span>第 {batch.row_page} 頁 · 共 {batch.rows_total} 列</span>
          <button
            type="button"
            aria-label="下一頁逐列證據"
            disabled={(batch.row_page * batch.row_page_size) >= batch.rows_total}
            onClick={() => onRowPageChange?.(batch.row_page + 1)}
          >
            下一頁
          </button>
        </nav>
      )}
      {batch.status === 'previewed' && onConfirm && (
        <footer className="msa-import-review__footer">
          <p aria-live="polite">
            {unresolvedCount > 0
              ? `尚有 ${unresolvedCount} 列 blocking issue 未解決`
              : '所有 blocking issue 已逐列處置'}
          </p>
          <button
            type="button"
            className="msa-button msa-button--primary"
            disabled={unresolvedCount > 0 || isConfirming}
            onClick={() => void onConfirm(resolutions)}
          >
            確認匯入
          </button>
        </footer>
      )}
    </section>
  );
}
