import type { ReactNode } from 'react';
import { Button, Col, Form, Nav, Row } from 'react-bootstrap';

import TusChart from '../../components/pyrometry/TusChart';
import TusDataTable from '../../components/pyrometry/TusDataTable';
import type { SatPoint, SatReading } from '../../types';
import ChartRangeControls from './ChartRangeControls';
import { resolvePyrometryChartSettings } from './pyrometryChartSettings';
import { parseActiveZone, type ChartData } from './pyrometryFormUtils';
import SatZoneTab from './SatZoneTab';
import { evaluateSatPoint } from './satEvaluation';

interface Props {
  satPoints: SatPoint[];
  activeZone: number;
  setpoint: string;
  tolerance: string;
  satChartData: ChartData | null;
  satRangeStart: number;
  satRangeEnd: number;
  satTimeLabels: string[];
  showSatDetail: boolean;
  furnaceSection: ReactNode;
  onSatFileUpload: (file: File) => void;
  onFurnaceFileUpload: (file: File) => void;
  onSatRangeStartChange: (value: number) => void;
  onSatRangeEndChange: (value: number) => void;
  onApplyRangeSat: () => void;
  onToggleSatDetail: () => void;
  onActiveZoneChange: (value: number) => void;
  onUpdateSatField: (index: number, key: keyof SatPoint, value: string) => void;
  onUpdateSatReading: (index: number, readingIndex: number, key: keyof SatReading, value: string) => void;
  onAddSatReading: (index: number) => void;
  onRemoveSatReading: (index: number, readingIndex: number) => void;
  onApplyCorrections: () => void;
  onToggleExclude: (index: number, checked: boolean) => void;
  onReasonChange: (index: number, value: string) => void;
}

const SatSection = ({
  satPoints,
  activeZone,
  setpoint,
  tolerance,
  satChartData,
  satRangeStart,
  satRangeEnd,
  satTimeLabels,
  showSatDetail,
  furnaceSection,
  onSatFileUpload,
  onFurnaceFileUpload,
  onSatRangeStartChange,
  onSatRangeEndChange,
  onApplyRangeSat,
  onToggleSatDetail,
  onActiveZoneChange,
  onUpdateSatField,
  onUpdateSatReading,
  onAddSatReading,
  onRemoveSatReading,
  onApplyCorrections,
  onToggleExclude,
  onReasonChange,
}: Props) => {
  const { setpointValue, toleranceValue } = resolvePyrometryChartSettings({ setpoint, tolerance });

  return (
    <>
    <Row className="g-2 mb-3">
      <Col md={6}>
        <Form.Label>SAT 儀器詳細資料（CSV/Excel，選配）</Form.Label>
        <input
          className="form-control form-control-sm"
          type="file"
          accept=".csv,.xlsx,.xls"
          aria-label="SAT 儀器詳細資料"
          onChange={event => {
            const file = event.target.files?.[0];
            if (file) onSatFileUpload(file);
          }}
        />
      </Col>
      <Col md={6}>
        <Form.Label>爐體記錄數據（對照，選配）</Form.Label>
        <input
          className="form-control form-control-sm"
          type="file"
          accept=".csv,.xlsx,.xls"
          aria-label="爐體記錄數據"
          onChange={event => {
            const file = event.target.files?.[0];
            if (file) onFurnaceFileUpload(file);
          }}
        />
      </Col>

      {satChartData && (
        <>
          <Col md={12}>
            <TusChart
              時間={satChartData.時間}
              數值={satChartData.數值}
              設定溫度={setpointValue}
              公差={toleranceValue}
              startIdx={satRangeStart}
              endIdx={satRangeEnd}
              標題="SAT 儀器溫度曲線"
            />
          </Col>
          <Col md={12}>
            <ChartRangeControls
              label="SAT 恆溫穩定期"
              start={satRangeStart}
              end={satRangeEnd}
              timeLabels={satTimeLabels}
              applyLabel="套用並回填讀值"
              onStartChange={onSatRangeStartChange}
              onEndChange={onSatRangeEndChange}
              onApply={onApplyRangeSat}
            />
          </Col>
          <Col md={12}>
            <div className="d-flex align-items-center gap-2 mb-1">
              <Button size="sm" variant="outline-secondary" onClick={onToggleSatDetail}>
                {showSatDetail ? '隱藏 SAT 詳細數據表' : '顯示 SAT 詳細數據表'}
              </Button>
            </div>
            {showSatDetail && (
              <TusDataTable
                時間={satChartData.時間}
                數值={satChartData.數值}
                設定溫度={setpointValue}
                公差={toleranceValue}
                穩定開始={satRangeStart}
                穩定結束={satRangeEnd}
              />
            )}
          </Col>
        </>
      )}

      {furnaceSection}
    </Row>

    {satPoints.length > 0 && (
      <>
        <div className="d-flex justify-content-between align-items-center mb-2">
          <h6 className="mb-0">SAT 量測點明細</h6>
          <Button size="sm" variant="outline-secondary" onClick={onApplyCorrections}>
            帶入儀器校正補正值
          </Button>
        </div>
        <div className="text-muted mb-2" style={{ fontSize: 11 }}>
          偏差＝（校正測試讀值＋修正值）− 控制讀值；每筆讀值均需符合公差 ±{tolerance || '?'}°C
        </div>

        <Nav variant="tabs" activeKey={activeZone} onSelect={key => onActiveZoneChange(parseActiveZone(key, activeZone, satPoints.length - 1))}>
          {satPoints.map((point, index) => {
            const { allPass, hasData } = evaluateSatPoint(point, tolerance);
            return (
              <Nav.Item key={index}>
                <Nav.Link eventKey={index} style={{ fontSize: 13, padding: '6px 14px' }}>
                  {point.控溫區 || `Zone${index + 1}`}
                  {hasData && (
                    <span style={{ marginLeft: 6, fontWeight: 700 }}>
                      {allPass
                        ? <span style={{ color: '#198754' }}>✓</span>
                        : <span style={{ color: '#dc3545' }}>✗</span>}
                    </span>
                  )}
                </Nav.Link>
              </Nav.Item>
            );
          })}
        </Nav>

        <div className="border border-top-0 rounded-bottom p-3 mb-3">
          {satPoints.map((point, index) =>
            index === activeZone ? (
              <div key={index}>
                <Row className="g-2 mb-2 align-items-start">
                  <Col md="auto" className="text-center">
                    <Form.Label className="mb-0 d-block" style={{ fontSize: 12 }}>排除</Form.Label>
                    <Form.Check
                      type="checkbox"
                      aria-label={`排除 ${index + 1}`}
                      checked={!!point.已排除}
                      onChange={event => onToggleExclude(index, event.target.checked)}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label className="mb-0" style={{ fontSize: 12 }}>排除原因</Form.Label>
                    <Form.Control
                      size="sm"
                      value={point.排除原因 ?? ''}
                      aria-label={`排除原因 ${index + 1}`}
                      disabled={!point.已排除}
                      placeholder={point.已排除 ? '必填' : ''}
                      isInvalid={!!point.已排除 && !String(point.排除原因 ?? '').trim()}
                      onChange={event => onReasonChange(index, event.target.value)}
                    />
                    <Form.Control.Feedback type="invalid">請填寫排除原因</Form.Control.Feedback>
                  </Col>
                </Row>
                <SatZoneTab
                  point={point}
                  tolerance={tolerance}
                  onUpdateField={(key, value) => onUpdateSatField(index, key, value)}
                  onUpdateReading={(readingIndex, key, value) => onUpdateSatReading(index, readingIndex, key, value)}
                  onAddReading={() => onAddSatReading(index)}
                  onRemoveReading={readingIndex => onRemoveSatReading(index, readingIndex)}
                />
              </div>
            ) : null,
          )}
        </div>
      </>
    )}
    </>
  );
};

export default SatSection;
