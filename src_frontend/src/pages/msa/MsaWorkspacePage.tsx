import { Link } from 'react-router-dom';

import './msaEquipment.css';

export default function MsaWorkspacePage() {
  return (
    <main className="msa-page" aria-labelledby="msa-title">
      <header className="msa-page__header">
        <div>
          <p className="msa-eyebrow">量測系統分析 / 受控證據入口</p>
          <h1 id="msa-title">MSA 工作台</h1>
          <p>先治理設備與匯入差異，再由可追溯證據建立正式研究。</p>
        </div>
      </header>
      <nav className="msa-workspace-lanes" aria-label="MSA 工作區">
        <Link to="/msa/equipment">
          <span className="msa-mono">EQUIPMENT</span>
          <strong>設備清單</strong>
          <small>檢查校驗失敗、逾期、待確認與維修設備。</small>
        </Link>
        <Link to="/msa/imports">
          <span className="msa-mono">IMPORT EVIDENCE</span>
          <strong>設備匯入紀錄</strong>
          <small>預覽差異、逐列處置並追查批次來源指紋。</small>
        </Link>
        <Link to="/msa/criteria">
          <span className="msa-mono">CRITERIA</span>
          <strong>判定準則</strong>
          <small>檢視版本化門檻，並由具核准權限者確認新版本。</small>
        </Link>
      </nav>
    </main>
  );
}
