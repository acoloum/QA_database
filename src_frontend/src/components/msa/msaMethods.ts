import type { MsaStudyType } from '../../types/msa';

export interface MsaMethodOption {
  studyType: MsaStudyType;
  methodCode: string;
  label: string;
  /** 適用情境 */
  scenario: string;
  /** 最低資料需求 */
  minimumDesign: string;
  /** 這個方法能回答什麼 */
  answers: string[];
  /** 這個方法「不能」回答什麼——選錯方法的代價都在這裡 */
  cannotAnswer: string[];
  /** 需要的設備或參考標準 */
  requires: string;
  /** 需要可追溯參考值才能計算 */
  needsReference?: boolean;
  /** 需要確認物理假設 */
  needsAssumptions?: boolean;
  /** 需要事先定義計數類別 */
  needsCategories?: boolean;
}

export const MSA_METHODS: MsaMethodOption[] = [
  {
    studyType: 'grr_range',
    methodCode: 'MSA4_GRR_RANGE_1_0',
    label: '極差法',
    scenario: '需要快速判斷量測系統是否明顯不可用時的初步篩選',
    minimumDesign: '至少 5 零件 × 2 評價人 × 2 試驗',
    answers: ['量測系統整體變差大約多大'],
    cannotAnswer: [
      '快速篩選用，不分解完整 EV／AV／PV',
      '無法判斷問題出在重複性還是評價人差異',
      '不可作為最終允收依據',
    ],
    requires: '主量具',
  },
  {
    studyType: 'grr_xbar_r',
    methodCode: 'MSA4_GRR_XBAR_R_1_0',
    label: '平均值－極差法',
    scenario: '標準 GRR 研究，需要拆解重複性與再現性',
    minimumDesign: '建議 10 零件 × 3 評價人 × 2–3 試驗',
    answers: [
      '重複性（EV）與再現性（AV）各佔多少',
      '零件變差（PV）與 ndc',
    ],
    cannotAnswer: [
      '無法檢定零件與評價人的交互作用是否顯著',
      '不適用於非平衡資料',
    ],
    requires: '主量具',
  },
  {
    studyType: 'grr_anova',
    methodCode: 'MSA4_GRR_ANOVA_1_0',
    label: '交叉型 ANOVA',
    scenario: '需要檢定零件與評價人交互作用的完整 GRR 研究',
    minimumDesign: '建議 10 零件 × 3 評價人 × 3 試驗',
    answers: [
      '重複性、再現性與交互作用的變異數分量',
      '交互作用是否達顯著水準',
      'ndc 與各百分比口徑',
    ],
    cannotAnswer: ['不適用於非平衡或有缺格的資料'],
    requires: '主量具',
  },
  {
    studyType: 'bias',
    methodCode: 'MSA4_BIAS_1_0',
    label: '偏倚',
    scenario: '確認量測值是否系統性偏離已知真值',
    minimumDesign: '1 個參考件 × 至少 10 次量測',
    answers: ['平均量測值與參考值的差距是否顯著'],
    cannotAnswer: [
      '無法得知偏倚是否隨量程改變（那是線性研究）',
      '不反映評價人之間的差異',
    ],
    requires: '參考標準或具可追溯參考值的零件',
    needsReference: true,
  },
  {
    studyType: 'linearity',
    methodCode: 'MSA4_LINEARITY_1_0',
    label: '線性',
    scenario: '確認偏倚是否隨量測範圍改變',
    minimumDesign: '至少 5 個涵蓋量程的參考量程 × 每個至少 2 次',
    answers: ['偏倚與量程之間是否存在系統性關係'],
    cannotAnswer: [
      '不回答量測系統的重複性與再現性大小',
      '判定不採用 R² 單獨判斷',
    ],
    requires: '涵蓋量程的多個參考標準',
    needsReference: true,
  },
  {
    studyType: 'stability',
    methodCode: 'MSA4_STABILITY_1_0',
    label: '穩定性',
    scenario: '確認量測系統隨時間是否漂移',
    minimumDesign: '同一基準件至少 20 期量測',
    answers: ['基準期間是否出現判異訊號'],
    cannotAnswer: [
      '不輸出任何單一穩定性指數，只列出實際判異',
      '不回答量測系統目前的變差大小',
    ],
    requires: '長期可用的穩定基準件',
    needsReference: true,
  },
  {
    studyType: 'attribute',
    methodCode: 'MSA4_ATTRIBUTE_1_0',
    label: '計數型',
    scenario: '合格／不合格或分類判定的量測系統',
    minimumDesign: '建議 20 樣本 × 2–3 評價人 × 2 次判定',
    answers: [
      '評價人內與評價人間的一致性',
      '相對參考標準的 Kappa、有效性與誤收誤拒率',
    ],
    cannotAnswer: [
      '沒有可信參考標準時只能報告一致性，不能推論正確性',
      '不提供連續型的變差分解',
    ],
    requires: '事先定義的類別集合與可信參考真值',
    needsCategories: true,
  },
  {
    studyType: 'nonreplicable',
    methodCode: 'MSA4_NONREPEATABLE_1_0',
    label: '不可重複／破壞性',
    scenario: '量測會破壞樣本、無法對同一件重複量測',
    minimumDesign: '依設計型態而異，配對型至少 10 組',
    answers: ['在物理假設成立下的重複性估計'],
    cannotAnswer: [
      '無法分離再現性與真實零件變差',
      '物理假設未確認時完全不產生結論',
    ],
    requires: '成立的樣本同質性與配對假設',
    needsAssumptions: true,
  },
];

export const findMethod = (studyType: MsaStudyType | null) =>
  MSA_METHODS.find((method) => method.studyType === studyType) ?? null;
