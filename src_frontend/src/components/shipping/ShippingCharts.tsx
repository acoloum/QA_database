
import { useState, useMemo } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { analyzeWECO } from '../../utils/spcAnalysis';
import { Alert, Card, Col, Row, Form } from 'react-bootstrap';
import { useShippingStats } from '../../hooks/useShipping';

// Register ChartJS components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

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

    const { chartData, ids, analysis, statsSummary } = useMemo(() => {
        if (!statsData || !statsData.avgs || statsData.avgs.length === 0) {
            return { chartData: null, ids: [], analysis: null, statsSummary: null };
        }

        const data = statsData;
        const ids = data.ids || [];
        const count = data.avgs.length;

        // Analyze WECO
        const weco = analyzeWECO(data.avgs, data.x_cl, data.x_ucl, data.x_lcl, data.labels);

        // Calculate Summary Stats locally
        const mean = data.avgs.reduce((a: number, b: number) => a + b, 0) / count;
        const sorted = [...data.avgs].sort((a: number, b: number) => a - b);
        const min = sorted[0];
        const max = sorted[count - 1];
        const range = max - min;
        // Standard Deviation
        const variance = data.avgs.reduce((acc: number, val: number) => acc + Math.pow(val - mean, 2), 0) / count;
        const stdDev = Math.sqrt(variance);

        const summary = {
            count,
            mean: mean.toFixed(3),
            min: min.toFixed(3),
            max: max.toFixed(3),
            range: range.toFixed(3),
            stdDev: stdDev.toFixed(3),
            violations: weco.violations.length
        };

        // Charts Configuration
        // Determine if violation is UCL/LCL (more severe) or pattern-based
        const pointColors = data.avgs.map((val, i) => {
            // Check for UCL/LCL violation (Rule 1) - most severe
            if (val > data.x_ucl || val < data.x_lcl) {
                return '#dc3545'; // Red - UCL/LCL violation
            }
            // Check for pattern violations
            if (weco.statuses[i] === 'violation') {
                return '#fd7e14'; // Orange - pattern violation
            }
            return '#0d6efd'; // Blue - normal
        });

        const pointRadius = data.avgs.map((val, i) => {
            if (weco.statuses[i] === 'violation') {
                return 8; // Larger for violations
            }
            return 4;
        });

        const pointBorderColor = data.avgs.map((val, i) => {
            if (weco.statuses[i] === 'violation') {
                return '#fff'; // White border for violations
            }
            return '#0d6efd';
        });

        const cData = {
            xBar: {
                labels: data.labels,
                datasets: [
                    {
                        label: '平均值',
                        data: data.avgs,
                        borderColor: '#0d6efd',
                        backgroundColor: pointColors,
                        pointRadius: pointRadius,
                        pointBorderColor: pointBorderColor,
                        pointBorderWidth: 2,
                        tension: 0.1
                    },
                    { label: 'UCL', data: Array(count).fill(data.x_ucl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0 },
                    { label: 'CL', data: Array(count).fill(data.x_cl), borderColor: 'green', pointRadius: 0 },
                    { label: 'LCL', data: Array(count).fill(data.x_lcl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0 }
                ]
            },
            rChart: {
                labels: data.labels,
                datasets: [
                    {
                        label: '全距 R',
                        data: data.ranges,
                        borderColor: '#6f42c1',
                        backgroundColor: '#6f42c1',
                        tension: 0.1
                    },
                    { label: 'UCL', data: Array(count).fill(data.r_ucl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0 }
                ]
            }
        };

        return { chartData: cData, ids, analysis: weco, statsSummary: summary };

    }, [statsData]);

    // Helper to get violation reasons for tooltip
    const getViolationReasons = (idx: number): string => {
        if (!analysis || !analysis.violations) return '';
        const label = chartData?.xBar?.labels?.[idx];
        const violation = analysis.violations.find(v => v.label === label);
        return violation ? violation.reasons.join(', ') : '';
    };

    if (!chartData) return <div className="text-center py-5 text-muted">請選擇廠商、材質與規格以檢視 SPC 圖表。</div>;

    return (
        <div className="mt-4">
            <div className="d-flex align-items-center mb-3">
                <h4 className="mb-0 me-3">📊 SPC 監控與分析</h4>
                <Form.Select
                    style={{ width: 'auto' }}
                    value={statsField}
                    onChange={e => setStatsField(e.target.value)}
                >
                    {ITEMS.map(i => <option key={i.key} value={i.key}>{i.label}</option>)}
                </Form.Select>
            </div>

            {/* Alarm Panel */}
            {analysis && analysis.violations.length > 0 && (
                <Alert variant="danger">
                    <div
                        className="d-flex justify-content-between align-items-center"
                        style={{ cursor: 'pointer' }}
                        onClick={() => setShowWeco(!showWeco)}
                    >
                        <Alert.Heading className="mb-0" style={{ fontSize: '1rem' }}>
                            🚨 偵測到 {analysis.violations.length} 個製程異常數據點 (WECO Rules) - 點擊展開/收合
                        </Alert.Heading>
                        <i className={`bi bi-chevron-${showWeco ? 'up' : 'down'}`}></i>
                    </div>
                    {showWeco && (
                        <ul className="mb-0 mt-3">
                            {analysis.violations.map((v: any, idx: number) => (
                                <li key={idx}><strong>{v.label}</strong>: {v.reasons.join(', ')}</li>
                            ))}
                        </ul>
                    )}
                </Alert>
            )}

            {/* Stats Summary */}
            {statsSummary && (
                <Card className="mb-4 bg-light">
                    <Card.Body>
                        <Row className="text-center">
                            <Col><strong>樣本數</strong><div className="h4">{statsSummary.count}</div></Col>
                            <Col><strong>平均值</strong><div className="h4">{statsSummary.mean}</div></Col>
                            <Col><strong>標準差</strong><div className={`h4 ${parseFloat(statsSummary.stdDev) > 0.1 ? 'text-danger' : 'text-success'}`}>{statsSummary.stdDev}</div></Col>
                            <Col><strong>最小值</strong><div className="h4">{statsSummary.min}</div></Col>
                            <Col><strong>最大值</strong><div className="h4">{statsSummary.max}</div></Col>
                            <Col><strong>異常點</strong><div className={`h4 ${statsSummary.violations > 0 ? 'text-danger' : 'text-success'}`}>{statsSummary.violations}</div></Col>
                        </Row>
                    </Card.Body>
                </Card>
            )}

            <Row>
                <Col md={6}>
                    <Card className="h-100 shadow-sm">
                        <Card.Body>
                            <h5 className="card-title text-center">X-bar 平均值管制圖</h5>
                            <div style={{ height: '300px' }}>
                                <Line
                                    data={chartData.xBar}
                                    options={{ 
                                        maintainAspectRatio: false,
                                        plugins: { 
                                            legend: { display: false },
                                            tooltip: {
                                                callbacks: {
                                                    afterLabel: (ctx) => {
                                                        const reasons = getViolationReasons(ctx.dataIndex);
                                                        return reasons ? `⚠️ ${reasons}` : '';
                                                    }
                                                }
                                            }
                                        },
                                        onClick: (_event, elements) => {
                                            if (elements.length > 0 && ids.length > 0) {
                                                const index = elements[0].index;
                                                const id = ids[index];
                                                if (id && onPointClick) onPointClick(Number(id));
                                            }
                                        },
                                        onHover: (event, elements) => {
                                            event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
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
                                        plugins: { legend: { display: false } },
                                        onClick: (_event, elements) => {
                                            if (elements.length > 0 && ids.length > 0) {
                                                const index = elements[0].index;
                                                const id = ids[index];
                                                if (id && onPointClick) onPointClick(Number(id));
                                            }
                                        },
                                        onHover: (event, elements) => {
                                            event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                                        }
                                    }}
                                />
                            </div>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>

            {/* Legend */}
            <div className="d-flex justify-content-center gap-4 mt-3">
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
            </div>
        </div>
    );
};

export default ShippingCharts;
