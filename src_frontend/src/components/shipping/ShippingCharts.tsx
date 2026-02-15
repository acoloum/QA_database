import { useEffect, useState } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import api from '../../services/api';
import { analyzeWECO } from '../../utils/spcAnalysis';
import { Alert, Card, Col, Row, Form } from 'react-bootstrap';

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
    const [chartData, setChartData] = useState<any>(null);
    const [chartIds, setChartIds] = useState<string[]>([]);
    const [analysis, setAnalysis] = useState<any>(null);
    const [statsSummary, setStatsSummary] = useState<any>(null);
    const [showWeco, setShowWeco] = useState(false);

    useEffect(() => {
        const fetchStats = async () => {
            if (!vendor && !material && !spec) {
                setChartData(null);
                return;
            }

            try {
                const res = await api.get(`/stats?field=${statsField}&vendor=${vendor}&material=${material}&spec=${spec}&start_date=${startDate}&end_date=${endDate}`);
                const data = res.data;
                setChartIds(data.ids || []);

                if (!data.avgs || data.avgs.length === 0) {
                    setChartData(null);
                    return;
                }

                // Analyze WECO
                const weco = analyzeWECO(data.avgs, data.x_cl, data.x_ucl, data.x_lcl, data.labels);
                setAnalysis(weco);

                // Calculate Summary Stats locally or use backend if available (backend doesn't seem to return summary stats object based on shipping.html, it calculates in JS)
                // Let's calculate locally like shipping.html
                const count = data.avgs.length;
                const mean = data.avgs.reduce((a: number, b: number) => a + b, 0) / count;
                const sorted = [...data.avgs].sort((a: number, b: number) => a - b);
                const min = sorted[0];
                const max = sorted[count - 1];
                const range = max - min;
                // Standard Deviation
                const variance = data.avgs.reduce((acc: number, val: number) => acc + Math.pow(val - mean, 2), 0) / count;
                const stdDev = Math.sqrt(variance);

                setStatsSummary({
                    count,
                    mean: mean.toFixed(3),
                    min: min.toFixed(3),
                    max: max.toFixed(3),
                    range: range.toFixed(3),
                    stdDev: stdDev.toFixed(3),
                    violations: weco.violations.length
                });

                // Charts Configuration
                const pointColors = weco.statuses.map((s) => s === "violation" ? '#ff0000' : '#3498db');
                const pointRadius = weco.statuses.map((s) => s === "violation" ? 6 : 3);

                setChartData({
                    xBar: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: '平均值',
                                data: data.avgs,
                                borderColor: '#3498db',
                                backgroundColor: pointColors,
                                pointRadius: pointRadius,
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
                                borderColor: '#f39c12',
                                backgroundColor: '#f39c12',
                                tension: 0.1
                            },
                            { label: 'UCL', data: Array(count).fill(data.r_ucl), borderColor: 'red', borderDash: [5, 5], pointRadius: 0 }
                        ]
                    }
                });

            } catch (e) {
                console.error('Error loading stats:', e);
                setChartData(null);
            }
        };

        fetchStats();
    }, [statsField, vendor, material, spec, startDate, endDate]);

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
                                    data={chartData.xBar}
                                    options={{
                                        maintainAspectRatio: false,
                                        plugins: { legend: { display: false } },
                                        onClick: (_event, elements) => {
                                            if (elements.length > 0 && chartIds.length > 0) {
                                                const index = elements[0].index;
                                                const id = chartIds[index];
                                                if (id && onPointClick) onPointClick(Number(id));
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
                                    data={chartData.rChart}
                                    options={{
                                        maintainAspectRatio: false,
                                        plugins: { legend: { display: false } },
                                        onClick: (_event, elements) => {
                                            if (elements.length > 0 && chartIds.length > 0) {
                                                const index = elements[0].index;
                                                const id = chartIds[index];
                                                if (id && onPointClick) onPointClick(Number(id));
                                            }
                                        }
                                    }}
                                />
                            </div>
                        </Card.Body>
                    </Card>
                </Col>
            </Row>
        </div>
    );
};

export default ShippingCharts;
