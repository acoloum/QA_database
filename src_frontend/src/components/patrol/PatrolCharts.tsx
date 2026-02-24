
import { useState, useMemo } from 'react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';
import { analyzeWECO } from '../../utils/spcAnalysis';
import { Alert, Card, Col, Row, Form, Collapse } from 'react-bootstrap';
import { usePatrolStats } from '../../hooks/usePatrol';

// Register ChartJS components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

interface PatrolChartsProps {
    machine: string;
    operator: string;
    material: string;
    spec: string;
    startDate: string;
    endDate: string;
    onEditPoint?: (id: number) => void;
}

const ITEMS = [
    { label: "外徑", key: "外徑" },
    { label: "內徑", key: "內徑" },
    { label: "厚度", key: "厚度" }
];

const POSITIONS = ['前段', '中段', '後段'];

const PatrolCharts = ({ machine, operator, material, spec, startDate, endDate, onEditPoint }: PatrolChartsProps) => {
    const [statsItem, setStatsItem] = useState('外徑');
    const [statsPos, setStatsPos] = useState('前段');
    const [showViolations, setShowViolations] = useState(true);

    const { data: statsData } = usePatrolStats({
        item: statsItem,
        pos: statsPos,
        m_id: machine,
        op_id: operator,
        mat: material,
        spec: spec,
        s_date: startDate,
        e_date: endDate
    });

    const { chartData, analysis, statsSummary } = useMemo(() => {
        if (!statsData || !statsData.labels || statsData.labels.length === 0) {
            return { chartData: null, analysis: null, statsSummary: null };
        }

        const data = statsData;
        const count = data.avgs.length;

        // Analyze WECO
        const weco = analyzeWECO(data.avgs, data.x_cl, data.x_ucl, data.x_lcl, data.labels);

        // Stats Summary
        const mean = data.avgs.reduce((a: number, b: number) => a + b, 0) / count;
        const sorted = [...data.avgs].sort((a: number, b: number) => a - b);
        const min = sorted[0];
        const max = sorted[count - 1];
        const range = max - min;
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
        const pointColors = weco.statuses.map((s) => s === "violation" ? '#ff0000' : '#0d6efd');
        const pointRadius = weco.statuses.map((s) => s === "violation" ? 6 : 3);

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

        return { chartData: cData, analysis: weco, statsSummary: summary };

    }, [statsData]);

    if (!chartData) return null;

    return (
        <div className="mt-4">
            <div className="d-flex align-items-center mb-3">
                <h4 className="mb-0 me-3 text-danger"><i className="bi bi-graph-up"></i> SPC 統計圖表</h4>
                <Form.Select
                    className="me-2"
                    style={{ width: 'auto' }}
                    value={statsPos}
                    onChange={e => setStatsPos(e.target.value)}
                >
                    <option value="">全段</option>
                    {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </Form.Select>
                <Form.Select
                    style={{ width: 'auto' }}
                    value={statsItem}
                    onChange={e => setStatsItem(e.target.value)}
                >
                    {ITEMS.map(i => <option key={i.key} value={i.key}>{i.label}</option>)}
                </Form.Select>
            </div>

            {/* Alarm Panel */}
            {analysis && analysis.violations.length > 0 && (
                <Alert variant="danger">
                    <div
                        className="d-flex justify-content-between align-items-center"
                        onClick={() => setShowViolations(!showViolations)}
                        style={{ cursor: 'pointer' }}
                    >
                        <Alert.Heading className="mb-0" style={{ fontSize: '1.1rem' }}>
                            🚨 偵測到製程異常數據點 (WECO Rules) {showViolations ? '' : `(${analysis.violations.length})`}
                        </Alert.Heading>
                        <i className={`bi bi-chevron-${showViolations ? 'up' : 'down'}`} style={{ fontSize: '1.2rem' }}></i>
                    </div>
                    <Collapse in={showViolations}>
                        <div>
                            <hr />
                            <ul className="mb-0">
                                {analysis.violations.map((v: any, idx: number) => (
                                    <li key={idx}><strong>{v.label}</strong>: {v.reasons.join(', ')}</li>
                                ))}
                            </ul>
                        </div>
                    </Collapse>
                </Alert>
            )}

            {/* Stats Summary */}
            {statsSummary && (
                <Card className="mb-4 border-0 shadow-sm bg-stats-gradient text-white">
                    <Card.Body>
                        <Row className="text-center">
                            <Col>
                                <div className="small opacity-75">樣本數</div>
                                <div className="h4 fw-bold">{statsSummary.count}</div>
                            </Col>
                            <Col>
                                <div className="small opacity-75">平均值</div>
                                <div className="h4 fw-bold">{statsSummary.mean}</div>
                            </Col>
                            <Col>
                                <div className="small opacity-75">標準差</div>
                                <div className="h4 fw-bold">{statsSummary.stdDev}</div>
                            </Col>
                            <Col>
                                <div className="small opacity-75">最小值</div>
                                <div className="h4 fw-bold">{statsSummary.min}</div>
                            </Col>
                            <Col>
                                <div className="small opacity-75">最大值</div>
                                <div className="h4 fw-bold">{statsSummary.max}</div>
                            </Col>
                            <Col>
                                <div className="small opacity-75">異常點</div>
                                <div className="h4 fw-bold">{statsSummary.violations}</div>
                            </Col>
                        </Row>
                    </Card.Body>
                </Card>
            )}

            <Row>
                <Col md={6}>
                    <Card className="h-100 shadow-sm border-primary">
                        <Card.Header className="bg-primary text-white">X-bar 平均值管制圖</Card.Header>
                        <Card.Body>
                            <div style={{ height: '300px' }}>
                                <Line
                                    data={chartData.xBar}
                                    options={{ 
                                        maintainAspectRatio: false, 
                                        plugins: { legend: { display: false } },
                                        onClick: (_evt, elements) => {
                                            if (elements.length > 0 && onEditPoint) {
                                                const idx = elements[0].index;
                                                const label = chartData.xBar.labels[idx];
                                                const match = label.match(/#(\d+)/);
                                                if (match) {
                                                    onEditPoint(parseInt(match[1], 10));
                                                }
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
                    <Card className="h-100 shadow-sm border-purple" style={{ borderColor: '#6f42c1' }}>
                        <Card.Header className="text-white" style={{ backgroundColor: '#6f42c1' }}>R 全距管制圖</Card.Header>
                        <Card.Body>
                            <div style={{ height: '300px' }}>
                                <Line
                                    data={chartData.rChart}
                                    options={{ 
                                        maintainAspectRatio: false, 
                                        plugins: { legend: { display: false } },
                                        onClick: (_evt, elements) => {
                                            if (elements.length > 0 && onEditPoint) {
                                                const idx = elements[0].index;
                                                const label = chartData.rChart.labels[idx];
                                                const match = label.match(/#(\d+)/);
                                                if (match) {
                                                    onEditPoint(parseInt(match[1], 10));
                                                }
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
        </div>
    );
};

export default PatrolCharts;
