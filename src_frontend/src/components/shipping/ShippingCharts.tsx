
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
import SpcDashboardPanel from '../spc/SpcDashboardPanel';
import OutlierManagerModal from '../spc/OutlierManagerModal';
import type { SpcChartData } from '../../types';
import { Button, Form } from 'react-bootstrap';
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
    const [outlierTargetId, setOutlierTargetId] = useState<number | null>(null);
    const [selectedRecordId, setSelectedRecordId] = useState('');
    const [showSpecLimits, setShowSpecLimits] = useState(false);

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

    const typedStatsData = statsData as SpcChartData | null | undefined;
    const spcModel = useMemo(
        () => buildSpcChartModel(typedStatsData, { showSpecLimits }),
        [typedStatsData, showSpecLimits]
    );

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
                    <Form.Check
                        type="switch"
                        id="show-spec-limits"
                        className="ms-3"
                        label="疊加規格界限（分析模式）"
                        checked={showSpecLimits}
                        onChange={e => setShowSpecLimits(e.target.checked)}
                    />
                </div>
                <div className="d-flex align-items-center gap-2">
                    <Form.Select
                        size="sm"
                        style={{ width: 'auto' }}
                        value={selectedRecordId}
                        onChange={e => setSelectedRecordId(e.target.value)}
                        disabled={spcModel.ids.length === 0}
                    >
                        <option value="">選擇記錄以管理離群值…</option>
                        {spcModel.ids.map((id, i) => {
                            const date = typedStatsData?.dates?.[i];
                            const label = typedStatsData?.labels?.[i];
                            const extra = [date, label && label !== id ? label : null].filter(Boolean).join(' · ');
                            return <option key={id} value={id}>#{id}{extra ? ` · ${extra}` : ''}</option>;
                        })}
                    </Form.Select>
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        disabled={!selectedRecordId}
                        onClick={() => setOutlierTargetId(Number(selectedRecordId))}
                    >
                        離群值管理
                    </Button>
                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={handleExportReport}
                        disabled={exportSpcReport.isPending || !spcModel.chartData}
                    >
                        {exportSpcReport.isPending ? '匯出中...' : '📥 匯出 SPC 報告'}
                    </Button>
                </div>
            </div>

            <SpcDashboardPanel
                model={spcModel}
                statsItem={statsField}
                emptyMessage={`選擇的檢驗項目「${statsField}」沒有足夠的數據來產生 SPC 圖表，請嘗試其他檢驗項目。`}
                sampleCount={statsData?.all_values?.length ?? 0}
                onEditPoint={onPointClick}
                filterXBarLegendLabels
            />

            <OutlierManagerModal
                shippingId={outlierTargetId}
                show={outlierTargetId != null}
                onHide={() => setOutlierTargetId(null)}
            />
        </div>
    );
};

export default ShippingCharts;
