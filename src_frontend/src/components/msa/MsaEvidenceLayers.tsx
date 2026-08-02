import { useState } from 'react';

import type { MsaResultVersion } from '../../types/msa';

import { flattenStatistics } from './msaEvidenceLayersUtils';

export interface MsaEvidenceLayer {
  id: string;
  title: string;
  /** 這一層要回答的問題 */
  question: string;
  content: React.ReactNode;
}

interface MsaEvidenceLayersProps {
  layers: MsaEvidenceLayer[];
  defaultOpenId?: string;
}

/**
 * 證據分層：由「結論」往下逐層展開到「原始資料」。
 * 預設只展開第一層，避免一次倒出全部細節；但每層標題都寫明它回答
 * 什麼問題，讀者可以直接跳到需要的深度。
 */
export default function MsaEvidenceLayers({
  layers, defaultOpenId,
}: MsaEvidenceLayersProps) {
  const [openId, setOpenId] = useState<string | null>(
    defaultOpenId ?? layers[0]?.id ?? null,
  );

  return (
    <div className="msa-evidence-layers">
      {layers.map((layer, index) => {
        const open = openId === layer.id;
        return (
          <section key={layer.id} className="msa-evidence-layer">
            <h2>
              <button
                type="button"
                aria-expanded={open}
                aria-controls={`layer-${layer.id}`}
                onClick={() => setOpenId(open ? null : layer.id)}
              >
                <span className="msa-num">第 {index + 1} 層</span>
                {layer.title}
                <small>{layer.question}</small>
              </button>
            </h2>
            <div id={`layer-${layer.id}`} hidden={!open}>
              {layer.content}
            </div>
          </section>
        );
      })}
    </div>
  );
}

interface MsaMethodEvidenceProps {
  result: MsaResultVersion;
}

/** 方法證據層：適用性判定與完整統計輸出。 */
export function MsaMethodEvidence({ result }: MsaMethodEvidenceProps) {
  const rows = flattenStatistics(result.statistics);

  return (
    <div>
      <h3>適用性判定</h3>
      <table className="msa-review-table">
        <caption>方法適用性</caption>
        <thead>
          <tr><th scope="col">項目</th><th scope="col">值</th></tr>
        </thead>
        <tbody>
          {flattenStatistics(result.applicability_result).map((row) => (
            <tr key={row.path}>
              <td>{row.path}</td>
              <td>{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>統計輸出</h3>
      <p>
        方法 {result.method_code}（版本 {result.method_version}）；
        程式版本 {result.code_version}。
      </p>
      <table className="msa-review-table">
        <caption>統計輸出</caption>
        <thead>
          <tr><th scope="col">統計項目</th><th scope="col">值</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.path}>
              <td>{row.path}</td>
              <td className="msa-num">{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
