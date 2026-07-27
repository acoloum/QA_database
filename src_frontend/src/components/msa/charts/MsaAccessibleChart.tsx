import { useState } from 'react';

import { downloadResponseBlob } from '../../../utils/downloadFile';
import { toCsv, type AccessibleMsaChartModel } from './msaChartModels';

interface MsaAccessibleChartProps {
  model: AccessibleMsaChartModel;
  /** 圖表本體；未提供時只呈現摘要與資料表 */
  children?: React.ReactNode;
}

/**
 * 每張 MSA 圖表都必須同時提供文字摘要與資料表：
 * 看不到顏色、用螢幕閱讀器，或把報告印成黑白時，結論都要讀得出來。
 */
export default function MsaAccessibleChart({
  model, children,
}: MsaAccessibleChartProps) {
  const [showTable, setShowTable] = useState(false);

  return (
    <figure className="msa-chart" aria-labelledby={`chart-${model.title}`}>
      <figcaption>
        <h3 id={`chart-${model.title}`}>{model.title}</h3>
        {/* 摘要永遠顯示，不是折疊起來的補充說明 */}
        <p className="msa-chart__summary">{model.summary}</p>
      </figcaption>

      {children && <div className="msa-chart__canvas">{children}</div>}

      <div className="msa-chart__actions">
        <button
          type="button"
          aria-expanded={showTable}
          onClick={() => setShowTable((current) => !current)}
        >
          {showTable ? '隱藏資料表' : '顯示資料表'}
        </button>
        <button
          type="button"
          onClick={() => downloadResponseBlob(
            `﻿${toCsv(model)}`,
            `${model.title}.csv`,
            'text/csv;charset=utf-8',
          )}
        >
          下載 CSV
        </button>
      </div>

      {showTable && (
        <table className="msa-review-table">
          <caption>{model.title}資料表</caption>
          <thead>
            <tr>
              {model.table.columns.map((column) => (
                <th key={column.key} scope="col">{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.table.rows.map((row, index) => (
              <tr key={index}>
                {model.table.columns.map((column) => (
                  <td key={column.key}>
                    {row[column.key] ?? '不可用'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </figure>
  );
}
