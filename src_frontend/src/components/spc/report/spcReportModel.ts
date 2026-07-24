// 依 AIAG-VDA SPC 2026 §11.2 Figure 11-1 產生一頁式製程能力報告的資料模型。
// 出貨/機械性質內嵌區塊提供 SpcChartData（即時預覽）；進階頁提供 SpcStudyResult（研究版本）。
// 兩者統一轉為 SpcChartData 後餵給 buildSpcChartModel，重用既有圖表與能力卡片。
import type {
  ProcessCapability,
  SpcChartData,
  SpcChartSet,
  SpcStudyResult,
} from '../../../types';
import { buildSpcChartModel, type SpcChartModel } from '../../../utils/spcChartModel';
import { isSpcChartSet, isSpcDistributionAssessment } from '../../../types/spc';

export type SpcReportSource = 'shipping' | 'patrol' | 'mechanical';

export interface ReportField {
  label: string;
  value: string;
}

export interface ProbabilityPoint {
  x: number; // 理論常態分位數 (z)
  y: number; // 觀測值
}

export interface SpcReportModel {
  title: string;
  sourceLabel: string;
  // 表頭識別欄位（手冊要素 1–6）
  identity: ReportField[];
  specLimits: { lsl: number | null; usl: number | null; unit: string; oneSided: 'upper' | 'lower' | null };
  // 要素 4：日期
  studyDate: string;
  dataStart: string;
  dataEnd: string;
  // 要素 7,8：研究備註
  remarks: string;
  // 要素 9,10：樣本資訊
  sampleInfo: { n: number; subgroupSize: string; k: number; strategy: string };
  // 要素 11–14 圖表（重用既有元件）
  chartModel: SpcChartModel;
  runChart: number[]; // 原始值圖
  probabilityPoints: ProbabilityPoint[]; // 機率圖
  // 要素 15,16,17
  locationEstimate: number | null; // X50%
  variationSpread: number | null; // X99.865% − X0.135%
  distributionLabel: string;
  // 要素 18,19
  capability: ProcessCapability | null;
  applicableLabel: string; // 能力(Cp/Cpk) / 績效(Pp/Ppk)
  methodLabel: string;
  // 要素 20
  conclusion: string;
}

const SOURCE_LABEL: Record<SpcReportSource, string> = {
  shipping: '出貨檢驗',
  patrol: '現場巡檢',
  mechanical: '機械性質',
};

const str = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '—';
  return String(value);
};

/** 由排序後樣本值計算指定百分位（線性內插）。 */
export const percentile = (values: number[], p: number): number | null => {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (sorted.length === 0) return null;
  if (sorted.length === 1) return sorted[0];
  const rank = (p / 100) * (sorted.length - 1);
  const low = Math.floor(rank);
  const high = Math.ceil(rank);
  if (low === high) return sorted[low];
  return sorted[low] + (rank - low) * (sorted[high] - sorted[low]);
};

// 標準常態分位數近似（Acklam/Beasley-Springer-Moro 常用有理逼近）
const normalQuantile = (p: number): number => {
  if (p <= 0) return -3.5;
  if (p >= 1) return 3.5;
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.383577518672690e2, -3.066479806614716e1, 2.506628277459239];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416];
  const pLow = 0.02425;
  const pHigh = 1 - pLow;
  let q: number;
  let r: number;
  if (p < pLow) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  if (p <= pHigh) {
    q = p - 0.5;
    r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
      (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  q = Math.sqrt(-2 * Math.log(1 - p));
  return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
    ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
};

/** 常態機率圖點：排序觀測值 vs 理論常態分位數（用中位數位置 (i-0.5)/n）。 */
export const probabilityPlotPoints = (values: number[]): ProbabilityPoint[] => {
  const sorted = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  const n = sorted.length;
  return sorted.map((y, i) => ({ x: normalQuantile((i + 0.5) / n), y }));
};

const buildConclusion = (capability: ProcessCapability | null): string => {
  if (!capability || !capability.available) {
    return '資料不足或不可計算能力指標，請確認樣本數與規格設定。';
  }
  const isCapability = capability.applicable === 'capability';
  const pk = isCapability ? capability.cpk : capability.ppk;
  const target = capability.targets?.pk_target;
  const kind = isCapability ? '製程穩定，回報能力指標 Cp/Cpk' : '製程不穩定或穩定性未證明，回報績效指標 Pp/Ppk';
  if (pk != null && target != null) {
    return capability.achieved
      ? `${kind}；指標達標（≥ ${target.toFixed(2)}），依計畫持續監控。`
      : `${kind}；指標未達標（目標 ≥ ${target.toFixed(2)}），需採取改善/矯正措施。`;
  }
  return `${kind}。`;
};

const buildIdentity = (
  source: SpcReportSource,
  filters: Record<string, unknown>,
): ReportField[] => {
  if (source === 'shipping') {
    return [
      { label: '製程 / 來源', value: '出貨檢驗' },
      { label: '廠商', value: str(filters.vendor) },
      { label: '零件（材質）', value: str(filters.material) },
      { label: '規格', value: str(filters.spec) },
      { label: '檢驗特性', value: str(filters.field) },
    ];
  }
  if (source === 'mechanical') {
    return [
      { label: '製程 / 來源', value: '機械性質' },
      { label: '廠商 ID', value: str(filters.vendor_id) },
      { label: '材質', value: str(filters.material) },
      { label: '產品尺寸', value: str(filters.product_size) },
      { label: '特性 / 位置', value: `${str(filters.item)}（${str(filters.position)}）` },
    ];
  }
  return [
    { label: '製程 / 來源', value: '現場巡檢' },
    { label: '機台 ID', value: str(filters.m_id) },
    { label: '操作員 ID', value: str(filters.op_id) },
    { label: '材質', value: str(filters.mat) },
    { label: '規格', value: str(filters.spec) },
    { label: '項目 / 位置', value: `${str(filters.item)}（${str(filters.pos)}）` },
  ];
};

interface BuildOptions {
  studyType?: string;
  createdAt?: string;
}

/** 由 SpcChartData（即時預覽或研究版本合成）建立報告模型。 */
export const reportModelFromStats = (
  source: SpcReportSource,
  filters: Record<string, unknown>,
  stats: SpcChartData,
  options: BuildOptions = {},
): SpcReportModel => {
  const chartModel = buildSpcChartModel(stats, { showSpecLimits: true });
  const capability = (stats.capability ?? stats.process_capability ?? null) as ProcessCapability | null;
  const allValues = stats.all_values ?? [];
  const dates = (stats.dates ?? []).filter(Boolean).sort();

  const distributionLabel = stats.distribution?.label
    ?? stats.distribution_stats?.model_label
    ?? '常態分布';
  const chartTypeLabel = chartModel.chartType ?? '—';
  const isCapability = capability?.applicable === 'capability';
  const applicableLabel = isCapability ? '能力（Cp/Cpk，製程穩定）' : '績效（Pp/Ppk，不穩定或未證明穩定）';
  const method = capability?.method ?? 'G';

  return {
    title: 'SPC 與製程能力研究報告',
    sourceLabel: SOURCE_LABEL[source],
    identity: buildIdentity(source, filters),
    specLimits: {
      // 規格界限（手冊要素 6）來自規格快照，與能力是否計算無關：
      // 能力可能因時間模型未確認而暫不可用，但規格界限仍應顯示。
      lsl: capability?.lsl ?? (stats.tolerance?.LSL as number | null | undefined) ?? null,
      usl: capability?.usl ?? (stats.tolerance?.USL as number | null | undefined) ?? null,
      unit: '',
      oneSided: capability?.one_sided ?? (stats.tolerance?.one_sided as 'upper' | 'lower' | null | undefined) ?? null,
    },
    studyDate: options.createdAt ? options.createdAt.slice(0, 10) : new Date().toISOString().slice(0, 10),
    dataStart: dates[0] ?? '—',
    dataEnd: dates[dates.length - 1] ?? '—',
    remarks: `${options.studyType ?? '即時預覽'}；${chartTypeLabel} 管制圖；${distributionLabel}`,
    sampleInfo: {
      n: allValues.length,
      subgroupSize: stats.avg_subgroup_size != null ? stats.avg_subgroup_size.toFixed(0) : '1',
      k: (stats.avgs ?? []).length,
      strategy: '固定',
    },
    chartModel,
    runChart: allValues,
    probabilityPoints: probabilityPlotPoints(allValues),
    locationEstimate: percentile(allValues, 50),
    variationSpread: (() => {
      const hi = percentile(allValues, 99.865);
      const lo = percentile(allValues, 0.135);
      return hi != null && lo != null ? hi - lo : null;
    })(),
    distributionLabel,
    capability,
    applicableLabel,
    methodLabel: `${method} 法（分位數法；常態時等同 6σ 公式）`,
    conclusion: buildConclusion(capability),
  };
};

/** 由研究版本合成 SpcChartData 以重用同一條建構路徑。 */
export const chartDataFromVersion = (version: SpcStudyResult): SpcChartData => {
  const charts = isSpcChartSet(version.charts) ? (version.charts as SpcChartSet) : null;
  const samples = version.samples ?? [];
  const allValues = samples.flatMap((s) => s.distribution_values?.length ? s.distribution_values : s.values);
  const capability = version.capability as ProcessCapability;
  return {
    labels: samples.map((s) => s.key),
    ids: samples.map((s) => String(s.record_ids?.[0] ?? s.id)),
    dates: samples.map((s) => (s.timestamp ? s.timestamp.slice(0, 10) : '')),
    avgs: charts?.location.values.map((v) => v ?? Number.NaN) ?? [],
    ranges: charts?.variation.values ?? [],
    subgroup_sizes: charts?.subgroup_sizes ?? [],
    all_values: allValues,
    x_cl: null, x_ucl: null, x_lcl: null, r_cl: null, r_ucl: null, r_lcl: null,
    avg_subgroup_size: charts?.subgroup_sizes?.length
      ? charts.subgroup_sizes.reduce((a, b) => a + b, 0) / charts.subgroup_sizes.length
      : null,
    tolerance: version.specification,
    process_capability: capability,
    distribution_stats: {},
    cpk_trend: [],
    charts: charts ?? undefined,
    stability: version.stability,
    distribution: isSpcDistributionAssessment(version.distribution) ? version.distribution : undefined,
    capability,
    applicability: version.applicability,
    process_stream_key: version.process_stream_key,
    data_hash: version.data_hash,
  } as SpcChartData;
};

export const reportModelFromVersion = (version: SpcStudyResult): SpcReportModel =>
  reportModelFromStats(
    version.source as SpcReportSource,
    version.filters,
    chartDataFromVersion(version),
    {
      studyType: version.study_type === 'ongoing' ? '持續監控研究' : '回溯研究',
      createdAt: version.created_at,
    },
  );
