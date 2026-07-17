
import { useMemo, useState } from 'react';
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
import PatrolOutlierManagerModal from '../spc/PatrolOutlierManagerModal';
import { Badge, Button, Form } from 'react-bootstrap';
import {
    useExportPatrolSpcReport, usePatrolStats,
    useFreezePatrolLimits, useUnfreezePatrolLimits,
} from '../../hooks/usePatrol';
import type { SpcChartData } from '../../types';

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
    const [showSpecLimits, setShowSpecLimits] = useState(false);
    const [outlierTargetId, setOutlierTargetId] = useState<number | null>(null);
    const [selectedRecordId, setSelectedRecordId] = useState('');

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

    const typedStatsData = statsData as SpcChartData | null | undefined;
    const controlLimitsKey = { material, spec, item: statsItem, position: statsPos };
    const freezeLimits = useFreezePatrolLimits();
    const unfreezeLimits = useUnfreezePatrolLimits();

    const spcModel = useMemo(
        () => buildSpcChartModel(typedStatsData, { showSpecLimits }),
        [typedStatsData, showSpecLimits]
    );

    // 記錄選單需去重：同一巡檢主檔可能對應多個組別，ids 陣列會重複同一 main_id
    const recordOptions = useMemo(() => {
        const seen = new Set<string>();
        const opts: { id: string; date?: string }[] = [];
        spcModel.ids.forEach((id, i) => {
            if (seen.has(id)) return;
            seen.add(id);
            opts.push({ id, date: typedStatsData?.dates?.[i] });
        });
        return opts;
    }, [spcModel.ids, typedStatsData]);

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
                        disabled={recordOptions.length === 0}
                    >
                        <option value="">選擇記錄以管理離群值…</option>
                        {recordOptions.map(o => (
                            <option key={o.id} value={o.id}>#{o.id}{o.date ? ` · ${o.date}` : ''}</option>
                        ))}
                    </Form.Select>
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        disabled={!selectedRecordId}
                        onClick={() => setOutlierTargetId(Number(selectedRecordId))}
                    >
                        離群值管理
                    </Button>
                    {typedStatsData?.limits_frozen
                        ? <Badge bg="info">管制界限已凍結</Badge>
                        : <Badge bg="light" text="dark">界限逐次重算中</Badge>}
                    <Button size="sm" variant="outline-primary"
                        disabled={freezeLimits.isPending || !spcModel.chartData}
                        onClick={() => freezeLimits.mutate(controlLimitsKey)}>
                        凍結目前界限
                    </Button>
                    <Button size="sm" variant="outline-secondary"
                        disabled={unfreezeLimits.isPending || !typedStatsData?.limits_frozen}
                        onClick={() => unfreezeLimits.mutate(controlLimitsKey)}>
                        解除凍結
                    </Button>
                    <Button variant="outline-success" onClick={handleExportSpc} disabled={exportSpcReport.isPending}>
                        <i className="bi bi-file-earmark-bar-graph"></i> {exportSpcReport.isPending ? '匯出中...' : '匯出 SPC 報告'}
                    </Button>
                </div>
            </div>

            <SpcDashboardPanel
                model={spcModel}
                statsItem={statsItem}
                emptyMessage={`選擇的檢驗項目「${statsItem}」沒有足夠的數據來產生 SPC 圖表，請嘗試其他檢驗項目或區段。`}
                sampleCount={statsData?.all_values?.length ?? 0}
                onEditPoint={onEditPoint}
                filterXBarLegendLabels
            />

            <PatrolOutlierManagerModal
                mainId={outlierTargetId}
                show={outlierTargetId != null}
                onHide={() => setOutlierTargetId(null)}
            />
        </div>
    );
};

export default PatrolCharts;
