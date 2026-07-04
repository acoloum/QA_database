import { Button, Col, Form, Row, Table } from 'react-bootstrap';

import TusChart from '../../components/pyrometry/TusChart';
import TusDataTable from '../../components/pyrometry/TusDataTable';
import type { TusPoint } from '../../types';
import ChartRangeControls from './ChartRangeControls';
import { resolvePyrometryChartSettings } from './pyrometryChartSettings';
import type { ChartData } from './pyrometryFormUtils';

interface Props {
  tusPoints: TusPoint[];
  setpoint: string;
  tolerance: string;
  chartData: ChartData | null;
  rangeStart: number;
  rangeEnd: number;
  showDetail: boolean;
  timeLabels: string[];
  onFileUpload: (file: File) => void;
  onRangeStartChange: (value: number) => void;
  onRangeEndChange: (value: number) => void;
  onApplyRangeTus: () => void;
  onToggleDetail: () => void;
  onUpdateTus: (index: number, key: keyof TusPoint, value: string) => void;
  onApplyCorrections: () => void;
  onToggleExclude: (index: number, checked: boolean) => void;
  onReasonChange: (index: number, value: string) => void;
}

const TusSection = ({
  tusPoints,
  setpoint,
  tolerance,
  chartData,
  rangeStart,
  rangeEnd,
  showDetail,
  timeLabels,
  onFileUpload,
  onRangeStartChange,
  onRangeEndChange,
  onApplyRangeTus,
  onToggleDetail,
  onUpdateTus,
  onApplyCorrections,
  onToggleExclude,
  onReasonChange,
}: Props) => {
  const { setpointValue, toleranceValue } = resolvePyrometryChartSettings({ setpoint, tolerance });

  return (
    <>
    <Row className="g-2 mb-3">
      <Col md={12}>
        <Form.Label>測試儀器數據（CSV/Excel）</Form.Label>
        <input
          className="form-control form-control-sm"
          type="file"
          accept=".csv,.xlsx,.xls"
          aria-label="測試儀器數據"
          onChange={event => {
            const file = event.target.files?.[0];
            if (file) onFileUpload(file);
          }}
        />
      </Col>
      {chartData && (
        <>
          <Col md={12}>
            <TusChart
              時間={chartData.時間}
              數值={chartData.數值}
              設定溫度={setpointValue}
              公差={toleranceValue}
              startIdx={rangeStart}
              endIdx={rangeEnd}
              標題="測試儀器（記錄器）溫度曲線"
            />
          </Col>
          <Col md={12}>
            <ChartRangeControls
              label="恆溫穩定期"
              start={rangeStart}
              end={rangeEnd}
              timeLabels={timeLabels}
              applyLabel="套用並回填量測點"
              onStartChange={onRangeStartChange}
              onEndChange={onRangeEndChange}
              onApply={onApplyRangeTus}
            />
          </Col>
          <Col md={12}>
            <div className="d-flex align-items-center gap-2 mb-1">
              <Button size="sm" variant="outline-secondary" onClick={onToggleDetail}>
                {showDetail ? '隱藏詳細數據表' : '顯示詳細數據表'}
              </Button>
              <span className="text-muted" style={{ fontSize: 11 }}>
                <span style={{ background: '#f8d7da', color: '#842029', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>紅底＝超上限</span>
                <span style={{ background: '#cfe2ff', color: '#084298', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>藍底＝低於下限</span>
              </span>
            </div>
            {showDetail && (
              <TusDataTable
                時間={chartData.時間}
                數值={chartData.數值}
                設定溫度={setpointValue}
                公差={toleranceValue}
                穩定開始={rangeStart}
                穩定結束={rangeEnd}
              />
            )}
          </Col>
        </>
      )}
    </Row>

    {tusPoints.length > 0 && (
      <>
        <div className="d-flex justify-content-between align-items-center">
          <h6 className="mb-0">TUS 量測點明細</h6>
          <Button size="sm" variant="outline-secondary" onClick={onApplyCorrections}>
            帶入儀器校正補正值
          </Button>
        </div>
        <div className="text-muted mb-1" style={{ fontSize: 11 }}>
          修正值＝熱電偶補正＋記錄器補正（依設定溫度內插）；校正後溫度＝量測值＋修正值
        </div>
        <Table bordered size="sm">
          <thead className="table-secondary">
            <tr>
              <th>點位</th>
              <th style={{ width: 100, minWidth: 100 }}>頻道</th>
              <th>修正值</th>
              <th>最高溫</th>
              <th>最低溫</th>
              <th style={{ width: 70 }}>排除</th>
              <th>排除原因</th>
            </tr>
          </thead>
          <tbody>
            {tusPoints.map((point, index) => (
              <tr key={index}>
                <td>
                  <Form.Control
                    size="sm"
                    value={point.點位}
                    aria-label={`點位 ${index + 1}`}
                    onChange={event => onUpdateTus(index, '點位', event.target.value)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    type="number"
                    min={1}
                    max={99}
                    value={point.頻道 ?? ''}
                    aria-label={`頻道 ${index + 1}`}
                    onChange={event => onUpdateTus(index, '頻道', event.target.value)}
                    style={{ minWidth: 70 }}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={String(point.修正值 ?? '')}
                    aria-label={`修正值 ${index + 1}`}
                    onChange={event => onUpdateTus(index, '修正值', event.target.value)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={String(point.最高溫 ?? '')}
                    aria-label={`最高溫 ${index + 1}`}
                    onChange={event => onUpdateTus(index, '最高溫', event.target.value)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={String(point.最低溫 ?? '')}
                    aria-label={`最低溫 ${index + 1}`}
                    onChange={event => onUpdateTus(index, '最低溫', event.target.value)}
                  />
                </td>
                <td className="text-center">
                  <Form.Check
                    type="checkbox"
                    aria-label={`排除 ${index + 1}`}
                    checked={!!point.已排除}
                    onChange={event => onToggleExclude(index, event.target.checked)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={point.排除原因 ?? ''}
                    aria-label={`排除原因 ${index + 1}`}
                    disabled={!point.已排除}
                    placeholder={point.已排除 ? '必填' : ''}
                    isInvalid={!!point.已排除 && !String(point.排除原因 ?? '').trim()}
                    onChange={event => onReasonChange(index, event.target.value)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </>
    )}
    </>
  );
};

export default TusSection;
