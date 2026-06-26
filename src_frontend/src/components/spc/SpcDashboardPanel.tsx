import { Badge, Card, Col, Row } from 'react-bootstrap';

import type { SpcViolation } from '../../types';
import type { SpcChartModel } from '../../utils/spcChartModel';
import ControlChartCard from '../patrol/ControlChartCard';
import ProcessCapabilityCard from '../patrol/ProcessCapabilityCard';
import WecoViolationAlert from '../patrol/WecoViolationAlert';
import CpkTrendChart from './CpkTrendChart';
import HistogramDistributionChart from './HistogramDistributionChart';

interface SpcDashboardPanelProps {
  model: SpcChartModel;
  statsItem: string;
  emptyMessage: string;
  sampleCount?: number;
  xBarTitle?: string;
  rChartTitle?: string;
  onEditPoint?: (id: number) => void;
  filterXBarLegendLabels?: boolean;
}

const findViolationReasons = (
  violations: SpcViolation[] | undefined,
  labels: unknown[] | undefined,
  index: number,
): string => {
  const label = labels?.[index];
  const violation = violations?.find(item => item.label === label);
  return violation ? violation.reasons.join(', ') : '';
};

const SpcDashboardPanel = ({
  model,
  statsItem,
  emptyMessage,
  sampleCount = 0,
  xBarTitle = 'X̄ 平均值管制圖',
  rChartTitle = 'R 全距管制圖',
  onEditPoint,
  filterXBarLegendLabels = false,
}: SpcDashboardPanelProps) => {
  const {
    chartData,
    ids,
    analysis,
    rAnalysis,
    statsSummary,
    processCapability,
    histogramData,
    distributionStats,
    cpkTrend,
  } = model;

  if (!chartData) {
    return <div className="text-center py-5 text-muted">{emptyMessage}</div>;
  }

  const allViolations: SpcViolation[] = [
    ...(analysis?.violations || []),
    ...(rAnalysis?.violations || []).map(violation => ({ ...violation, label: `[R] ${violation.label}` })),
  ];

  return (
    <>
      <WecoViolationAlert violations={allViolations} />

      {statsSummary && (
        <Card className="mb-3 bg-light">
          <Card.Body>
            <Row className="text-center">
              <Col><strong>樣本數</strong><div className="h4">{statsSummary.count}</div></Col>
              <Col><strong>平均值</strong><div className="h4">{statsSummary.mean}</div></Col>
              <Col>
                <strong>標準差</strong>
                <div className={`h4 ${Number(statsSummary.cv) > 5 ? 'text-danger' : 'text-success'}`}>
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

      {distributionStats && (
        <Card className="mb-3" style={{
          border: `2px solid ${distributionStats.normality === 'good' ? '#28a745' : distributionStats.normality === 'moderate' ? '#ffc107' : '#dc3545'}`,
          backgroundColor: distributionStats.normality === 'good' ? '#f8fff8' : distributionStats.normality === 'moderate' ? '#fffef5' : '#fff8f8',
        }}>
          <Card.Body className="py-2">
            <Row className="text-center align-items-center">
              <Col xs="auto"><strong>常態性檢查</strong></Col>
              <Col><span className="text-muted small me-1">偏態</span><strong>{distributionStats.skewness}</strong></Col>
              <Col><span className="text-muted small me-1">峰態</span><strong>{distributionStats.kurtosis}</strong></Col>
              <Col xs="auto">
                <Badge bg={distributionStats.normality === 'good' ? 'success' : distributionStats.normality === 'moderate' ? 'warning' : 'danger'}>
                  {distributionStats.normality_label}
                </Badge>
              </Col>
            </Row>
          </Card.Body>
        </Card>
      )}

      <ProcessCapabilityCard processCapability={processCapability} statsItem={statsItem} />

      <Row className="mb-3">
        <Col md={6}>
          <ControlChartCard
            title={xBarTitle}
            data={chartData.xBar}
            ids={ids}
            getViolationReasons={index => findViolationReasons(analysis?.violations, chartData.xBar.labels, index)}
            filterLegendLabels={filterXBarLegendLabels}
            onEditPoint={onEditPoint}
          />
        </Col>
        <Col md={6}>
          <ControlChartCard
            title={rChartTitle}
            data={chartData.rChart}
            ids={ids}
            getViolationReasons={index => findViolationReasons(rAnalysis?.violations, chartData.rChart.labels, index)}
            onEditPoint={onEditPoint}
          />
        </Col>
      </Row>

      {histogramData && histogramData.bins.length > 1 && (
        <Row className="mb-3">
          <Col md={8} className="mx-auto">
            <HistogramDistributionChart histogramData={histogramData} sampleCount={sampleCount} />
          </Col>
        </Row>
      )}

      {cpkTrend && cpkTrend.length >= 2 && (
        <Row className="mb-3">
          <Col md={8} className="mx-auto">
            <CpkTrendChart cpkTrend={cpkTrend} />
          </Col>
        </Row>
      )}

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
  );
};

export default SpcDashboardPanel;
