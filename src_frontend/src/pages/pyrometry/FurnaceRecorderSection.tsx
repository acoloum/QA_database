import { Button, Col, Form } from 'react-bootstrap';

import TusChart from '../../components/pyrometry/TusChart';
import TusDataTable from '../../components/pyrometry/TusDataTable';
import { resolvePyrometryChartSettings } from './pyrometryChartSettings';
import type { ChartData } from './pyrometryFormUtils';

interface Props {
  furnaceChartData: ChartData | null;
  setpoint: string;
  tolerance: string;
  furnaceRangeStart: number;
  furnaceRangeEnd: number;
  furnaceTimeLabels: string[];
  showFurnaceDetail: boolean;
  onFurnaceRangeStartChange: (value: number) => void;
  onFurnaceRangeEndChange: (value: number) => void;
  onApplyRangeFurnace: () => void;
  onToggleFurnaceDetail: () => void;
}

const FurnaceRecorderSection = ({
  furnaceChartData,
  setpoint,
  tolerance,
  furnaceRangeStart,
  furnaceRangeEnd,
  furnaceTimeLabels,
  showFurnaceDetail,
  onFurnaceRangeStartChange,
  onFurnaceRangeEndChange,
  onApplyRangeFurnace,
  onToggleFurnaceDetail,
}: Props) => {
  if (!furnaceChartData) return null;
  const { setpointValue, toleranceValue } = resolvePyrometryChartSettings({ setpoint, tolerance });

  return (
    <>
      <Col md={12}>
        <TusChart
          時間={furnaceChartData.時間}
          數值={furnaceChartData.數值}
          設定溫度={setpointValue}
          公差={toleranceValue}
          startIdx={furnaceRangeStart}
          endIdx={furnaceRangeEnd}
          標題="爐體記錄溫度曲線"
        />
      </Col>
      <Col md={12}>
        <div className="d-flex align-items-center gap-3 p-2 bg-light rounded border">
          <span className="fw-semibold text-nowrap" style={{ fontSize: 13 }}>爐體恆溫穩定期：</span>
          <div className="d-flex align-items-center gap-1">
            <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>開始</Form.Label>
            <Form.Select
              size="sm"
              style={{ minWidth: 120 }}
              value={furnaceRangeStart}
              aria-label="爐體恆溫穩定期開始"
              onChange={event => onFurnaceRangeStartChange(Number(event.target.value))}
            >
              {furnaceTimeLabels.map((time, index) => <option key={index} value={index}>{time}</option>)}
            </Form.Select>
          </div>
          <div className="d-flex align-items-center gap-1">
            <Form.Label className="mb-0 text-muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>結束</Form.Label>
            <Form.Select
              size="sm"
              style={{ minWidth: 120 }}
              value={furnaceRangeEnd}
              aria-label="爐體恆溫穩定期結束"
              onChange={event => onFurnaceRangeEndChange(Number(event.target.value))}
            >
              {furnaceTimeLabels.map((time, index) => <option key={index} value={index}>{time}</option>)}
            </Form.Select>
          </div>
          <Button size="sm" variant="primary" onClick={onApplyRangeFurnace}>
            套用並回填控制儀表讀值
          </Button>
          <span className="text-muted" style={{ fontSize: 11 }}>
            共 {furnaceRangeEnd >= furnaceRangeStart ? furnaceRangeEnd - furnaceRangeStart + 1 : 0} 筆
          </span>
        </div>
      </Col>
      <Col md={12}>
        <div className="d-flex align-items-center gap-2 mb-1">
          <Button size="sm" variant="outline-secondary" onClick={onToggleFurnaceDetail}>
            {showFurnaceDetail ? '隱藏爐體詳細數據表' : '顯示爐體詳細數據表'}
          </Button>
          <span className="text-muted" style={{ fontSize: 11 }}>
            <span style={{ background: '#f8d7da', color: '#842029', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>紅底＝超上限</span>
            <span style={{ background: '#cfe2ff', color: '#084298', fontWeight: 600, padding: '0 4px', margin: '0 2px' }}>藍底＝低於下限</span>
          </span>
        </div>
        {showFurnaceDetail && (
          <TusDataTable
            時間={furnaceChartData.時間}
            數值={furnaceChartData.數值}
            設定溫度={setpointValue}
            公差={toleranceValue}
            穩定開始={furnaceRangeStart}
            穩定結束={furnaceRangeEnd}
          />
        )}
      </Col>
    </>
  );
};

export default FurnaceRecorderSection;
