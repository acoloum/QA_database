// AIAG-VDA SPC 2026 §11.2 Figure 11-1 一頁式製程能力研究報告版面。
import { Chart, Line, Scatter } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, BarController, LineController, ScatterController,
  Title, Tooltip, Legend, Filler,
} from 'chart.js';
import type { ChartData, ChartOptions } from 'chart.js';

import type { SpcReportModel } from './spcReportModel';

// 報告可從任一頁開啟，確保其圖表所需的軸/元素/控制器已註冊（register 為冪等）。
ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  BarController, LineController, ScatterController, Title, Tooltip, Legend, Filler,
);

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
    x: { title: { display: true, text: '理論常態分位數 (z)' }, ticks: { font: { size: 8 } } },
    y: { ticks: { font: { size: 8 } } },
  },
};

const histOptions: ChartOptions<'bar'> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { font: { size: 7 }, maxRotation: 0, autoSkip: true } },
    y: { beginAtZero: true, ticks: { font: { size: 8 } } },
  },
};

const ctrlOptions: ChartOptions<'line'> = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  elements: { point: { radius: 2 }, line: { borderWidth: 1 } },
  scales: {
    x: { ticks: { display: false } },
    y: { ticks: { font: { size: 8 } } },
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

  const hist = model.chartModel.histogramData;
  const histData: ChartData<'bar'> = hist ? {
    labels: hist.bins.map((b) => b.label),
    datasets: [
      { type: 'bar' as const, label: '頻次', data: hist.bins.map((b) => b.count), backgroundColor: 'rgba(13,110,253,0.5)', borderColor: '#0d6efd', borderWidth: 1, barPercentage: 1, categoryPercentage: 1, order: 2 },
      ...(hist.normalCurve.length ? [{ type: 'line' as const, label: '常態', data: hist.normalCurve, borderColor: '#dc3545', borderWidth: 1.5, pointRadius: 0, tension: 0.4, order: 1 }] : []),
    ] as ChartData<'bar'>['datasets'],
  } : { labels: [], datasets: [] };
  const ctrl = model.chartModel.chartData;

  const cap = model.capability;
  const specText = model.specLimits.oneSided === 'lower'
    ? `LSL = ${fmt(model.specLimits.lsl)}（單邊下限）`
    : model.specLimits.oneSided === 'upper'
      ? `USL = ${fmt(model.specLimits.usl)}（單邊上限）`
      : `LSL = ${fmt(model.specLimits.lsl)}, USL = ${fmt(model.specLimits.usl)}`;

  const isCap = cap?.applicable === 'capability';
  const pLabel = `${isCap ? 'Cp' : 'Pp'}.${cap?.method ?? 'G'}`;
  const pkLabel = `${isCap ? 'Cpk' : 'Ppk'}.${cap?.method ?? 'G'}`;
  const pVal = isCap ? cap?.cp : cap?.pp;
  const pkVal = isCap ? cap?.cpk : cap?.ppk;
  const t = cap?.targets;

  return (
    <div className="spc-report">
      <div className="spc-report-grid">
        {/* 標題列 */}
        <div className="spc-report-titlebar">
          <span>{model.title}</span>
          <span className="spc-report-std">AIAG / VDA SPC 協調標準 · 方法 2026.2</span>
        </div>

        {/* 識別欄位 */}
        <div className="spc-grid-row">
          {model.identity.map((f) => (
            <div className="spc-grid-cell" key={f.label}>
              <div className="spc-grid-title">{f.label}</div>{f.value}
            </div>
          ))}
        </div>

        {/* 規格 / 日期 / 資料期間 */}
        <div className="spc-grid-row">
          <div className="spc-grid-cell" style={{ flexGrow: 2 }}>
            <div className="spc-grid-title">規格界限</div>{specText}
            {model.specLimits.unit ? <span>，單位：{model.specLimits.unit}</span> : null}
          </div>
          <div className="spc-grid-cell">
            <div className="spc-grid-title">研究日期</div>{model.studyDate}
          </div>
          <div className="spc-grid-cell" style={{ flexGrow: 2 }}>
            <div className="spc-grid-title">資料蒐集期間（開始 / 結束）</div>{model.dataStart} ~ {model.dataEnd}
          </div>
        </div>

        {/* 研究備註 */}
        <div className="spc-grid-row">
          <div className="spc-grid-cell">
            <div className="spc-grid-title">研究備註</div>{model.remarks}
          </div>
        </div>

        {/* 樣本資訊 */}
        <div className="spc-grid-row">
          <div className="spc-grid-cell">
            <div className="spc-grid-title">樣本資訊</div>
            樣本數 N = {model.sampleInfo.n}，子組大小 n = {model.sampleInfo.subgroupSize}，子組數 k = {model.sampleInfo.k}，抽樣策略 = {model.sampleInfo.strategy}
          </div>
        </div>

        {/* 四張圖 2×2 */}
        <div className="spc-grid-row">
          <div className="spc-grid-cell">
            <div className="spc-grid-title">直方圖</div>
            <div className="spc-grid-chart">
              {hist ? <Chart type="bar" data={histData} options={histOptions} /> : <span className="text-muted">無足夠資料</span>}
            </div>
          </div>
          <div className="spc-grid-cell">
            <div className="spc-grid-title">原始值圖</div>
            <div className="spc-grid-chart"><Line data={runData} options={compactLineOptions} /></div>
          </div>
        </div>
        <div className="spc-grid-row">
          <div className="spc-grid-cell">
            <div className="spc-grid-title">機率圖（常態）</div>
            <div className="spc-grid-chart"><Scatter data={probData} options={scatterOptions} /></div>
          </div>
          <div className="spc-grid-cell">
            <div className="spc-grid-title">管制圖（製程位置 / 製程變異）</div>
            {ctrl ? (
              <div className="spc-grid-chart d-flex flex-column">
                <div style={{ flex: 1, minHeight: 0 }}><Line data={ctrl.xBar} options={ctrlOptions} /></div>
                <div style={{ flex: 1, minHeight: 0 }}><Line data={ctrl.rChart} options={ctrlOptions} /></div>
              </div>
            ) : <div className="spc-grid-chart"><span className="text-muted">無足夠資料</span></div>}
          </div>
        </div>

        {/* 位置 / 變異 / 分布 */}
        <div className="spc-grid-row">
          <div className="spc-grid-cell">
            <div className="spc-grid-title">製程位置估計 X₅₀%</div>{fmt(model.locationEstimate)}
          </div>
          <div className="spc-grid-cell">
            <div className="spc-grid-title">製程變異估計 X₉₉.₈₆₅% − X₀.₁₃₅%</div>{fmt(model.variationSpread)}
          </div>
          <div className="spc-grid-cell">
            <div className="spc-grid-title">分布模型</div>{model.distributionLabel}
          </div>
        </div>

        {/* 能力要求 + 計算方法 */}
        <div className="spc-grid-row">
          <div className="spc-grid-cell">
            <div className="spc-grid-title">績效 / 能力要求</div>{model.applicableLabel}
          </div>
          <div className="spc-grid-cell">
            <div className="spc-grid-title">計算方法</div>{model.methodLabel}
          </div>
        </div>

        {/* 計算指標 + PPM */}
        {cap && cap.available ? (
          <div className="spc-grid-row">
            {model.specLimits.oneSided == null && (
              <div className="spc-grid-cell">
                <div className="spc-grid-title">{pLabel}</div>{num3(pVal)}{t?.p_target != null ? `（目標 ≥ ${t.p_target.toFixed(2)}）` : ''}
              </div>
            )}
            <div className="spc-grid-cell">
              <div className="spc-grid-title">{pkLabel}</div>{num3(pkVal)}{t?.pk_target != null ? `（目標 ≥ ${t.pk_target.toFixed(2)}）` : ''}{cap.achieved != null ? ` ${cap.achieved ? '達標' : '未達標'}` : ''}
            </div>
            <div className="spc-grid-cell">
              <div className="spc-grid-title">CWk（組內參考）</div>{num3(cap.cwk)}
            </div>
            <div className="spc-grid-cell">
              <div className="spc-grid-title">估計超規格 PPM（上 / 下 / 總）</div>{ppm(cap.ppm?.upper)} / {ppm(cap.ppm?.lower)} / {ppm(cap.ppm?.total)}
            </div>
          </div>
        ) : (
          <div className="spc-grid-row">
            <div className="spc-grid-cell">
              <div className="spc-grid-title">計算所得的績效 / 能力指標</div>
              <span className="text-muted">無法計算指數{cap?.capability_reason ? `（${cap.capability_reason}）` : ''}——請確認樣本數與規格界限設定。</span>
            </div>
          </div>
        )}

        {/* 結論 */}
        <div className="spc-grid-row">
          <div className="spc-grid-cell">
            <div className="spc-grid-title">結論 / 建議 / 矯正措施</div>{model.conclusion}
          </div>
        </div>
      </div>
    </div>
  );
}
