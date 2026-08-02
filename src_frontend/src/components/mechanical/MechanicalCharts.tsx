import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, Form } from 'react-bootstrap';

import { mechanicalApi } from '../../services/mechanicalApi';
import { buildSpcChartModel, mergeOngoingStudyForDisplay } from '../../utils/spcChartModel';
import SpcDashboardPanel from '../spc/SpcDashboardPanel';
import SpcStudyPanel from '../spc/SpcStudyPanel';
import SpcReportModal from '../spc/report/SpcReportModal';
import { reportModelFromStats } from '../spc/report/spcReportModel';
import type { SpcStudyResult } from '../../types';
import { mechanicalKeys, masterDataKeys } from '../../hooks/queryKeys';
import '../../utils/chartSetup';

// 力學特性（EC 值不納入 SPC）與量測位置（爐門/爐頂分開監控）
const MECHANICAL_ITEMS = ['硬度', '抗拉強度', '降伏強度', '伸長率'];
const MECHANICAL_POSITIONS = ['爐門', '爐頂'];

interface MechanicalChartsProps {
  vendorId: string;
  material: string;
  productSize: string;
  startDate: string;
  endDate: string;
  onPointClick?: (id: number) => void;
}

export default function MechanicalCharts({
  vendorId, material, productSize, startDate, endDate, onPointClick,
}: MechanicalChartsProps) {
  const [item, setItem] = useState('抗拉強度');
  const [position, setPosition] = useState('爐門');
  const [showSpecLimits, setShowSpecLimits] = useState(false);
  const [studyVersion, setStudyVersion] = useState<SpcStudyResult | null>(null);
  const [showReport, setShowReport] = useState(false);

  const params = useMemo(() => ({
    item, position,
    vendor_id: vendorId || undefined,
    material: material || undefined,
    product_size: productSize || undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  }), [item, position, vendorId, material, productSize, startDate, endDate]);

  const { data: statsData } = useQuery({
    queryKey: mechanicalKeys.stats(params),
    queryFn: () => mechanicalApi.stats(params),
    staleTime: 5 * 60 * 1000,
  });

  const { data: vendors } = useQuery({ queryKey: masterDataKeys.vendors, queryFn: mechanicalApi.getVendors });
  const vendorName = vendors?.find((v) => String(v.id) === String(vendorId))?.name;

  const studyFilters = useMemo(() => ({
    item, position, vendor_id: vendorId || null, material,
    product_size: productSize, start_date: startDate, end_date: endDate,
  }), [item, position, vendorId, material, productSize, startDate, endDate]);

  const displayStatsData = useMemo(
    () => mergeOngoingStudyForDisplay(statsData, studyVersion),
    [statsData, studyVersion],
  );
  const spcModel = useMemo(
    () => buildSpcChartModel(displayStatsData, { showSpecLimits }),
    [displayStatsData, showSpecLimits],
  );

  const advancedSpcHref = useMemo(() => {
    const search = new URLSearchParams({ family: 'variable', source: 'mechanical' });
    const values: Record<string, string> = {
      vendor_id: vendorId, material, product_size: productSize,
      item, position, start_date: startDate, end_date: endDate,
    };
    Object.entries(values).forEach(([key, value]) => {
      if (value.trim()) search.set(key, value.trim());
    });
    return `/spc/advanced?${search.toString()}`;
  }, [vendorId, material, productSize, item, position, startDate, endDate]);

  return (
    <div className="mt-4">
      <div className="d-flex align-items-center justify-content-between gap-3 flex-wrap mb-3">
        <div className="d-flex align-items-center flex-wrap gap-2">
          <h4 className="mb-0 me-3">📊 SPC 監控與分析</h4>
          <Form.Select
            style={{ width: 'auto' }}
            aria-label="力學特性"
            value={item}
            onChange={(e) => setItem(e.target.value)}
          >
            {MECHANICAL_ITEMS.map((name) => <option key={name} value={name}>{name}</option>)}
          </Form.Select>
          <Form.Select
            style={{ width: 'auto' }}
            aria-label="量測位置"
            value={position}
            onChange={(e) => setPosition(e.target.value)}
          >
            {MECHANICAL_POSITIONS.map((p) => <option key={p} value={p}>{p}</option>)}
          </Form.Select>
          <Form.Check
            type="switch"
            id="mechanical-show-spec-limits"
            className="ms-3"
            label="疊加規格界限（分析模式）"
            checked={showSpecLimits}
            onChange={(e) => setShowSpecLimits(e.target.checked)}
          />
        </div>
        <div className="d-flex gap-2">
          <Button
            variant="outline-primary"
            size="sm"
            disabled={!statsData?.all_values?.length}
            onClick={() => setShowReport(true)}
          >
            📄 產生 SPC 報告
          </Button>
          <a href={advancedSpcHref} className="btn btn-outline-info btn-sm">
            進階變數分析
          </a>
        </div>
      </div>

      <SpcStudyPanel
        source="mechanical"
        filters={studyFilters}
        preview={statsData}
        version={studyVersion}
        onVersionChange={setStudyVersion}
      />

      <SpcDashboardPanel
        model={spcModel}
        statsItem={`${item}（${position}）`}
        emptyMessage={`選擇的特性「${item}（${position}）」沒有足夠的數據來產生 SPC 圖表，請嘗試其他特性或位置。`}
        sampleCount={statsData?.all_values?.length ?? 0}
        onEditPoint={onPointClick}
        filterXBarLegendLabels
      />

      <SpcReportModal
        show={showReport}
        model={statsData ? reportModelFromStats('mechanical', studyFilters, displayStatsData ?? statsData, { vendorName }) : null}
        statsItem={`${item}（${position}）`}
        onHide={() => setShowReport(false)}
      />
    </div>
  );
}
