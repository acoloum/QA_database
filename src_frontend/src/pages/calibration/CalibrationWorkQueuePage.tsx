import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useCalibrations } from '../../hooks/useCalibrations';
import type { CalibrationListParams, CalibrationRecord } from '../../types/calibration';
import './calibration.css';

export const WORK_QUEUE_ORDER = [
  'submitted', 'rejected', 'fail', 'limited_use', 'ready_for_submission',
  'in_progress', 'draft',
] as const;

const resultLabel = (result: CalibrationRecord['result']) => ({
  pending: '待判定', pass: '合格', fail: '不合格', limited_use: '限制使用',
}[result]);

const statusLabel = (status: CalibrationRecord['status']) => ({
  draft: '草稿', in_progress: '進行中', ready_for_submission: '待送審',
  submitted: '待核准', rejected: '已退回', approved: '已核准',
  superseded: '已取代', voided: '已作廢',
}[status]);

export default function CalibrationWorkQueuePage() {
  const [params, setParams] = useState<CalibrationListParams>({
    page: 1, page_size: 25, sort: 'risk', order: 'asc',
  });
  const [searchText, setSearchText] = useState('');
  const query = useCalibrations({
    ...params,
    search: searchText.trim() || undefined,
    sort: 'risk',
    order: 'asc',
  });

  return (
    <main className="cal-page" aria-labelledby="cal-work-queue-title">
      <header className="cal-page-header">
        <div>
          <p className="cal-kicker">校正證據卷宗 / 待辦托盤</p>
          <h1 id="cal-work-queue-title">校正工作佇列</h1>
          <p>依後端風險順序呈現待處理紀錄；跨頁優先級由伺服器判定。</p>
        </div>
      </header>
      <form className="cal-filter-bar" onSubmit={(event) => event.preventDefault()}>
        <label>
          搜尋校正紀錄
          <input
            type="search"
            value={searchText}
            placeholder="設備編號、名稱"
            onChange={(event) => {
              setSearchText(event.target.value);
              setParams((current) => ({ ...current, page: 1 }));
            }}
          />
        </label>
        <label>
          工作狀態
          <select
            value={params.status ?? ''}
            onChange={(event) => setParams((current) => ({
              ...current,
              page: 1,
              status: (event.target.value || undefined) as CalibrationListParams['status'],
            }))}
          >
            <option value="">全部狀態</option>
            <option value="submitted">待核准</option>
            <option value="rejected">已退回</option>
            <option value="ready_for_submission">待送審</option>
            <option value="in_progress">進行中</option>
            <option value="draft">草稿</option>
          </select>
        </label>
      </form>
      {query.isLoading && <p className="cal-state" role="status">正在讀取校正工作佇列…</p>}
      {query.isError && (
        <section className="cal-state cal-state--error" role="alert">
          <p>校正工作佇列載入失敗。</p>
          <button type="button" onClick={() => void query.refetch()}>重新載入</button>
        </section>
      )}
      {!query.isLoading && !query.isError && (
        <>
          <ol className="cal-work-queue" aria-label="校正風險工作佇列">
            {(query.data?.items ?? []).map((record) => (
              <li key={record.id} data-status={record.status}>
                <Link to={`/calibrations/${record.id}`} aria-label={`開啟 ${record.equipment_no ?? `校正紀錄 ${record.id}`} 詳情`}>
                  <span className="cal-work-queue__spine" aria-hidden="true" />
                  <div>
                    <code>{record.equipment_no || `CAL-${record.id}`}</code>
                    <h2>{record.equipment_name || '未命名量測設備'}</h2>
                    <p>{record.procedure_code || '程序快照未提供'} · 校正日 {record.calibration_date}</p>
                  </div>
                  <dl>
                    <div><dt>工作狀態</dt><dd>{statusLabel(record.status)}</dd></div>
                    <div><dt>判定</dt><dd>{resultLabel(record.result)}</dd></div>
                    <div><dt>資料層級</dt><dd>{record.data_level === 'detailed' ? '逐點證據' : '舊版摘要'}</dd></div>
                  </dl>
                </Link>
              </li>
            ))}
          </ol>
          {(query.data?.items.length ?? 0) === 0 && <p className="cal-state">目前沒有符合條件的校正紀錄。</p>}
          <nav className="cal-pagination" aria-label="校正工作佇列分頁">
            <button type="button" disabled={params.page <= 1} onClick={() => setParams((current) => ({ ...current, page: current.page - 1 }))}>上一頁</button>
            <span>第 {params.page} 頁 · 共 {query.data?.total ?? 0} 筆</span>
            <button type="button" disabled={params.page * params.page_size >= (query.data?.total ?? 0)} onClick={() => setParams((current) => ({ ...current, page: current.page + 1 }))}>下一頁</button>
          </nav>
        </>
      )}
    </main>
  );
}
