
import { useState, useMemo } from 'react';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    Title,
    Tooltip,
    Legend,
    Filler
} from 'chart.js';
import { Line, Chart } from 'react-chartjs-2';
import {
    analyzeWECO,
    analyzeRChartWECO,
    getCpkGrade,
    generateHistogramBins,
    normalPDF,
    movingAverage,
    formatPPM,
    getPpmGrade
} from '../../utils/spcAnalysis';
import type { SpcViolation, HistogramBin } from '../../types';
import { Alert, Badge, Button, Card, Col, Row, Form } from 'react-bootstrap';
import { useShippingStats, useExportSpcReport } from '../../hooks/useShipping';
import type { ChartData, TooltipItem, ActiveDataPoint } from 'chart.js';

// Register ChartJS components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler);

interface ShippingChartsProps {
    vendor: string;
    material: string;
    spec: string;
    startDate: string;
    endDate: string;
    onPointClick?: (id: number) => void;
}

const ITEMS = [
    { label: "外徑", key: "外徑" },
    { label: "內徑", key: "內徑" },
    { label: "真圓度", key: "真圓度" },
    { label: "厚度", key: "厚度" },
    { label: "同心度", key: "同心度" },
    { label: "長度", key: "長度" },
    { label: "硬度", key: "硬度" },
    { label: "真直度", key: "真直度" }
];

const ShippingCharts = ({ vendor, material, spec, startDate, endDate, onPointClick }: ShippingChartsProps) => {
    const [statsField, setStatsField] = useState('外徑');
    const [showWeco, setShowWeco] = useState(false);

    const { data: statsData } = useShippingStats({
        field: statsField,
        vendor,
        material,
        spec,
        start_date: startDate,
        end_date: endDate
    });

    const exportSpcReport = useExportSpcReport();

    const { chartData, ids, analysis, rAnalysis, statsSummary, processCapability, histogramData, distributionStats, cpkTrend } = useMemo(() => {
        if (!statsData || !statsData.avgs || statsData.avgs.length === 0) {
            return { chartData: null, ids: [], analysis: null, rAnalysis: null, statsSummary: null, processCapability: null, histogramData: null, distributionStats: null, cpkTrend: null };
        }

        const data = statsData;
        const ids = data.ids || [];
        const count = data.avgs.length;

        // Analyze WECO for X-bar
        const weco = analyzeWECO(data.avgs, data.x_cl, data.x_ucl, data.x_lcl, data.labels);

        // Analyze WECO for R chart
        const rWeco = analyzeRChartWECO(data.ranges, data.r_cl, data.r_ucl, data.labels);

        // Calculate Summary Stats locally (using sample stdDev: N-1)
        const mean = data.avgs.reduce((a: number, b: number) => a + b, 0) / count;
        const sorted = [...data.avgs].sort((a: number, b: number) => a - b);
        const min = sorted[0];
        const max = sorted[count - 1];
        const range = max - min;
        const variance = count > 1
            ? data.avgs.reduce((acc: number, val: number) => acc + Math.pow(val - mean, 2), 0) / (count - 1)
            : 0;
        const stdDev = Math.sqrt(variance);
        const cv = mean !== 0 ? (stdDev / Math.abs(mean)) * 100 : 0;  // CV%

        const summary = {
            count,
            mean: mean.toFixed(3),
            min: min.toFixed(3),
            max: max.toFixed(3),
            range: range.toFixed(3),
            stdDev: stdDev.toFixed(3),
            cv: cv.toFixed(2),
            violations: weco.violations.length + rWeco.violations.length
        };

        // Process capability from backend
        const pc = data.process_capability || null;

        // Distribution stats from backend
        const distStats = data.distribution_stats || null;

        // Cpk trend from backend
        const trend = data.cpk_trend || [];

        // --- Histogram Data ---
        const allValues = data.all_values || [];
        let histData = null;
        if (allValues.length > 0) {
            const bins = generateHistogramBins(allValues);
            const allMean = allValues.reduce((a: number, b: number) => a + b, 0) / allValues.length;
            const allVariance = allValues.length > 1
                ? allValues.reduce((a: number, v: number) => a + Math.pow(v - allMean, 2), 0) / (allValues.length - 1)
                : 0;
            const allStdDev = Math.sqrt(allVariance);
            const binWidth = bins.length > 1 ? bins[1].midpoint - bins[0].midpoint : 1;

            // Normal curve scaled to match histogram area
            const totalArea = allValues.length * binWidth;
            const normalCurve = bins.map(b => normalPDF(b.midpoint, allMean, allStdDev) * totalArea);

            histData = { bins, normalCurve, allMean, allStdDev, usl: pc?.usl, lsl: pc?.lsl };
        }

        // --- Moving Average ---
        const ma = movingAverage(data.avgs, 5);

        // --- Zone bands for X-bar chart ---
        const sigma = (data.x_ucl - data.x_cl) / 3;
        const zone1Upper = Array(count).fill(data.x_cl + sigma);
        const zone1Lower = Array(count).fill(data.x_cl - sigma);
        const zone2Upper = Array(count).fill(data.x_cl + 2 * sigma);
        const zone2Lower = Array(count).fill(data.x_cl - 2 * sigma);

        // Point colors for X-bar
        const pointColors = data.avgs.map((val: number, i: number) => {
            if (val > data.x_ucl || val < data.x_lcl) return '#dc3545';
            if (weco.statuses[i] === 'violation') return '#fd7e14';
            return '#0d6efd';
        });

        const pointRadius = data.avgs.map((_: number, i: number) => {
            if (weco.statuses[i] === 'violation') return 8;
            return 4;
        });

        const pointBorderColor = data.avgs.map((_: number, i: number) => {
            if (weco.statuses[i] === 'violation') return '#fff';
            return '#0d6efd';
        });

        // R-chart point colors
        const rPointColors = data.ranges.map((val: number, i: number) => {
            if (val > data.r_ucl) return '#dc3545';
            if (rWeco.statuses[i] === 'violation') return '#fd7e14';
            return '#6f42c1';
        });

        const rPointRadius = data.ranges.map((_: number, i: number) => {
            if (rWeco.statuses[i] === 'violation') return 8;
            return 4;
        });

        // X-bar chart datasets
        const xBarDatasets: ChartData<'line'>['datasets'] = [
            {
                label: '平均值',
                data: data.avgs,
                borderColor: '#0d6efd',
                backgroundColor: pointColors,
                pointRadius: pointRadius,
                pointBorderColor: pointBorderColor,
                pointBorderWidth: 2,
                tension: 0.1,
                order: 1
            },
            // Moving Average
            {
                label: '移動平均 (MA5)',
                data: ma,
                borderColor: '#20c997',
                borderWidth: 2,
                borderDash: [8, 4],
                pointRadius: 0,
                tension: 0.3,
                order: 2
            },
            // Zone bands - ±1σ (Zone C - green)
            {
                label: '+1σ',
                data: zone1Upper,
                borderColor: 'transparent',
                backgroundColor: 'rgba(40, 167, 69, 0.08)',
                fill: '+1',
                pointRadius: 0,
                order: 10
            },
            {
                label: '-1σ',
                data: zone1Lower,
                borderColor: 'transparent',
                backgroundColor: 'rgba(40, 167, 69, 0.08)',
                fill: '-1',
                pointRadius: 0,
                order: 10
            },
            // Zone bands - ±2σ (Zone B - yellow)
            {
                label: '+2σ',
                data: zone2Upper,
                borderColor: 'rgba(255, 193, 7, 0.3)',
                borderWidth: 1,
                borderDash: [3, 3],
                backgroundColor: 'rgba(255, 193, 7, 0.06)',
                fill: '-2',
                pointRadius: 0,
                order: 10
            },
            {
                label: '-2σ',
                data: zone2Lower,
                borderColor: 'rgba(255, 193, 7, 0.3)',
                borderWidth: 1,
                borderDash: [3, 3],
                backgroundColor: 'rgba(255, 193, 7, 0.06)',
                fill: '+2',
                pointRadius: 0,
                order: 10
            },
            // Control limits
            { label: 'UCL', data: Array(count).fill(data.x_ucl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0, order: 5 },
            { label: 'CL', data: Array(count).fill(data.x_cl), borderColor: 'green', pointRadius: 0, order: 5 },
            { label: 'LCL', data: Array(count).fill(data.x_lcl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0, order: 5 },
        ];

        // USL/LSL lines if available
        if (pc?.available && pc.usl != null && pc.lsl != null) {
            xBarDatasets.push(
                { label: 'USL', data: Array(count).fill(pc.usl), borderColor: '#e83e8c', borderDash: [10, 5], borderWidth: 2, pointRadius: 0, order: 4 },
                { label: 'LSL', data: Array(count).fill(pc.lsl), borderColor: '#e83e8c', borderDash: [10, 5], borderWidth: 2, pointRadius: 0, order: 4 }
            );
        }

        const cData = {
            xBar: {
                labels: data.labels,
                datasets: xBarDatasets
            },
            rChart: {
                labels: data.labels,
                datasets: [
                    {
                        label: '全距 R',
                        data: data.ranges,
                        borderColor: '#6f42c1',
                        backgroundColor: rPointColors,
                        pointRadius: rPointRadius,
                        pointBorderColor: rPointColors,
                        pointBorderWidth: 2,
                        tension: 0.1
                    },
                    { label: 'UCL', data: Array(count).fill(data.r_ucl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0 },
                    { label: 'R̄', data: Array(count).fill(data.r_cl), borderColor: 'green', pointRadius: 0 }
                ]
            }
        };

        return {
            chartData: cData,
            ids,
            analysis: weco,
            rAnalysis: rWeco,
            statsSummary: summary,
            processCapability: pc,
            histogramData: histData,
            distributionStats: distStats,
            cpkTrend: trend
        };

    }, [statsData]);

    // Helper to get violation reasons for tooltip
    const getViolationReasons = (idx: number): string => {
        if (!analysis || !analysis.violations) return '';
        const label = chartData?.xBar?.labels?.[idx];
        const violation = analysis.violations.find((v: SpcViolation) => v.label === label);
        return violation ? violation.reasons.join(', ') : '';
    };

    const getRViolationReasons = (idx: number): string => {
        if (!rAnalysis || !rAnalysis.violations) return '';
        const label = chartData?.rChart?.labels?.[idx];
        const violation = rAnalysis.violations.find((v: SpcViolation) => v.label === label);
        return violation ? violation.reasons.join(', ') : '';
    };

    const handleExportReport = () => {
        exportSpcReport.mutate({
            field: statsField,
            vendor,
            material,
            spec,
            start_date: startDate,
            end_date: endDate
        });
    };

    const cpkGrade = processCapability?.cpk != null ? getCpkGrade(processCapability.cpk) : null;
    const ppkGrade = processCapability?.ppk != null ? getCpkGrade(processCapability.ppk) : null;
    const ppmData = processCapability?.ppm || null;
    const ppmGrade = ppmData ? getPpmGrade(ppmData.total) : null;

    // Combine X-bar and R-chart violations for alert
    const allViolations: SpcViolation[] = [
        ...(analysis?.violations || []),
        ...(rAnalysis?.violations || []).map((v: SpcViolation) => ({ ...v, label: `[R] ${v.label}` }))
    ];

    return (
        <div className="mt-4">
            <div className="d-flex align-items-center justify-content-between mb-3">
                <div className="d-flex align-items-center">
                    <h4 className="mb-0 me-3">📊 SPC 監控與分析</h4>
                    <Form.Select
                        style={{ width: 'auto' }}
                        value={statsField}
                        onChange={e => setStatsField(e.target.value)}
                    >
                        {ITEMS.map(i => <option key={i.key} value={i.key}>{i.label}</option>)}
                    </Form.Select>
                </div>
                <Button
                    variant="outline-primary"
                    size="sm"
                    onClick={handleExportReport}
                    disabled={exportSpcReport.isPending || !chartData}
                >
                    {exportSpcReport.isPending ? '匯出中...' : '📥 匯出 SPC 報告'}
                </Button>
            </div>

            {!chartData ? (
                <div className="text-center py-5 text-muted">
                    選擇的檢驗項目「<strong>{statsField}</strong>」沒有足夠的數據來產生 SPC 圖表，請嘗試其他檢驗項目。
                </div>
            ) : (
                <>

                    {/* Alarm Panel */}
                    {allViolations.length > 0 && (
                        <Alert variant="danger">
                            <div
                                className="d-flex justify-content-between align-items-center"
                                style={{ cursor: 'pointer' }}
                                onClick={() => setShowWeco(!showWeco)}
                            >
                                <Alert.Heading className="mb-0" style={{ fontSize: '1rem' }}>
                                    🚨 偵測到 {allViolations.length} 個製程異常數據點 (WECO Rules) - 點擊展開/收合
                                </Alert.Heading>
                                <i className={`bi bi-chevron-${showWeco ? 'up' : 'down'}`}></i>
                            </div>
                            {showWeco && (
                                <ul className="mb-0 mt-3">
                                    {allViolations.map((v: SpcViolation, idx: number) => (
                                        <li key={idx}><strong>{v.label}</strong>: {v.reasons.join(', ')}</li>
                                    ))}
                                </ul>
                            )}
                        </Alert>
                    )}

                    {/* Stats Summary */}
                    {statsSummary && (
                        <Card className="mb-3 bg-light">
                            <Card.Body>
                                <Row className="text-center">
                                    <Col><strong>樣本數</strong><div className="h4">{statsSummary.count}</div></Col>
                                    <Col><strong>平均值</strong><div className="h4">{statsSummary.mean}</div></Col>
                                    <Col>
                                        <strong>標準差</strong>
                                        <div className={`h4 ${parseFloat(statsSummary.cv) > 5 ? 'text-danger' : 'text-success'}`}>
                                            {statsSummary.stdDev}
                                        </div>
                                        <div className="text-muted small">CV: {statsSummary.cv}%</div>
                                    </Col>
                                    <Col><strong>最小值</strong><div className="h4">{statsSummary.min}</div></Col>
                                    <Col><strong>最大值</strong><div className="h4">{statsSummary.max}</div></Col>
                                    <Col><strong>異常點</strong><div className={`h4 ${statsSummary.violations > 0 ? 'text-danger' : 'text-success'}`}>{statsSummary.violations}</div></Col>
                                </Row>
                            </Card.Body>
                        </Card>
                    )}

                    {/* Distribution Stats (Skewness / Kurtosis) */}
                    {distributionStats && (
                        <Card className="mb-3" style={{
                            border: `2px solid ${distributionStats.normality === 'good' ? '#28a745' : distributionStats.normality === 'moderate' ? '#ffc107' : '#dc3545'}`,
                            backgroundColor: distributionStats.normality === 'good' ? '#f8fff8' : distributionStats.normality === 'moderate' ? '#fffef5' : '#fff8f8'
                        }}>
                            <Card.Body className="py-2">
                                <Row className="text-center align-items-center">
                                    <Col xs="auto">
                                        <strong>📐 常態性檢查</strong>
                                    </Col>
                                    <Col>
                                        <span className="text-muted small me-1">偏態</span>
                                        <strong>{distributionStats.skewness}</strong>
                                    </Col>
                                    <Col>
                                        <span className="text-muted small me-1">峰態</span>
                                        <strong>{distributionStats.kurtosis}</strong>
                                    </Col>
                                    <Col xs="auto">
                                        <Badge bg={distributionStats.normality === 'good' ? 'success' : distributionStats.normality === 'moderate' ? 'warning' : 'danger'}>
                                            {distributionStats.normality_label}
                                        </Badge>
                                    </Col>
                                </Row>
                            </Card.Body>
                        </Card>
                    )}

                    {/* Process Capability Card */}
                    <Card className="mb-4" style={{ border: '2px solid #dee2e6' }}>
                        <Card.Body>
                            <h5 className="mb-3">🎯 製程能力指標</h5>
                            {processCapability?.available ? (
                                <>
                                    <Row className="text-center">
                                        <Col>
                                            <div className="text-muted small">Cp</div>
                                            <div className="h4">{processCapability.cp?.toFixed(3) ?? 'N/A'}</div>
                                            <div className="text-muted small">製程能力</div>
                                        </Col>
                                        <Col>
                                            <div className="text-muted small">Cpk</div>
                                            <div className="h3 mb-1">{processCapability.cpk?.toFixed(3) ?? 'N/A'}</div>
                                            {cpkGrade && (
                                                <Badge style={{ backgroundColor: cpkGrade.bgColor, color: cpkGrade.color, fontSize: '0.85rem' }}>
                                                    {cpkGrade.label} - {cpkGrade.description}
                                                </Badge>
                                            )}
                                        </Col>
                                        <Col>
                                            <div className="text-muted small">Pp</div>
                                            <div className="h4">{processCapability.pp?.toFixed(3) ?? 'N/A'}</div>
                                            <div className="text-muted small">製程績效</div>
                                        </Col>
                                        <Col>
                                            <div className="text-muted small">Ppk</div>
                                            <div className="h3 mb-1">{processCapability.ppk?.toFixed(3) ?? 'N/A'}</div>
                                            {ppkGrade && (
                                                <Badge style={{ backgroundColor: ppkGrade.bgColor, color: ppkGrade.color, fontSize: '0.85rem' }}>
                                                    {ppkGrade.label} - {ppkGrade.description}
                                                </Badge>
                                            )}
                                        </Col>
                                        <Col>
                                            <div className="text-muted small">USL</div>
                                            <div className="h5" style={{ color: '#e83e8c' }}>{processCapability.usl?.toFixed(3) ?? 'N/A'}</div>
                                        </Col>
                                        <Col>
                                            <div className="text-muted small">LSL</div>
                                            <div className="h5" style={{ color: '#e83e8c' }}>{processCapability.lsl?.toFixed(3) ?? 'N/A'}</div>
                                        </Col>
                                    </Row>

                                    {/* PPM Row */}
                                    {ppmData && (
                                        <div className="mt-3 pt-3 border-top">
                                            <Row className="text-center align-items-center">
                                                <Col xs="auto">
                                                    <strong>📉 PPM 不良率估算</strong>
                                                </Col>
                                                <Col>
                                                    <span className="text-muted small me-1">超上限</span>
                                                    <strong>{formatPPM(ppmData.upper)}</strong>
                                                </Col>
                                                <Col>
                                                    <span className="text-muted small me-1">超下限</span>
                                                    <strong>{formatPPM(ppmData.lower)}</strong>
                                                </Col>
                                                <Col>
                                                    <span className="text-muted small me-1">總計</span>
                                                    <strong className="h5 mb-0">{formatPPM(ppmData.total)}</strong>
                                                    <span className="text-muted small ms-1">PPM</span>
                                                </Col>
                                                {ppmGrade && (
                                                    <Col xs="auto">
                                                        <Badge style={{ backgroundColor: ppmGrade.bgColor, color: ppmGrade.color, fontSize: '0.8rem' }}>
                                                            {ppmGrade.label}
                                                        </Badge>
                                                    </Col>
                                                )}
                                            </Row>
                                        </div>
                                    )}
                                </>
                            ) : (
                                <Alert variant="info" className="mb-0">
                                    <i className="bi bi-info-circle me-2"></i>
                                    無法計算 Cp/Cpk — 需要在<strong>公差管理</strong>中設定該材質/規格的 USL（規格上限）和 LSL（規格下限）。
                                    目前選擇的檢驗項目「<strong>{statsField}</strong>」尚未找到對應的公差資料。
                                </Alert>
                            )}
                        </Card.Body>
                    </Card>

                    {/* Charts Row 1: X-bar and R */}
                    <Row className="mb-3">
                        <Col md={6}>
                            <Card className="h-100 shadow-sm">
                                <Card.Body>
                                    <h5 className="card-title text-center">X̄ 平均值管制圖</h5>
                                    <div style={{ height: '300px' }}>
                                        <Line
                                            data={chartData.xBar}
                                            options={{
                                                maintainAspectRatio: false,
                                                plugins: {
                                                    legend: {
                                                        display: true,
                                                        position: 'bottom',
                                                        labels: {
                                                            filter: (item) => {
                                                                const hidden = ['+1σ', '-1σ', '+2σ', '-2σ'];
                                                                return !hidden.includes(item.text);
                                                            },
                                                            usePointStyle: true,
                                                            pointStyle: 'line',
                                                            font: { size: 10 }
                                                        }
                                                    },
                                                    tooltip: {
                                                        callbacks: {
                                                            afterLabel: (ctx: TooltipItem<'line'>) => {
                                                                if (ctx.datasetIndex !== 0) return '';
                                                                const reasons = getViolationReasons(ctx.dataIndex);
                                                                return reasons ? `⚠️ ${reasons}` : '';
                                                            }
                                                        }
                                                    }
                                                },
                                                onClick: (_event: unknown, elements: ActiveDataPoint<'line'>[]) => {
                                                    if (elements.length > 0 && ids.length > 0) {
                                                        const index = elements[0].index;
                                                        const id = ids[index];
                                                        if (id && onPointClick) onPointClick(Number(id));
                                                    }
                                                },
                                                onHover: (event: unknown, elements: ActiveDataPoint<'line'>[]) => {
                                                    if (event?.native?.target) {
                                                        event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                                                    }
                                                }
                                            }}
                                        />
                                    </div>
                                </Card.Body>
                            </Card>
                        </Col>
                        <Col md={6}>
                            <Card className="h-100 shadow-sm">
                                <Card.Body>
                                    <h5 className="card-title text-center">R 全距管制圖</h5>
                                    <div style={{ height: '300px' }}>
                                        <Line
                                            data={chartData.rChart}
                                            options={{
                                                maintainAspectRatio: false,
                                                plugins: {
                                                    legend: {
                                                        display: true,
                                                        position: 'bottom',
                                                        labels: {
                                                            usePointStyle: true,
                                                            pointStyle: 'line',
                                                            font: { size: 10 }
                                                        }
                                                    },
                                                    tooltip: {
                                                        callbacks: {
                                                            afterLabel: (ctx: TooltipItem<'line'>) => {
                                                                if (ctx.datasetIndex !== 0) return '';
                                                                const reasons = getRViolationReasons(ctx.dataIndex);
                                                                return reasons ? `⚠️ ${reasons}` : '';
                                                            }
                                                        }
                                                    }
                                                },
                                                onClick: (_event: unknown, elements: ActiveDataPoint<'line'>[]) => {
                                                    if (elements.length > 0 && ids.length > 0) {
                                                        const index = elements[0].index;
                                                        const id = ids[index];
                                                        if (id && onPointClick) onPointClick(Number(id));
                                                    }
                                                },
                                                onHover: (event: unknown, elements: ActiveDataPoint<'line'>[]) => {
                                                    if (event?.native?.target) {
                                                        event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                                                    }
                                                }
                                            }}
                                        />
                                    </div>
                                </Card.Body>
                            </Card>
                        </Col>
                    </Row>

                    {/* Charts Row 2: Histogram */}
                    {histogramData && histogramData.bins.length > 1 && (
                        <Row className="mb-3">
                            <Col md={8} className="mx-auto">
                                <Card className="shadow-sm">
                                    <Card.Body>
                                        <h5 className="card-title text-center">📊 量測值分佈直方圖 + 常態分佈曲線</h5>
                                        <div style={{ height: '320px' }}>
                                            <Chart
                                                type="bar"
                                                data={{
                                                    labels: histogramData.bins.map((b: HistogramBin) => b.label),
                                                    datasets: [
                                                        {
                                                            type: 'bar' as const,
                                                            label: '頻次',
                                                            data: histogramData.bins.map((b: HistogramBin) => b.count),
                                                            backgroundColor: 'rgba(13, 110, 253, 0.5)',
                                                            borderColor: '#0d6efd',
                                                            borderWidth: 1,
                                                            order: 2,
                                                            barPercentage: 1.0,
                                                            categoryPercentage: 1.0
                                                        },
                                                        {
                                                            type: 'line' as const,
                                                            label: '常態分佈',
                                                            data: histogramData.normalCurve,
                                                            borderColor: '#dc3545',
                                                            borderWidth: 2,
                                                            pointRadius: 0,
                                                            tension: 0.4,
                                                            order: 1
                                                        },
                                                        // USL vertical indicator
                                                        ...(histogramData.usl != null ? [{
                                                            type: 'line' as const,
                                                            label: `USL (${histogramData.usl.toFixed(2)})`,
                                                            data: histogramData.bins.map((b: HistogramBin) => {
                                                                const dist = Math.abs(b.midpoint - histogramData.usl);
                                                                const binW = histogramData.bins.length > 1
                                                                    ? histogramData.bins[1].midpoint - histogramData.bins[0].midpoint
                                                                    : 1;
                                                                return dist < binW / 2 ? Math.max(...histogramData.bins.map((bb: HistogramBin) => bb.count)) * 1.1 : null;
                                                            }),
                                                            borderColor: '#e83e8c',
                                                            borderDash: [5, 5],
                                                            borderWidth: 2,
                                                            pointRadius: 0,
                                                            spanGaps: false,
                                                            order: 0
                                                        }] : []),
                                                        // LSL vertical indicator
                                                        ...(histogramData.lsl != null ? [{
                                                            type: 'line' as const,
                                                            label: `LSL (${histogramData.lsl.toFixed(2)})`,
                                                            data: histogramData.bins.map((b: HistogramBin) => {
                                                                const dist = Math.abs(b.midpoint - histogramData.lsl);
                                                                const binW = histogramData.bins.length > 1
                                                                    ? histogramData.bins[1].midpoint - histogramData.bins[0].midpoint
                                                                    : 1;
                                                                return dist < binW / 2 ? Math.max(...histogramData.bins.map((bb: HistogramBin) => bb.count)) * 1.1 : null;
                                                            }),
                                                            borderColor: '#e83e8c',
                                                            borderDash: [5, 5],
                                                            borderWidth: 2,
                                                            pointRadius: 0,
                                                            spanGaps: false,
                                                            order: 0
                                                        }] : [])
                                                    ] as ChartData<'bar'>['datasets']
                                                }}
                                                options={{
                                                    maintainAspectRatio: false,
                                                    plugins: {
                                                        legend: {
                                                            display: true,
                                                            position: 'bottom',
                                                            labels: { usePointStyle: true, font: { size: 10 } }
                                                        },
                                                        tooltip: {
                                                            callbacks: {
                                                                title: (items: TooltipItem<'bar'>[]) => items[0]?.label || '',
                                                                label: (ctx: TooltipItem<'bar'>) => {
                                                                    if (ctx.dataset.label === '頻次') return `數量: ${ctx.raw}`;
                                                                    if (ctx.dataset.label === '常態分佈') return `期望值: ${ctx.raw?.toFixed(1)}`;
                                                                    return ctx.dataset.label || '';
                                                                }
                                                            }
                                                        }
                                                    },
                                                    scales: {
                                                        x: { title: { display: true, text: '量測值區間' } },
                                                        y: { title: { display: true, text: '頻次' }, beginAtZero: true }
                                                    }
                                                }}
                                            />
                                        </div>
                                        <div className="text-center text-muted small mt-2">
                                            平均值: {histogramData.allMean.toFixed(3)} | 標準差: {histogramData.allStdDev.toFixed(3)} | 樣本數: {statsData?.all_values?.length ?? 0}
                                        </div>
                                    </Card.Body>
                                </Card>
                            </Col>
                        </Row>
                    )}

                    {/* Cpk Monthly Trend Chart */}
                    {cpkTrend && cpkTrend.length >= 2 && (
                        <Row className="mb-3">
                            <Col md={8} className="mx-auto">
                                <Card className="shadow-sm">
                                    <Card.Body>
                                        <h5 className="card-title text-center">📈 Cpk 月趨勢圖</h5>
                                        <div style={{ height: '280px' }}>
                                            <Line
                                                data={{
                                                    labels: cpkTrend.map((t: any) => t.month),
                                                    datasets: [
                                                        {
                                                            label: 'Cpk',
                                                            data: cpkTrend.map((t: any) => t.cpk),
                                                            borderColor: '#0d6efd',
                                                            backgroundColor: cpkTrend.map((t: any) => {
                                                                if (t.cpk >= 1.33) return '#28a745';
                                                                if (t.cpk >= 1.0) return '#ffc107';
                                                                return '#dc3545';
                                                            }),
                                                            pointRadius: 6,
                                                            pointBorderWidth: 2,
                                                            pointBorderColor: '#fff',
                                                            tension: 0.2,
                                                            fill: false
                                                        },
                                                        {
                                                            label: '目標線 (1.33)',
                                                            data: Array(cpkTrend.length).fill(1.33),
                                                            borderColor: '#28a745',
                                                            borderDash: [8, 4],
                                                            borderWidth: 1,
                                                            pointRadius: 0,
                                                            fill: false
                                                        },
                                                        {
                                                            label: '警戒線 (1.0)',
                                                            data: Array(cpkTrend.length).fill(1.0),
                                                            borderColor: '#dc3545',
                                                            borderDash: [5, 5],
                                                            borderWidth: 1,
                                                            pointRadius: 0,
                                                            fill: false
                                                        }
                                                    ]
                                                }}
                                                options={{
                                                    maintainAspectRatio: false,
                                                    plugins: {
                                                        legend: {
                                                            display: true,
                                                            position: 'bottom',
                                                            labels: { usePointStyle: true, font: { size: 10 } }
                                                        },
                                                        tooltip: {
                                                            callbacks: {
                                                                afterLabel: (ctx: any) => {
                                                                    if (ctx.datasetIndex !== 0) return '';
                                                                    const t = cpkTrend[ctx.dataIndex];
                                                                    return t ? `樣本數: ${t.count}` : '';
                                                                }
                                                            }
                                                        }
                                                    },
                                                    scales: {
                                                        y: {
                                                            title: { display: true, text: 'Cpk' },
                                                            beginAtZero: true
                                                        }
                                                    }
                                                }}
                                            />
                                        </div>
                                    </Card.Body>
                                </Card>
                            </Col>
                        </Row>
                    )}

                    {/* Legend */}
                    <div className="d-flex justify-content-center gap-4 mt-3 flex-wrap">
                        <div className="d-flex align-items-center">
                            <span style={{ width: 16, height: 16, borderRadius: '50%', backgroundColor: '#0d6efd', marginRight: 8, display: 'inline-block' }}></span>
                            <span className="small">正常</span>
                        </div>
                        <div className="d-flex align-items-center">
                            <span style={{ width: 16, height: 16, borderRadius: '50%', backgroundColor: '#fd7e14', marginRight: 8, display: 'inline-block', border: '2px solid #fff' }}></span>
                            <span className="small">趨勢異常 (WECO)</span>
                        </div>
                        <div className="d-flex align-items-center">
                            <span style={{ width: 16, height: 16, borderRadius: '50%', backgroundColor: '#dc3545', marginRight: 8, display: 'inline-block', border: '2px solid #fff' }}></span>
                            <span className="small">超出管制界限</span>
                        </div>
                        <div className="d-flex align-items-center">
                            <span style={{ width: 16, height: 2, backgroundColor: '#20c997', marginRight: 8, display: 'inline-block', borderTop: '2px dashed #20c997' }}></span>
                            <span className="small">移動平均 (MA5)</span>
                        </div>
                        {processCapability?.available && (
                            <div className="d-flex align-items-center">
                                <span style={{ width: 16, height: 2, backgroundColor: '#e83e8c', marginRight: 8, display: 'inline-block', borderTop: '2px dashed #e83e8c' }}></span>
                                <span className="small">USL/LSL 規格限</span>
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
};

export default ShippingCharts;
