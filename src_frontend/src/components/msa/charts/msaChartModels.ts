/**
 * MSA 圖表的純資料模型。
 *
 * 兩個原則貫穿整份檔案：
 * 1. 圖表一定附帶文字摘要與資料表——只靠顏色與形狀傳達的結論不算數。
 * 2. 無法計算的指標一律省略或標示為不可用，絕不畫成 0。
 */

import type { MsaJsonObject, MsaResultVersion } from '../../../types/msa';

export interface AccessibleMsaChartModel {
  title: string;
  summary: string;
  data: {
    labels: string[];
    datasets: Array<{
      label: string;
      data: Array<number | null | { x: number; y: number }>;
      kind?: 'line' | 'bar' | 'scatter';
    }>;
  };
  options: MsaJsonObject;
  table: {
    columns: Array<{ key: string; label: string }>;
    rows: Array<Record<string, string | number | null>>;
  };
}

const asRecord = (value: unknown): Record<string, unknown> =>
  (value && typeof value === 'object' ? value as Record<string, unknown> : {});

const num = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const fixed = (value: number | null, digits = 4): string =>
  value == null ? '不可用' : value.toFixed(digits);

const percent = (value: number | null): string =>
  value == null ? '不可用' : `${value.toFixed(2)}%`;

const BASE_OPTIONS: MsaJsonObject = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' } },
};

// ---------------------------------------------------------------------------
// GRR：變差分量
// ---------------------------------------------------------------------------

const COMPONENT_LABELS: Array<[string, string]> = [
  ['ev', '重複性 EV'],
  ['av', '再現性 AV'],
  ['grr', '量具 GRR'],
  ['pv', '零件間 PV'],
];

export const buildGrrVariationModel = (
  result: Pick<MsaResultVersion, 'statistics' | 'conclusion'>,
): AccessibleMsaChartModel => {
  const statistics = asRecord(result.statistics);
  const basis = result.conclusion?.percent_basis ?? 'study_variation';
  const percentField = {
    tolerance: 'percent_tolerance',
    study_variation: 'percent_study_variation',
    process_variation: 'percent_process',
  }[basis] ?? 'percent_study_variation';
  const percents = asRecord(statistics[percentField]);

  const labels = COMPONENT_LABELS.map(([, label]) => label);
  const sigmas = COMPONENT_LABELS.map(([key]) => num(statistics[key]));
  const shares = COMPONENT_LABELS.map(([key]) => num(percents[key]));

  const grrShare = shares[2];
  const summary = grrShare == null
    ? '量具 GRR 佔研究變差的比例目前無法計算，請確認選定的百分比口徑是否有可用數值。'
    : `量具 GRR 佔研究變差 ${percent(grrShare)}；`
      + `重複性 ${percent(shares[0])}、再現性 ${percent(shares[1])}、`
      + `零件間變差 ${percent(shares[3])}。`;

  return {
    title: '量測系統變差分量',
    summary,
    data: {
      labels,
      datasets: [
        { label: '標準差', data: sigmas, kind: 'bar' },
        { label: '佔比 %', data: shares, kind: 'bar' },
      ],
    },
    options: BASE_OPTIONS,
    table: {
      columns: [
        { key: 'component', label: '變差來源' },
        { key: 'sigma', label: '標準差' },
        { key: 'share', label: '佔比' },
      ],
      rows: COMPONENT_LABELS.map(([key, label], index) => ({
        component: label,
        sigma: fixed(sigmas[index], 6),
        share: percent(shares[index]),
        // 無法估計的分量保留 null，讓資料表顯示「不可用」而不是 0
        raw: sigmas[index],
        key,
      })),
    },
  };
};

// ---------------------------------------------------------------------------
// GRR：Xbar / R 管制圖
// ---------------------------------------------------------------------------

export const buildGrrControlChartModel = (
  result: Pick<MsaResultVersion, 'chart_data'>,
): AccessibleMsaChartModel => {
  const charts = asRecord(result.chart_data);
  const xbar = asRecord(charts.xbar_chart);
  const range = asRecord(charts.range_chart);
  const points = asRecord(xbar.points);
  const rangePoints = asRecord(range.points);
  const keys = Object.keys(points).sort();
  const outOfControl = new Set(
    Array.isArray(xbar.out_of_control_points)
      ? xbar.out_of_control_points as string[] : [],
  );

  return {
    title: '平均值與極差管制圖',
    summary:
      `平均值圖中心線 ${fixed(num(xbar.center))}，`
      + `管制界限 ${fixed(num(xbar.lcl))} 至 ${fixed(num(xbar.ucl))}；`
      + `共 ${outOfControl.size} 個子組落在界限外`
      + `（在 GRR 研究中超限代表零件差異可被鑑別）。`,
    data: {
      labels: keys,
      datasets: [
        { label: '子組平均', data: keys.map((key) => num(points[key])), kind: 'line' },
        {
          label: '管制上限',
          data: keys.map(() => num(xbar.ucl)),
          kind: 'line',
        },
        {
          label: '管制下限',
          data: keys.map(() => num(xbar.lcl)),
          kind: 'line',
        },
      ],
    },
    options: BASE_OPTIONS,
    table: {
      columns: [
        { key: 'subgroup', label: '子組（評價人｜零件）' },
        { key: 'mean', label: '平均' },
        { key: 'range', label: '極差' },
        { key: 'state', label: '狀態' },
      ],
      rows: keys.map((key) => ({
        subgroup: key,
        mean: fixed(num(points[key])),
        range: fixed(num(rangePoints[key])),
        state: outOfControl.has(key) ? '超出管制界限' : '界限內',
      })),
    },
  };
};

// ---------------------------------------------------------------------------
// 偏倚
// ---------------------------------------------------------------------------

export const buildBiasModel = (
  result: Pick<MsaResultVersion, 'statistics' | 'chart_data'>,
): AccessibleMsaChartModel => {
  const statistics = asRecord(result.statistics);
  const charts = asRecord(result.chart_data);
  const readings = Array.isArray(charts.readings)
    ? charts.readings as number[] : [];
  const interval = Array.isArray(statistics.confidence_interval)
    ? statistics.confidence_interval as number[] : null;
  const bias = num(statistics.bias);
  const significant = statistics.significant === true;

  return {
    title: '偏倚與信賴區間',
    summary: interval
      ? `偏倚 ${fixed(bias)}，95% 信賴區間 ${fixed(interval[0])} 至 `
        + `${fixed(interval[1])}，`
        + `${significant ? '不包含 0，判定存在顯著偏倚' : '包含 0，未觀察到顯著偏倚'}。`
      : `偏倚 ${fixed(bias)}；`
        + `${statistics.estimability_note ?? '無法估計信賴區間'}。`,
    data: {
      labels: readings.map((_value, index) => `第 ${index + 1} 次`),
      datasets: [
        { label: '量測讀值', data: readings, kind: 'scatter' },
        {
          label: '參考值',
          data: readings.map(() => num(charts.reference_value)),
          kind: 'line',
        },
        {
          label: '平均值',
          data: readings.map(() => num(charts.mean)),
          kind: 'line',
        },
      ],
    },
    options: BASE_OPTIONS,
    table: {
      columns: [
        { key: 'item', label: '項目' },
        { key: 'value', label: '值' },
      ],
      rows: [
        { item: '量測次數', value: num(statistics.n) },
        { item: '平均值', value: fixed(num(statistics.mean)) },
        { item: '參考值', value: fixed(num(statistics.reference_value)) },
        { item: '偏倚', value: fixed(bias) },
        { item: 't 值', value: fixed(num(statistics.t_value)) },
        { item: 'p 值', value: fixed(num(statistics.p_value), 6) },
        {
          item: '信賴區間',
          value: interval
            ? `${fixed(interval[0])} 至 ${fixed(interval[1])}` : '不可用',
        },
        { item: '判定', value: significant ? '存在顯著偏倚' : '未觀察到顯著偏倚' },
      ],
    },
  };
};

// ---------------------------------------------------------------------------
// 線性
// ---------------------------------------------------------------------------

export const buildLinearityModel = (
  result: Pick<MsaResultVersion, 'statistics' | 'chart_data'>,
): AccessibleMsaChartModel => {
  const statistics = asRecord(result.statistics);
  const charts = asRecord(result.chart_data);
  const regression = asRecord(statistics.regression);
  const levels = Array.isArray(statistics.reference_levels)
    ? statistics.reference_levels as Array<Record<string, unknown>> : [];
  const points = Array.isArray(charts.points)
    ? charts.points as Array<{ x: number; y: number }> : [];
  const fitted = Array.isArray(charts.fitted_line)
    ? charts.fitted_line as Array<{ x: number; y: number }> : [];
  const confidence = Array.isArray(charts.confidence_band)
    ? charts.confidence_band as Array<Record<string, number>> : [];
  const evidence = asRecord(statistics.linearity_evidence);

  return {
    title: '線性：偏倚與量程',
    summary:
      `回歸斜率 ${fixed(num(regression.slope), 6)}`
      + `（p = ${fixed(num(regression.slope_p_value), 6)}）；`
      + `${evidence.levels_excluding_zero ?? 0} 個量程的偏倚區間不含 0；`
      + `判定${evidence.acceptable ? '合格' : '不合格'}。`
      + '判定僅依斜率、截距與各量程區間，不採用 R² 單獨判斷。',
    data: {
      labels: levels.map((level) => String(level.reference_value)),
      datasets: [
        { label: '個別偏倚', data: points, kind: 'scatter' },
        {
          label: '平均偏倚',
          data: levels.map((level) => num(level.mean_bias)),
          kind: 'scatter',
        },
        {
          label: '回歸線',
          data: fitted.map((point) => point.y),
          kind: 'line',
        },
        { label: '零偏倚', data: fitted.map(() => 0), kind: 'line' },
        {
          label: '95% 信賴帶',
          data: confidence.map((band) => num(band.upper)),
          kind: 'line',
        },
        {
          label: '95% 預測帶',
          data: (Array.isArray(charts.prediction_band)
            ? charts.prediction_band as Array<Record<string, number>> : []
          ).map((band) => num(band.upper)),
          kind: 'line',
        },
      ],
    },
    options: BASE_OPTIONS,
    table: {
      columns: [
        { key: 'reference', label: '參考量程' },
        { key: 'meanBias', label: '平均偏倚' },
        { key: 'interval', label: '95% 信賴區間' },
        { key: 'crossesZero', label: '區間是否含 0' },
      ],
      rows: levels.map((level) => {
        const interval = Array.isArray(level.confidence_interval)
          ? level.confidence_interval as number[] : null;
        return {
          reference: String(level.reference_value),
          meanBias: fixed(num(level.mean_bias)),
          interval: interval
            ? `${fixed(interval[0])} 至 ${fixed(interval[1])}` : '不可用',
          crossesZero: level.crosses_zero ? '含 0' : '不含 0',
        };
      }),
    },
  };
};

// ---------------------------------------------------------------------------
// 穩定性
// ---------------------------------------------------------------------------

const RULE_TEXT: Record<number, string> = {
  1: '規則 1：點超出 3 倍標準差管制界限',
  2: '規則 2：連續 3 點中有 2 點落在同側 2 倍標準差之外',
  3: '規則 3：連續 5 點中有 4 點落在同側 1 倍標準差之外',
  4: '規則 4：連續 8 點落在中心線同一側',
};

export const buildStabilityModel = (
  result: Pick<MsaResultVersion, 'statistics' | 'chart_data'>,
): AccessibleMsaChartModel => {
  const statistics = asRecord(result.statistics);
  const charts = asRecord(result.chart_data);
  const primary = asRecord(charts.primary_chart);
  const points = Array.isArray(primary.points)
    ? primary.points as Array<Record<string, unknown>> : [];
  const violations = Array.isArray(statistics.rule_violations)
    ? statistics.rule_violations as Array<Record<string, unknown>> : [];
  const violationByIndex = new Map<number, string[]>();
  for (const violation of violations) {
    const index = Number(violation.index);
    const list = violationByIndex.get(index) ?? [];
    list.push(RULE_TEXT[Number(violation.rule)] ?? String(violation.message));
    violationByIndex.set(index, list);
  }

  return {
    title: `穩定性管制圖（${statistics.chart_type ?? '未知圖型'}）`,
    summary: statistics.stable
      ? `基準期間共 ${points.length} 期，未出現任何判異訊號。`
      : `基準期間共 ${points.length} 期，出現 ${violations.length} 次判異訊號；`
        + '每次違反的規則列於下方資料表。',
    data: {
      labels: points.map((point) => String(point.measured_on)),
      datasets: [
        {
          label: String(primary.label ?? '量測值'),
          data: points.map((point) => num(point.value)),
          kind: 'line',
        },
        {
          label: '管制上限',
          data: points.map(() => num(primary.ucl)),
          kind: 'line',
        },
        {
          label: '管制下限',
          data: points.map(() => num(primary.lcl)),
          kind: 'line',
        },
      ],
    },
    options: BASE_OPTIONS,
    table: {
      columns: [
        { key: 'measuredOn', label: '量測日期' },
        { key: 'value', label: '值' },
        { key: 'violations', label: '判異規則' },
      ],
      rows: points.map((point, index) => ({
        measuredOn: String(point.measured_on),
        value: fixed(num(point.value)),
        violations: (violationByIndex.get(index) ?? []).join('；') || '無',
      })),
    },
  };
};

// ---------------------------------------------------------------------------
// 計數型
// ---------------------------------------------------------------------------

export const buildAttributeModel = (
  result: Pick<MsaResultVersion, 'statistics'>,
): AccessibleMsaChartModel => {
  const statistics = asRecord(result.statistics);
  const labels = Array.isArray(statistics.labels)
    ? statistics.labels as string[] : [];
  const matrix = asRecord(statistics.confusion_matrix);
  const accuracyAvailable = statistics.accuracy_available === true;

  const rows = labels.map((actual) => {
    const row = asRecord(matrix[actual]);
    const counts = labels.map((predicted) => num(row[predicted]) ?? 0);
    return {
      actual,
      counts,
      total: counts.reduce((sum, value) => sum + value, 0),
    };
  });
  const columnTotals = labels.map((_label, index) =>
    rows.reduce((sum, row) => sum + row.counts[index], 0));

  const summary = accuracyAvailable
    ? `Kappa ${fixed(num(asRecord(asRecord(statistics.against_reference).overall).kappa))}`
      + `，有效性 ${percent(num(statistics.effectiveness))}`
      + `，誤收率 ${percent(num(statistics.false_accept_rate))}`
      + `，誤拒率 ${percent(num(statistics.false_reject_rate))}。`
    : '沒有可信的參考標準，因此只能報告一致性，不能推論判定是否正確。';

  return {
    title: '計數型判定矩陣',
    summary,
    data: {
      labels,
      datasets: rows.map((row) => ({
        label: `參考=${row.actual}`,
        data: row.counts,
        kind: 'bar' as const,
      })),
    },
    options: BASE_OPTIONS,
    table: {
      columns: [
        { key: 'actual', label: '參考真值' },
        ...labels.map((label) => ({ key: label, label: `判定 ${label}` })),
        { key: 'total', label: '合計' },
      ],
      rows: [
        ...rows.map((row) => ({
          actual: row.actual,
          ...Object.fromEntries(
            labels.map((label, index) => [label, row.counts[index]]),
          ),
          total: row.total,
        })),
        {
          actual: '合計',
          ...Object.fromEntries(
            labels.map((label, index) => [label, columnTotals[index]]),
          ),
          total: columnTotals.reduce((sum, value) => sum + value, 0),
        },
      ],
    },
  };
};

// ---------------------------------------------------------------------------
// 不可重複
// ---------------------------------------------------------------------------

export const buildNonrepeatableModel = (
  result: Pick<MsaResultVersion, 'statistics' | 'chart_data'>,
): AccessibleMsaChartModel => {
  const statistics = asRecord(result.statistics);
  const charts = asRecord(result.chart_data);
  const pairs = Array.isArray(charts.pairs)
    ? charts.pairs as Array<Record<string, unknown>> : [];
  const unidentifiable = Array.isArray(statistics.unidentifiable_sources)
    ? statistics.unidentifiable_sources as string[] : [];

  return {
    title: `不可重複研究（${statistics.design_type ?? '未指定設計'}）`,
    summary:
      `配對 ${pairs.length} 組，配對差平均 `
      + `${fixed(num(statistics.mean_difference), 6)}，`
      + `重複性標準差 ${fixed(num(statistics.repeatability_sigma), 6)}。`
      + `本設計無法分離：${unidentifiable.join('、') || '無'}。`,
    data: {
      labels: pairs.map((pair) => String(pair.unit)),
      datasets: [
        {
          label: '第一次量測',
          data: pairs.map((pair) => num(pair.first)),
          kind: 'line',
        },
        {
          label: '第二次量測',
          data: pairs.map((pair) => num(pair.second)),
          kind: 'line',
        },
        {
          label: '配對差',
          data: pairs.map((pair) => num(pair.difference)),
          kind: 'bar',
        },
      ],
    },
    options: BASE_OPTIONS,
    table: {
      columns: [
        { key: 'unit', label: '配對單位' },
        { key: 'first', label: '第一次' },
        { key: 'second', label: '第二次' },
        { key: 'difference', label: '差值' },
      ],
      rows: pairs.map((pair) => ({
        unit: String(pair.unit),
        first: fixed(num(pair.first)),
        second: fixed(num(pair.second)),
        difference: fixed(num(pair.difference), 6),
      })),
    },
  };
};

/** 依方法代碼取得該方法的圖表模型組合。 */
export const buildModelsForMethod = (
  result: MsaResultVersion,
): AccessibleMsaChartModel[] => {
  switch (result.method_code) {
    case 'MSA4_GRR_RANGE_1_0':
      return [buildGrrVariationModel(result)];
    case 'MSA4_GRR_XBAR_R_1_0':
    case 'MSA4_GRR_ANOVA_1_0':
      return [
        buildGrrVariationModel(result),
        buildGrrControlChartModel(result),
      ];
    case 'MSA4_BIAS_1_0':
      return [buildBiasModel(result)];
    case 'MSA4_LINEARITY_1_0':
      return [buildLinearityModel(result)];
    case 'MSA4_STABILITY_1_0':
      return [buildStabilityModel(result)];
    case 'MSA4_ATTRIBUTE_1_0':
      return [buildAttributeModel(result)];
    case 'MSA4_NONREPEATABLE_1_0':
      return [buildNonrepeatableModel(result)];
    default:
      return [];
  }
};

/** 把資料表轉成可下載的 CSV；來源是結果版本保存的圖表資料。 */
export const toCsv = (model: AccessibleMsaChartModel): string => {
  const escape = (value: string | number | null) => {
    const text = value == null ? '' : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  const header = model.table.columns.map((column) => escape(column.label));
  const body = model.table.rows.map((row) =>
    model.table.columns.map((column) => escape(row[column.key] ?? null)));
  return [header, ...body].map((row) => row.join(',')).join('\n');
};
