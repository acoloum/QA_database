
import { useMemo } from 'react';
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
import { Line } from 'react-chartjs-2';
import { getClickedPointId, setChartPointCursor, shouldShowControlLegendLabel } from '../../utils/spcChartOptions';
import { buildSpcChartModel } from '../../utils/spcChartModel';
import CpkTrendChart from '../spc/CpkTrendChart';
import HistogramDistributionChart from '../spc/HistogramDistributionChart';
import ProcessCapabilityCard from './ProcessCapabilityCard';
import WecoViolationAlert from './WecoViolationAlert';
import { Badge, Button, Card, Col, Row, Form } from 'react-bootstrap';
import { useExportPatrolSpcReport, usePatrolStats } from '../../hooks/usePatrol';
import type { SpcViolation, SpcChartData } from '../../types';
import type { TooltipItem, ActiveDataPoint } from 'chart.js';

// 註冊 ChartJS 元件
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler);

interface PatrolChartsProps {
    machine: string;
    operator: string;
    customer: string;
    material: string;
    spec: string;
    startDate: string;
    endDate: string;
    onEditPoint?: (id: number) => void;
    statsItem: string;
    statsPos: string;
    onItemChange: (val: string) => void;
    onPosChange: (val: string) => void;
}

const ITEMS = [
    { label: "外徑", key: "外徑" },
    { label: "內徑", key: "內徑" },
    { label: "厚度", key: "厚度" }
];

const POSITIONS = ['前段', '中段', '後段'];

const PatrolCharts = ({ machine, operator, customer, material, spec, startDate, endDate, onEditPoint, statsItem, statsPos, onItemChange, onPosChange }: PatrolChartsProps) => {
    const exportSpcReport = useExportPatrolSpcReport();

    // 匯出 SPC 報告（含原始數據 + SPC 統計與圖表）
    const handleExportSpc = () => {
        exportSpcReport.mutate({
            s_date: startDate,
            e_date: endDate,
            m_id: machine,
            op_id: operator,
            cust_id: customer,
            mat: material,
            spec,
            item: statsItem,
            pos: statsPos
        });
    };

    const { data: statsData } = usePatrolStats({
        item: statsItem,
        pos: statsPos,
        m_id: machine,
        op_id: operator,
        cust_id: customer,
        mat: material,
        spec: spec,
        s_date: startDate,
        e_date: endDate
    });

    const { chartData, ids, analysis, rAnalysis, statsSummary, processCapability, histogramData, distributionStats, cpkTrend } = useMemo(() => buildSpcChartModel(statsData as SpcChartData | null | undefined), [statsData]);

    // tooltip 顯示違規原因
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

    // 合併 X-bar 和 R 圖的違規
    const allViolations: SpcViolation[] = [
        ...(analysis?.violations || []),
        ...(rAnalysis?.violations || []).map((v: SpcViolation) => ({ ...v, label: `[R] ${v.label}` }))
    ];

    return (
        <div className="mt-4">
            <div className="d-flex align-items-center justify-content-between mb-3">
                <div className="d-flex align-items-center">
                    <h4 className="mb-0 me-3">SPC 監控與分析</h4>
                    <Form.Select
                        className="me-2"
                        style={{ width: 'auto' }}
                        value={statsPos}
                        onChange={e => onPosChange(e.target.value)}
                    >
                        <option value="">全段</option>
                        {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                    </Form.Select>
                    <Form.Select
                        style={{ width: 'auto' }}
                        value={statsItem}
                        onChange={e => onItemChange(e.target.value)}
                    >
                        {ITEMS.map(i => <option key={i.key} value={i.key}>{i.label}</option>)}
                    </Form.Select>
                </div>
                <Button variant="outline-success" onClick={handleExportSpc} disabled={exportSpcReport.isPending}>
                    <i className="bi bi-file-earmark-bar-graph"></i> {exportSpcReport.isPending ? '匯出中...' : '匯出 SPC 報告'}
                </Button>
            </div>

            {!chartData ? (
                <div className="text-center py-5 text-muted">
                    選擇的檢驗項目「<strong>{statsItem}</strong>」沒有足夠的數據來產生 SPC 圖表，請嘗試其他檢驗項目或區段。
                </div>
            ) : (
                <>
                    {/* 異常警告面板 */}
                    <WecoViolationAlert violations={allViolations} />

                    {/* 統計摘要 */}
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

                    {/* 常態性檢查 */}
                    {distributionStats && (
                        <Card className="mb-3" style={{
                            border: `2px solid ${distributionStats.normality === 'good' ? '#28a745' : distributionStats.normality === 'moderate' ? '#ffc107' : '#dc3545'}`,
                            backgroundColor: distributionStats.normality === 'good' ? '#f8fff8' : distributionStats.normality === 'moderate' ? '#fffef5' : '#fff8f8'
                        }}>
                            <Card.Body className="py-2">
                                <Row className="text-center align-items-center">
                                    <Col xs="auto">
                                        <strong>常態性檢查</strong>
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

                    {/* 製程能力指標卡 */}
                    <ProcessCapabilityCard processCapability={processCapability} statsItem={statsItem} />

                    {/* X-bar 和 R 管制圖 */}
                    <Row className="mb-3">
                        <Col md={6}>
                            <Card className="h-100 shadow-sm">
                                <Card.Body>
                                    <h5 className="card-title text-center">X&#x0304; 平均值管制圖</h5>
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
                                                            filter: item => shouldShowControlLegendLabel(item.text),
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
                                                                return reasons ? `\u26a0\ufe0f ${reasons}` : '';
                                                            }
                                                        }
                                                    }
                                                },
                                                onClick: (_event: unknown, elements: ActiveDataPoint[]) => {
                                                    const id = getClickedPointId(ids, elements);
                                                    if (id && onEditPoint) onEditPoint(id);
                                                },
                                                onHover: (event: unknown, elements: ActiveDataPoint[]) => {
                                                    setChartPointCursor(event, elements);
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
                                                                return reasons ? `\u26a0\ufe0f ${reasons}` : '';
                                                            }
                                                        }
                                                    }
                                                },
                                                onClick: (_event: unknown, elements: ActiveDataPoint[]) => {
                                                    const id = getClickedPointId(ids, elements);
                                                    if (id && onEditPoint) onEditPoint(id);
                                                },
                                                onHover: (event: unknown, elements: ActiveDataPoint[]) => {
                                                    setChartPointCursor(event, elements);
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
                                <HistogramDistributionChart
                                    histogramData={histogramData}
                                    sampleCount={statsData?.all_values?.length ?? 0}
                                />
                            </Col>
                        </Row>
                    )}
                    {/* Cpk Monthly Trend Chart */}
                    {cpkTrend && cpkTrend.length >= 2 && (
                        <Row className="mb-3">
                            <Col md={8} className="mx-auto">
                                <CpkTrendChart cpkTrend={cpkTrend} />
                            </Col>
                        </Row>
                    )}
                    {/* 圖例 */}
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

export default PatrolCharts;
