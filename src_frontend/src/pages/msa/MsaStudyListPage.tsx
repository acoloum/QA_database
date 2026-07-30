import { useMemo, useState } from 'react';
import { Link } from 'react-router';

import { MSA_METHODS } from '../../components/msa/MsaMethodSelector';
import { useAuth } from '../../context/useAuth';
import { useMsaStudies } from '../../hooks/useMsaStudies';
import { isOverdue, sortStudies } from './msaStudySorting';
import type { MsaStudyStatus, MsaStudyType } from '../../types/msa';
import './msa.css';

const STATUS_LABELS: Record<MsaStudyStatus, string> = {
  draft: '草稿',
  ready: '已凍結設計',
  collecting: '資料收集中',
  ready_for_analysis: '可進行分析',
  analyzed: '已分析',
  submitted: '待核准',
  approved: '已核准',
  rejected: '已退回',
  voided: '已作廢',
  superseded: '已被取代',
};

const METHOD_LABELS: Record<string, string> = Object.fromEntries(
  MSA_METHODS.map((method) => [method.studyType, method.label]),
);

export default function MsaStudyListPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('msa.manage');
  const [status, setStatus] = useState<MsaStudyStatus | ''>('');
  const [studyType, setStudyType] = useState<MsaStudyType | ''>('');
  const [keyword, setKeyword] = useState('');

  const query = useMsaStudies({
    page: 1,
    page_size: 100,
    sort: 'updated_at',
    order: 'desc',
    ...(status ? { status } : {}),
  });

  const items = useMemo(() => {
    const rows = query.data?.items ?? [];
    const filtered = rows.filter((study) => {
      if (studyType && study.study_type !== studyType) return false;
      if (!keyword.trim()) return true;
      const needle = keyword.trim().toLowerCase();
      return (
        study.study_no.toLowerCase().includes(needle)
        || study.characteristic.toLowerCase().includes(needle)
      );
    });
    return sortStudies(filtered);
  }, [query.data, studyType, keyword]);

  return (
    <main className="msa-shell" aria-labelledby="msa-studies-title">
      <header className="msa-shell__header">
        <div>
          <p className="msa-eyebrow">量測系統分析 / 研究</p>
          <h1 id="msa-studies-title">研究清單</h1>
          <p>待核准與逾期的研究排在最前面，其餘依流程階段與更新時間排列。</p>
        </div>
        {canManage && <Link to="/msa/studies/new">建立研究</Link>}
      </header>

      <form
        className="msa-filters"
        aria-label="研究篩選"
        onSubmit={(event) => event.preventDefault()}
      >
        <label>
          搜尋
          <input
            type="search"
            placeholder="研究編號或品質特性"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </label>
        <label>
          狀態
          <select
            value={status}
            onChange={(event) => setStatus(
              event.target.value as MsaStudyStatus | '',
            )}
          >
            <option value="">全部</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label>
          方法
          <select
            value={studyType}
            onChange={(event) => setStudyType(
              event.target.value as MsaStudyType | '',
            )}
          >
            <option value="">全部</option>
            {MSA_METHODS.map((method) => (
              <option key={method.studyType} value={method.studyType}>
                {method.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => { setStatus(''); setStudyType(''); setKeyword(''); }}
        >
          清除篩選
        </button>
      </form>

      {query.isLoading && (
        <div className="msa-state" role="status">正在讀取研究清單</div>
      )}
      {query.isError && (
        <div className="msa-state msa-state--error" role="alert">
          <p>無法載入研究清單</p>
          <button type="button" onClick={() => void query.refetch()}>重試</button>
        </div>
      )}
      {!query.isLoading && !query.isError && items.length === 0 && (
        <div className="msa-state">
          <strong>沒有符合條件的 MSA 研究</strong>
          <p>調整篩選條件，或由具權限的人員建立新研究。</p>
        </div>
      )}

      {items.length > 0 && (
        <div className="msa-panel">
          <table className="msa-review-table" aria-label="MSA 研究">
            <caption>MSA 研究清單</caption>
            <thead>
              <tr>
                <th scope="col">研究編號</th>
                <th scope="col">方法</th>
                <th scope="col">品質特性</th>
                <th scope="col">狀態</th>
                <th scope="col">下次到期</th>
                <th scope="col">更新時間</th>
              </tr>
            </thead>
            <tbody>
              {items.map((study) => (
                <tr key={study.id} data-overdue={isOverdue(study)}>
                  <td className="msa-num">
                    <Link to={`/msa/studies/${study.id}`}>{study.study_no}</Link>
                  </td>
                  <td>
                    {METHOD_LABELS[study.study_type] ?? study.study_type}
                  </td>
                  <td>{study.characteristic}</td>
                  <td>{STATUS_LABELS[study.status]}</td>
                  <td className="msa-num">
                    {study.next_due_date ?? '—'}
                    {isOverdue(study) && <span>（已逾期）</span>}
                  </td>
                  <td className="msa-num">{study.updated_at.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
