import { describe, expect, it } from 'vitest';

import type { MsaResultVersion } from '../../../types/msa';

import {
  buildAttributeModel,
  buildBiasModel,
  buildGrrControlChartModel,
  buildGrrVariationModel,
  buildLinearityModel,
  buildModelsForMethod,
  buildNonrepeatableModel,
  buildStabilityModel,
  toCsv,
} from './msaChartModels';

/** fixture 保持純物件，展開時才有精確型別；傳入模型時再轉型。 */
const asResult = (value: object) => value as unknown as MsaResultVersion;

const grrRaw = {
  method_code: 'MSA4_GRR_ANOVA_1_0',
  statistics: {
    ev: 0.0177, av: 0.0225, grr: 0.0287, pv: 0.1122, ndc: 5,
    percent_tolerance: { ev: 10.6, av: 13.5, grr: 17.2, pv: 67.3 },
    percent_study_variation: { ev: 15.3, av: 19.4, grr: 24.7, pv: 96.9 },
  },
  chart_data: {
    xbar_chart: {
      center: 10.1, ucl: 10.3, lcl: 9.9,
      points: { 'A01|P01': 10.0, 'A01|P02': 10.5 },
      out_of_control_points: ['A01|P02'],
    },
    range_chart: {
      center: 0.02, ucl: 0.06, lcl: 0,
      points: { 'A01|P01': 0.02, 'A01|P02': 0.02 },
    },
  },
  conclusion: { percent_basis: 'study_variation' },
};
const grrResult = asResult(grrRaw);

describe('GRR 變差模型', () => {
  it('顯示人類可讀中文，不暴露內部代碼', () => {
    const model = buildGrrVariationModel(grrResult);

    expect(model.data.labels).toEqual([
      '重複性 EV', '再現性 AV', '量具 GRR', '零件間 PV',
    ]);
    expect(model.summary).toContain('量具 GRR 佔研究變差');
    expect(JSON.stringify(model.data)).not.toContain('ev_sigma');
    expect(JSON.stringify(model.data)).not.toContain('percent_study_variation');
  });

  it('依結論選定的百分比口徑取值', () => {
    const model = buildGrrVariationModel(grrResult);
    expect(model.summary).toContain('24.70%');

    const byTolerance = buildGrrVariationModel(asResult({
      ...grrRaw,
      conclusion: { percent_basis: 'tolerance' },
    }));
    expect(byTolerance.summary).toContain('17.20%');
  });

  it('無法計算的分量標示為不可用而不是畫成 0', () => {
    const model = buildGrrVariationModel(asResult({
      ...grrRaw,
      statistics: {
        ...grrRaw.statistics, av: null,
        percent_study_variation: {
          ...grrRaw.statistics.percent_study_variation, av: null,
        },
      },
    }));

    expect(model.data.datasets[0].data[1]).toBeNull();
    const avRow = model.table.rows.find((row) => row.key === 'av');
    expect(avRow?.sigma).toBe('不可用');
    expect(avRow?.share).toBe('不可用');
  });

  it('缺少選定口徑時明說無法計算', () => {
    const model = buildGrrVariationModel(asResult({
      ...grrRaw,
      statistics: { ...grrRaw.statistics, percent_study_variation: null },
    }));

    expect(model.summary).toContain('無法計算');
  });
});

describe('GRR 管制圖模型', () => {
  it('列出子組平均、極差與是否超限', () => {
    const model = buildGrrControlChartModel(grrResult);

    expect(model.table.rows).toHaveLength(2);
    expect(model.table.rows[1].state).toBe('超出管制界限');
    expect(model.summary).toContain('1 個子組落在界限外');
  });
});

describe('偏倚模型', () => {
  const biasResult = {
    statistics: {
      n: 15, mean: 10.0052, reference_value: 10, bias: 0.0052,
      t_value: 13.667, p_value: 1.7e-9,
      confidence_interval: [0.0044, 0.006], significant: true,
    },
    chart_data: { readings: [10.004, 10.006], reference_value: 10, mean: 10.005 },
  } as unknown as MsaResultVersion;

  it('說明信賴區間是否包含 0', () => {
    const model = buildBiasModel(biasResult);

    expect(model.summary).toContain('不包含 0');
    expect(model.summary).toContain('顯著偏倚');
    expect(model.table.rows.at(-1)).toEqual({
      item: '判定', value: '存在顯著偏倚',
    });
  });

  it('無法估計時保留原因而不是給 0', () => {
    const model = buildBiasModel({
      statistics: {
        n: 5, mean: 10.2, reference_value: 10, bias: 0.2,
        t_value: null, p_value: null, confidence_interval: null,
        significant: true,
        estimability_note: '重複性標準差為 0 但偏倚不為 0',
      },
      chart_data: { readings: [10.2], reference_value: 10, mean: 10.2 },
    } as unknown as MsaResultVersion);

    expect(model.summary).toContain('重複性標準差為 0 但偏倚不為 0');
    const interval = model.table.rows.find((row) => row.item === '信賴區間');
    expect(interval?.value).toBe('不可用');
  });
});

describe('線性模型', () => {
  const linearityResult = {
    statistics: {
      regression: { slope: -0.0126, intercept: 0.0737, slope_p_value: 1.6e-13 },
      reference_levels: [
        {
          reference_value: 2, mean_bias: 0.05,
          confidence_interval: [0.04, 0.06], crosses_zero: false,
        },
        {
          reference_value: 6, mean_bias: 0,
          confidence_interval: [-0.01, 0.01], crosses_zero: true,
        },
      ],
      linearity_evidence: {
        acceptable: false, levels_excluding_zero: 1,
        slope_significant: true, intercept_significant: true,
      },
    },
    chart_data: {
      points: [{ x: 2, y: 0.05 }],
      fitted_line: [{ x: 2, y: 0.048 }, { x: 6, y: -0.002 }],
      confidence_band: [{ x: 2, lower: 0.04, upper: 0.056 }],
      prediction_band: [{ x: 2, lower: 0.02, upper: 0.07 }],
    },
  } as unknown as MsaResultVersion;

  it('包含零偏倚線、回歸線與信賴帶', () => {
    const model = buildLinearityModel(linearityResult);

    expect(model.data.datasets.map((dataset) => dataset.label)).toEqual(
      expect.arrayContaining([
        '個別偏倚', '平均偏倚', '回歸線', '零偏倚', '95% 信賴帶',
      ]),
    );
  });

  it('明說判定不採用 R² 單獨判斷', () => {
    const model = buildLinearityModel(linearityResult);

    expect(model.summary).toContain('不採用 R² 單獨判斷');
    expect(model.summary).toContain('判定不合格');
  });

  it('逐量程列出區間是否含 0', () => {
    const model = buildLinearityModel(linearityResult);

    expect(model.table.rows[0].crossesZero).toBe('不含 0');
    expect(model.table.rows[1].crossesZero).toBe('含 0');
  });
});

describe('穩定性模型', () => {
  const stabilityRaw = {
    statistics: {
      chart_type: 'xbar_r', stable: false,
      rule_violations: [
        { rule: 1, index: 1, message: '點超出管制界限' },
        { rule: 4, index: 1, message: '連續 8 點同側' },
      ],
    },
    chart_data: {
      primary_chart: {
        label: 'xbar', center: 10, ucl: 10.1, lcl: 9.9,
        points: [
          { measured_on: '2026-01-01', value: 10.0 },
          { measured_on: '2026-01-08', value: 10.5 },
        ],
      },
    },
  };
  const stabilityResult = asResult(stabilityRaw);

  it('違規點附上規則說明文字', () => {
    const model = buildStabilityModel(stabilityResult);

    expect(model.table.rows[0].violations).toBe('無');
    expect(model.table.rows[1].violations).toContain(
      '規則 1：點超出 3 倍標準差管制界限',
    );
    expect(model.table.rows[1].violations).toContain(
      '規則 4：連續 8 點落在中心線同一側',
    );
  });

  it('穩定時明說沒有判異訊號', () => {
    const model = buildStabilityModel(asResult({
      ...stabilityRaw,
      statistics: { chart_type: 'i_mr', stable: true, rule_violations: [] },
    }));

    expect(model.summary).toContain('未出現任何判異訊號');
  });
});

describe('計數型模型', () => {
  const attributeResult = {
    statistics: {
      accuracy_available: true,
      labels: ['pass', 'fail'],
      confusion_matrix: {
        pass: { pass: 100, fail: 2 },
        fail: { pass: 5, fail: 40 },
      },
      effectiveness: 75, false_accept_rate: 11.9, false_reject_rate: 1.28,
      against_reference: { overall: { kappa: 0.8876 } },
    },
  } as unknown as MsaResultVersion;

  it('confusion matrix 行列總和正確', () => {
    const model = buildAttributeModel(attributeResult);
    const rows = model.table.rows;

    expect(rows[0]).toMatchObject({ actual: 'pass', pass: 100, fail: 2, total: 102 });
    expect(rows[1]).toMatchObject({ actual: 'fail', pass: 5, fail: 40, total: 45 });
    expect(rows[2]).toMatchObject({ actual: '合計', pass: 105, fail: 42, total: 147 });
  });

  it('沒有可信參考標準時不推論正確性', () => {
    const model = buildAttributeModel({
      statistics: {
        accuracy_available: false, labels: ['pass', 'fail'],
        confusion_matrix: {},
      },
    } as unknown as MsaResultVersion);

    expect(model.summary).toContain('不能推論判定是否正確');
    expect(model.summary).not.toContain('有效性');
  });
});

describe('不可重複模型', () => {
  const nonrepeatableResult = {
    statistics: {
      design_type: 'split_sample', mean_difference: 0.01,
      repeatability_sigma: 0.0011,
      unidentifiable_sources: ['reproducibility', 'part_variation'],
    },
    chart_data: {
      pairs: [
        { unit: 'U01', first: 10, second: 10.01, difference: 0.01 },
      ],
    },
  } as unknown as MsaResultVersion;

  it('顯示配對線與差值分布', () => {
    const model = buildNonrepeatableModel(nonrepeatableResult);

    expect(model.data.datasets.map((dataset) => dataset.label)).toEqual(
      ['第一次量測', '第二次量測', '配對差'],
    );
    expect(model.table.rows[0]).toMatchObject({ unit: 'U01' });
  });

  it('明確說明本設計無法分離哪些變差來源', () => {
    const model = buildNonrepeatableModel(nonrepeatableResult);

    expect(model.summary).toContain('無法分離：reproducibility、part_variation');
  });
});

describe('共用契約', () => {
  it('每個模型都同時提供標題、摘要與資料表', () => {
    const models = buildModelsForMethod(grrResult);

    expect(models).toHaveLength(2);
    for (const model of models) {
      expect(model.title).toBeTruthy();
      expect(model.summary).toBeTruthy();
      expect(model.table.columns.length).toBeGreaterThan(0);
      expect(model.table.rows.length).toBeGreaterThan(0);
    }
  });

  it('未知方法不硬湊圖表', () => {
    expect(buildModelsForMethod(asResult({
      ...grrRaw, method_code: 'UNKNOWN',
    }))).toEqual([]);
  });

  it('資料表可輸出為跳脫過的 CSV', () => {
    const csv = toCsv(buildGrrVariationModel(grrResult));

    expect(csv.split('\n')[0]).toBe('變差來源,標準差,佔比');
    expect(csv.split('\n')[1]).toContain('重複性 EV');
  });
});
