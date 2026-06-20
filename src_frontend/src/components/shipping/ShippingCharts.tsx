
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
import { buildSpcChartModel } from '../../utils/spcChartModel';
import CpkTrendChart from '../spc/CpkTrendChart';
import HistogramDistributionChart from '../spc/HistogramDistributionChart';
import ControlChartCard from '../patrol/ControlChartCard';
import ProcessCapabilityCard from '../patrol/ProcessCapabilityCard';
import WecoViolationAlert from '../patrol/WecoViolationAlert';
import type { SpcViolation, SpcChartData } from '../../types';
import { Badge, Button, Card, Col, Row, Form } from 'react-bootstrap';
import { useShippingStats, useExportSpcReport } from '../../hooks/useShipping';

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

const BASE_CHART_ITEMS = [
    { label: "外徑", key: "外徑" },
    { label: "內徑", key: "內徑" },
    { label: "真圓度", key: "真圓度" },
    { label: "厚度", key: "厚度" },
    { label: "同心度", key: "同心度" },
    { label: "長度", key: "長度" },
    { label: "硬度", key: "硬度" },
    { label: "真直度", key: "真直度" }
];

const ANTAI_VENDOR_NAME = "安泰";

const ShippingCharts = ({ vendor, material, spec, startDate, endDate, onPointClick }: ShippingChartsProps) => {
    const [statsField, setStatsField] = useState('外徑');

    // 安泰廠商：硬度改標示為洛氏硬度(HRB)，並新增韋伯氏硬度(HW)
    const isAntai = vendor.includes(ANTAI_VENDOR_NAME);
    const ITEMS = useMemo(() => {
        if (!isAntai) return BASE_CHART_ITEMS;
        return BASE_CHART_ITEMS.map(item =>
            item.key === '硬度' ? { ...item, label: '洛氏硬度(HRB)' } : item
        ).concat([{ label: '韋伯氏硬度(HW)', key: '韋伯氏硬度' }]);
    }, [isAntai]);

    const { data: statsData } = useShippingStats({
        field: statsField,
        vendor,
        material,
        spec,
        start_date: startDate,
        end_date: endDate
    });

    const exportSpcReport = useExportSpcReport();

    const { chartData, ids, analysis, rAnalysis, statsSummary, processCapability, histogramData, distributionStats, cpkTrend } = useMemo(() => buildSpcChartModel(statsData as SpcChartData | null | undefined), [statsData]);

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
                    <WecoViolationAlert violations={allViolations} />

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
                    <ProcessCapabilityCard processCapability={processCapability} statsItem={statsField} />

                    {/* Charts Row 1: X-bar and R */}
                    <Row className="mb-3">
                        <Col md={6}>
                            <ControlChartCard
                                title="X̄ 平均值管制圖"
                                data={chartData.xBar}
                                ids={ids}
                                getViolationReasons={getViolationReasons}
                                filterLegendLabels
                                onEditPoint={onPointClick}
                            />
                        </Col>
                        <Col md={6}>
                            <ControlChartCard
                                title="R 全距管制圖"
                                data={chartData.rChart}
                                ids={ids}
                                getViolationReasons={getRViolationReasons}
                                onEditPoint={onPointClick}
                            />
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
