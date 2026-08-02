import { useMemo, useState } from 'react';
import { Badge, Button, Card, Col, Container, Form, Row, Spinner, Table } from 'react-bootstrap';
import { Bar, Line } from 'react-chartjs-2';
import {
    useCapaAging,
    useDefectTrends,
    usePareto,
    useRepeatIssues,
    useVendorRanking,
} from '../../hooks/useQualityAnalytics';
import { formatLocalMonth } from '../../utils/dateUtils';
import '../../utils/chartSetup';

const COLORS = ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#0891b2'];

const currentMonth = () => formatLocalMonth();

const QualityAnalyticsPage = () => {
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');
    const [applied, setApplied] = useState<{ date_from?: string; date_to?: string }>({});
    const [trendSource, setTrendSource] = useState<'ncmr' | 'complaint'>('ncmr');
    const [rankingPeriod, setRankingPeriod] = useState(currentMonth());

    const ncmrPareto = usePareto('ncmr', applied);
    const complaintPareto = usePareto('complaint', applied);
    const defectTrends = useDefectTrends(trendSource, applied);
    const capaAging = useCapaAging();
    const repeatIssues = useRepeatIssues(applied);
    const vendorRanking = useVendorRanking(rankingPeriod);

    const isLoading = ncmrPareto.isLoading || complaintPareto.isLoading || defectTrends.isLoading ||
        capaAging.isLoading || repeatIssues.isLoading || vendorRanking.isLoading;

    const applyFilter = () => setApplied({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
    });

    const clearFilter = () => {
        setDateFrom('');
        setDateTo('');
        setApplied({});
    };

    const trendChartData = useMemo(() => ({
        labels: defectTrends.data?.months ?? [],
        datasets: (defectTrends.data?.series ?? []).map((series, index) => ({
            label: series.label,
            data: series.data,
            borderColor: COLORS[index % COLORS.length],
            backgroundColor: COLORS[index % COLORS.length],
            tension: 0.25,
        })),
    }), [defectTrends.data]);

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h4 className="mb-1">
                        <i className="fa-solid fa-chart-simple me-2 text-primary" />
                        品質分析
                    </h4>
                    <div className="text-muted small">Pareto、分類趨勢、CAPA aging、重複問題與供應商排名</div>
                </div>
                {isLoading && <Spinner animation="border" size="sm" />}
            </div>

            <Card className="mb-4 shadow-sm">
                <Card.Body className="py-3">
                    <Row className="g-2 align-items-end">
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（起）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
                        </Col>
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（迄）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateTo} onChange={e => setDateTo(e.target.value)} />
                        </Col>
                        <Col xs={6} md={2}>
                            <Button size="sm" className="w-100" onClick={applyFilter}>套用篩選</Button>
                        </Col>
                        <Col xs={6} md={2}>
                            <Button size="sm" variant="outline-secondary" className="w-100" onClick={clearFilter}>清除</Button>
                        </Col>
                        <Col xs={12} md={2}>
                            <Form.Label className="small mb-1">供應商排名月份</Form.Label>
                            <Form.Control type="month" size="sm" value={rankingPeriod} onChange={e => setRankingPeriod(e.target.value)} />
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            <Row className="g-4">
                <Col xl={6}>
                    <ParetoCard title="NCMR 不良原因 Pareto" items={ncmrPareto.data?.items ?? []} />
                </Col>
                <Col xl={6}>
                    <ParetoCard title="客訴不良類別 Pareto" items={complaintPareto.data?.items ?? []} />
                </Col>

                <Col xl={8}>
                    <Card className="shadow-sm h-100">
                        <Card.Header className="d-flex justify-content-between align-items-center">
                            <span className="fw-semibold">不良分類趨勢</span>
                            <Form.Select
                                size="sm"
                                style={{ width: 140 }}
                                value={trendSource}
                                onChange={e => setTrendSource(e.target.value as 'ncmr' | 'complaint')}
                            >
                                <option value="ncmr">NCMR</option>
                                <option value="complaint">客訴</option>
                            </Form.Select>
                        </Card.Header>
                        <Card.Body>
                            {(defectTrends.data?.series?.length ?? 0) > 0 ? (
                                <Line data={trendChartData} options={{ responsive: true, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }} />
                            ) : (
                                <EmptyState />
                            )}
                        </Card.Body>
                    </Card>
                </Col>

                <Col xl={4}>
                    <CapaAgingCard data={capaAging.data} />
                </Col>

                <Col xl={7}>
                    <RepeatIssuesCard data={repeatIssues.data} />
                </Col>

                <Col xl={5}>
                    <VendorRankingCard rows={vendorRanking.data ?? []} />
                </Col>
            </Row>
        </Container>
    );
};

const EmptyState = () => <div className="text-center text-muted py-4">無資料</div>;

const paretoChartOptions = {
    responsive: true,
    scales: {
        x: {
            ticks: {
                autoSkip: false,
                maxRotation: 45,
                minRotation: 0,
            },
        },
        y: { beginAtZero: true },
    },
};

const ParetoCard = ({ title, items }: { title: string; items: { label: string; count: number; cumulative_pct: number }[] }) => (
    <Card className="shadow-sm h-100">
        <Card.Header className="fw-semibold">{title}</Card.Header>
        <Card.Body>
            {items.length > 0 ? (
                <Bar
                    data={{
                        labels: items.map(i => i.label),
                        datasets: [
                            { label: '件數', data: items.map(i => i.count), backgroundColor: '#2563eb' },
                            { label: '累積%', data: items.map(i => i.cumulative_pct), backgroundColor: '#f59e0b' },
                        ],
                    }}
                    options={paretoChartOptions}
                />
            ) : <EmptyState />}
        </Card.Body>
    </Card>
);

const CapaAgingCard = ({ data }: { data?: { buckets: Record<string, number>; open_count: number; overdue_count: number; avg_close_days: number | null; overdue_items: { number: string; overdue_days: number }[] } }) => (
    <Card className="shadow-sm h-100">
        <Card.Header className="fw-semibold">CAPA Aging</Card.Header>
        <Card.Body>
            {data ? (
                <>
                    <div className="d-flex gap-2 mb-3 flex-wrap">
                        <Badge bg="primary">未結案 {data.open_count}</Badge>
                        <Badge bg="danger">逾期 {data.overdue_count}</Badge>
                        <Badge bg="secondary">平均結案 {data.avg_close_days ?? '-'} 天</Badge>
                    </div>
                    <Table size="sm" className="mb-3">
                        <tbody>
                            {Object.entries(data.buckets).map(([bucket, count]) => (
                                <tr key={bucket}>
                                    <td>{bucket} 天</td>
                                    <td className="text-end fw-semibold">{count}</td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                    <div className="small fw-semibold mb-2">逾期清單</div>
                    {data.overdue_items.length > 0 ? data.overdue_items.slice(0, 5).map(item => (
                        <div key={item.number} className="d-flex justify-content-between border-bottom py-1 small">
                            <span>{item.number}</span>
                            <span className="text-danger">{item.overdue_days} 天</span>
                        </div>
                    )) : <div className="text-muted small">無逾期 CAPA</div>}
                </>
            ) : <EmptyState />}
        </Card.Body>
    </Card>
);

const RepeatIssuesCard = ({ data }: { data?: { ncmr: { vendor: string; defect_category: string; defect_detail: string; count: number; latest_date: string | null }[]; complaints: { complaint_no: string; customer: string; defect_category: string; complaint_date: string | null }[] } }) => (
    <Card className="shadow-sm h-100">
        <Card.Header className="fw-semibold">重複問題</Card.Header>
        <Card.Body>
            <div className="small fw-semibold mb-2">NCMR 重複群組</div>
            <Table size="sm" responsive>
                <thead><tr><th>廠商</th><th>類別</th><th>細項</th><th className="text-end">次數</th><th>最近</th></tr></thead>
                <tbody>
                    {(data?.ncmr ?? []).length > 0 ? data?.ncmr.map((item, idx) => (
                        <tr key={`${item.vendor}-${item.defect_category}-${idx}`}>
                            <td>{item.vendor}</td>
                            <td>{item.defect_category}</td>
                            <td>{item.defect_detail}</td>
                            <td className="text-end">{item.count}</td>
                            <td>{item.latest_date ?? '-'}</td>
                        </tr>
                    )) : <tr><td colSpan={5} className="text-center text-muted">無資料</td></tr>}
                </tbody>
            </Table>
            <div className="small fw-semibold mb-2 mt-3">已標記重複客訴</div>
            {(data?.complaints ?? []).length > 0 ? data?.complaints.slice(0, 5).map(item => (
                <div key={item.complaint_no} className="d-flex justify-content-between border-bottom py-1 small">
                    <span>{item.complaint_no} / {item.customer}</span>
                    <span>{item.defect_category}</span>
                </div>
            )) : <div className="text-muted small">無重複客訴</div>}
        </Card.Body>
    </Card>
);

const VendorRankingCard = ({ rows }: { rows: { vendor_id: number; vendor_name: string; score: number; defect_rate: number; capa_count: number; complaint_count: number }[] }) => (
    <Card className="shadow-sm h-100">
        <Card.Header className="fw-semibold">供應商風險排名</Card.Header>
        <Card.Body>
            <Table size="sm" responsive>
                <thead><tr><th>供應商</th><th className="text-end">分數</th><th className="text-end">缺陷率</th><th className="text-end">CAPA</th><th className="text-end">客訴</th></tr></thead>
                <tbody>
                    {rows.length > 0 ? rows.map(row => (
                        <tr key={row.vendor_id}>
                            <td>{row.vendor_name}</td>
                            <td className="text-end fw-semibold">{row.score}</td>
                            <td className="text-end">{row.defect_rate}%</td>
                            <td className="text-end">{row.capa_count}</td>
                            <td className="text-end">{row.complaint_count}</td>
                        </tr>
                    )) : <tr><td colSpan={5} className="text-center text-muted">無資料</td></tr>}
                </tbody>
            </Table>
        </Card.Body>
    </Card>
);

export default QualityAnalyticsPage;
