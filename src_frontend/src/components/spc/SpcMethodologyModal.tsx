import { Modal, Table } from 'react-bootstrap';

interface SpcMethodologyModalProps { show: boolean; onHide: () => void; }

/** §10.2 參數透明化：讓使用者了解指數計算所用的方法與參數 */
const SpcMethodologyModal = ({ show, onHide }: SpcMethodologyModalProps) => (
  <Modal show={show} onHide={onHide} size="lg">
    <Modal.Header closeButton>
      <Modal.Title>SPC 計算方法說明（AIAG-VDA SPC 2026）</Modal.Title>
    </Modal.Header>
    <Modal.Body>
      <Table size="sm" bordered>
        <tbody>
          <tr><td>指數方法</td><td>G 法（分位數法）；常態分布時等同 (U−L)/6s。指數名稱後綴 .G 表示此方法。</td></tr>
          <tr><td>能力 vs 績效</td><td>穩定性準則全數通過 → 報告 Cp/Cpk（能力）；否則報告 Pp/Ppk（績效）。兩者公式相同，皆用整體標準差。</td></tr>
          <tr><td>穩定性準則</td><td>預設：超出管制界限、連續9點同側、連續6點趨勢（避免同時套用過多準則以控制誤警率）。</td></tr>
          <tr><td>目標值</td><td>依公差管理之「特性重要度」查表（關鍵 1.67 / 主要 1.33 / 次要與其他 1.00）；樣本數 &lt;125 時依 95% 信賴水準上修。</td></tr>
          <tr><td>離群值</td><td>僅由人工標示（必填原因），標示後排除於統計但保留於資料庫供追溯，不會刪除。</td></tr>
          <tr><td>單側公差</td><td>僅計算對應側指數；同心度/真圓度/真直度（共3項）於僅有上限尺寸時，以 0 為自然下界、採單側上限。</td></tr>
          <tr><td>分布模型</td><td>同心度/真圓度/真直度/圓度/平面度/直線度（共6項）等形狀公差特性採摺疊常態；其他特性以 Anderson-Darling 檢定，非常態時擬合對數常態並以分位數法計算。</td></tr>
          <tr><td>PPM</td><td>依擬合分布之尾端機率估算（非常態時不再使用常態假設）。</td></tr>
          <tr><td>管制界限</td><td>預設以前 25 個子組為基準期；可於圖表工具列凍結/解除。</td></tr>
        </tbody>
      </Table>
      <div className="text-muted small">完整參數揭露見 docs/spc_validation.md（§10.2 軟體確效）。</div>
    </Modal.Body>
  </Modal>
);

export default SpcMethodologyModal;
