// AIAG-VDA SPC 2026 §11.2 Figure 11-1 一頁式製程能力研究報告版面。
import { Line, Scatter } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';
import type { ChartData, ChartOptions } from 'chart.js';

import ControlChartCard from '../../patrol/ControlChartCard';
import HistogramDistributionChart from '../HistogramDistributionChart';
import type { SpcReportModel } from './spcReportModel';

// 報告可從任一頁開啟，確保其圖表所需的軸/元素已註冊（register 為冪等）。
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler);

interface SpcReportViewProps {
  model: SpcReportModel;
  statsItem: string;
}

const fmt = (value: number | null, digits = 4): string =>
  value == null || !Number.isFinite(value) ? '—' : value.toFixed(digits);

const compactLineOptions: ChartOptions<'line'> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  elements: { point: { radius: 1 }, line: { borderWidth: 1 } },
  scales: { x: { ticks: { display: false } } },
};

const scatterOptions: ChartOptions<'scatter'> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { title: { display: true, text: '理論常態分位數 (z)' } },
    y: { title: { display: true, text: '觀測值' } },
  },
};

const num3 = (v: number | null | undefined): string =>
  v == null || !Number.isFinite(v) ? '—' : v.toFixed(3);
const ppm = (v: number | null | undefined): string =>
  v == null || !Number.isFinite(v) ? '—' : Math.round(v).toLocaleString();

export default function SpcReportView({ model }: SpcReportViewProps) {
  const runData: ChartData<'line'> = {
    labels: model.runChart.map((_, i) => i + 1),
    datasets: [{
      label: '原始值',
      data: model.runChart,
      borderColor: '#198754',
      backgroundColor: '#198754',
      tension: 0,
    }],
  };
  const probData: ChartData<'scatter'> = {
    datasets: [{
      label: '機率圖',
      data: model.probabilityPoints,
      borderColor: '#0d6efd',
      backgroundColor: '#0d6efd',
      pointRadius: 2,
    }],
  };

  const cap = model.capability;
  const specText = model.specLimits.oneSided === 'lower'
    ? `LSL = ${fmt(model.specLimits.lsl)}（單邊下限）`
    : model.specLimits.oneSided === 'upper'
      ? `USL = ${fmt(model.specLimits.usl)}（單邊上限）`
      : `LSL = ${fmt(model.specLimits.lsl)}, USL = ${fmt(model.specLimits.usl)}`;

  return (
    <div className="spc-report">
      <div className="spc-report-header d-flex justify-content-between align-items-start">
        <div>
          <h2 className="h5 mb-0">{model.title}</h2>
          <div className="text-muted small">AIAG-VDA SPC harmonized standard · 方法 2026.2</div>
        </div>
        <div className="text-end small">
          <div>研究日期：{model.studyDate}</div>
          <div>資料期間：{model.dataStart} ~ {model.dataEnd}</div>
        </div>
      </div>

      {/* 要素 1–10：識別與樣本資訊 */}
      <table className="table table-bordered table-sm spc-report-meta mt-2 mb-2">
        <tbody>
          <tr>
            {model.identity.map((f) => (
              <td key={f.label}><div className="spc-report-key">{f.label}</div>{f.value}</td>
            ))}
          </tr>
          <tr>
            <td colSpan={Math.max(1, model.identity.length - 2)}>
              <div className="spc-report-key">規格界限</div>{specText}
            </td>
            <td>
              <div className="spc-report-key">研究備註</div>{model.remarks}
            </td>
            <td>
              <div className="spc-report-key">樣本 N / 子組 n / 組數 k / 抽樣</div>
              {model.sampleInfo.n} / {model.sampleInfo.subgroupSize} / {model.sampleInfo.k} / {model.sampleInfo.strategy}
            </td>
          </tr>
        </tbody>
      </table>

      {/* 要素 11–14：四張圖 */}
      <div className="row g-2">
        <div className="col-6">
          <div className="spc-report-chart-title">① 直方圖</div>
          {model.chartModel.histogramData
            ? <HistogramDistributionChart histogramData={model.chartModel.histogramData} sampleCount={model.sampleInfo.n} />
            : <div className="text-muted small">無足夠資料</div>}
        </div>
        <div className="col-6">
          <div className="spc-report-chart-title">② 原始值圖</div>
          <div style={{ height: 160 }}><Line data={runData} options={compactLineOptions} /></div>
        </div>
        <div className="col-6">
          <div className="spc-report-chart-title">③ 機率圖（常態）</div>
          <div style={{ height: 160 }}><Scatter data={probData} options={scatterOptions} /></div>
        </div>
        <div className="col-6">
          <div className="spc-report-chart-title">④ 管制圖</div>
          {model.chartModel.chartData
            ? <ControlChartCard title={`${model.chartModel.locationLabel} 管制圖`} data={model.chartModel.chartData.xBar} ids={model.chartModel.ids} getViolationReasons={() => ''} />
            : <div className="text-muted small">無足夠資料</div>}
        </div>
      </div>

      {/* 要素 15–17：位置/變異/分布 */}
      <table className="table table-bordered table-sm spc-report-meta mt-2 mb-2">
        <tbody>
          <tr>
            <td><div className="spc-report-key">製程位置估計 X₅₀%</div>{fmt(model.locationEstimate)}</td>
            <td><div className="spc-report-key">製程變異估計 X₉₉.₈₆₅% − X₀.₁₃₅%</div>{fmt(model.variationSpread)}</td>
            <td><div className="spc-report-key">分布模型</div>{model.distributionLabel}</td>
          </tr>
          <tr>
            <td colSpan={2}><div className="spc-report-key">績效 / 能力要求</div>{model.applicableLabel}</td>
            <td><div className="spc-report-key">計算方法</div>{model.methodLabel}</td>
          </tr>
        </tbody>
      </table>

      {/* 要素 18,19：能力/績效指標（精簡呈現，貼近手冊 Figure 11-1） */}
      {(() => {
        if (!cap || !cap.available) {
          return (
            <div className="spc-report-conclusion mt-2">
              <div className="spc-report-key">績效 / 能力指標</div>
              <div className="text-muted">
                無法計算指數{cap?.capability_reason ? `（${cap.capability_reason}）` : ''}——
                請確認樣本數與規格界限設定。
              </div>
            </div>
          );
        }
        const isCap = cap.applicable === 'capability';
        const pLabel = `${isCap ? 'Cp' : 'Pp'}.${cap.method ?? 'G'}`;
        const pkLabel = `${isCap ? 'Cpk' : 'Ppk'}.${cap.method ?? 'G'}`;
        const pVal = isCap ? cap.cp : cap.pp;
        const pkVal = isCap ? cap.cpk : cap.ppk;
        const t = cap.targets;
        return (
          <table className="table table-bordered table-sm spc-report-meta mt-2 mb-2">
            <tbody>
              <tr>
                {model.specLimits.oneSided == null && (
                  <td><div className="spc-report-key">{pLabel}</div>{num3(pVal)}{t?.p_target != null ? `（目標 ≥ ${t.p_target.toFixed(2)}）` : ''}</td>
                )}
                <td><div className="spc-report-key">{pkLabel}</div>{num3(pkVal)}{t?.pk_target != null ? `（目標 ≥ ${t.pk_target.toFixed(2)}）` : ''}{cap.achieved != null ? ` ${cap.achieved ? '達標' : '未達標'}` : ''}</td>
                <td><div className="spc-report-key">CWk（組內參考）</div>{num3(cap.cwk)}</td>
                <td><div className="spc-report-key">估計超規格 PPM（上 / 下 / 總）</div>{ppm(cap.ppm?.upper)} / {ppm(cap.ppm?.lower)} / {ppm(cap.ppm?.total)}</td>
              </tr>
            </tbody>
          </table>
        );
      })()}

      {/* 要素 20：結論 */}
      <div className="spc-report-conclusion mt-2">
        <div className="spc-report-key">結論 / 建議 / 矯正措施</div>
        <div>{model.conclusion}</div>
      </div>
    </div>
  );
}
