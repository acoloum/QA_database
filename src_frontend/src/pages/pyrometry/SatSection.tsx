import type { ReactNode } from 'react';
import { Button, Col, Form, Nav, Row } from 'react-bootstrap';

import TusChart from '../../components/pyrometry/TusChart';
import TusDataTable from '../../components/pyrometry/TusDataTable';
import type { SatPoint, SatReading } from '../../types';
import { resolvePyrometryChartSettings } from './pyrometryChartSettings';
import type { ChartData } from './pyrometryFormUtils';
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
            <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
              <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>SAT 恆溫穩定期：</span>
              <div className="d-flex align-items-center gap-1">
                <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
                <Form.Select
                  size="sm"
                  style={{ minWidth: 120 }}
                  value={satRangeStart}
                  onChange={event => onSatRangeStartChange(Number(event.target.value))}
                >
                  {satTimeLabels.map((time, index) => <option key={index} value={index}>{time}</option>)}
                </Form.Select>
              </div>
              <div className="d-flex align-items-center gap-1">
                <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
                <Form.Select
                  size="sm"
                  style={{ minWidth: 120 }}
                  value={satRangeEnd}
                  onChange={event => onSatRangeEndChange(Number(event.target.value))}
                >
                  {satTimeLabels.map((time, index) => <option key={index} value={index}>{time}</option>)}
                </Form.Select>
              </div>
              <Button size="sm" variant="primary" onClick={onApplyRangeSat}>
                套用並回填讀值
              </Button>
              <span className="text-muted" style={{ fontSize: 11 }}>
                共 {satRangeEnd >= satRangeStart ? satRangeEnd - satRangeStart + 1 : 0} 筆
              </span>
            </div>
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

        <Nav variant="tabs" activeKey={activeZone} onSelect={key => onActiveZoneChange(Number(key))}>
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
              <SatZoneTab
                key={index}
                point={point}
                tolerance={tolerance}
                onUpdateField={(key, value) => onUpdateSatField(index, key, value)}
                onUpdateReading={(readingIndex, key, value) => onUpdateSatReading(index, readingIndex, key, value)}
                onAddReading={() => onAddSatReading(index)}
                onRemoveReading={readingIndex => onRemoveSatReading(index, readingIndex)}
              />
            ) : null,
          )}
        </div>
      </>
    )}
    </>
  );
};

export default SatSection;
