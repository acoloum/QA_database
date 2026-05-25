import { useState } from 'react';
import { Container, Card, Row, Col, Form, Button, Spinner } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import {
    Chart as ChartJS,
    CategoryScale, LinearScale, BarElement, ArcElement,
    PointElement, LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';
import { Bar, Line } from 'react-chartjs-2';
import {
    useComplaintStatsByCustomer,
    useComplaintStatsByProduct,
    useComplaintStatsByMonth,
    useComplaintStatsWarranty,
} from '../../hooks/useComplaint';

ChartJS.register(
    CategoryScale, LinearScale, BarElement, ArcElement,
    PointElement, LineElement, Title, Tooltip, Legend, Filler,
);

const CHART_COLORS = ['#2B579A', '#4472C4', '#5B9BD5', '#9DC3E6', '#BDD7EE', '#DDEBF7'];

const ComplaintStatsPage = () => {
    const navigate = useNavigate();
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo,   setDateTo]   = useState('');
    const [appliedFrom, setAppliedFrom] = useState<string | undefined>(undefined);
    const [appliedTo,   setAppliedTo]   = useState<string | undefined>(undefined);

    const applyFilter = () => {
        setAppliedFrom(dateFrom || undefined);
        setAppliedTo(dateTo || undefined);
    };
    const resetFilter = () => {
        setDateFrom(''); setDateTo('');
        setAppliedFrom(undefined); setAppliedTo(undefined);
    };

    const fp = { date_from: appliedFrom, date_to: appliedTo };

    const { data: byCustomer, isLoading: l1 } = useComplaintStatsByCustomer(fp);
    const { data: byProduct,  isLoading: l2 } = useComplaintStatsByProduct(fp);
    const { data: byMonth,    isLoading: l3 } = useComplaintStatsByMonth(fp);
    const { data: warranty,   isLoading: l4 } = useComplaintStatsWarranty(fp);

    const anyLoading = l1 || l2 || l3 || l4;

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="bi bi-bar-chart-fill me-2 text-primary" />
                    客訴統計分析
                </h4>
                <Button variant="outline-secondary" size="sm" onClick={() => navigate('/complaints')}>
                    <i className="bi bi-arrow-left me-1" />
                    返回客訴列表
                </Button>
            </div>

            {/* 日期篩選 */}
            <Card className="mb-4 shadow-sm">
                <Card.Body className="py-2">
                    <Row className="g-2 align-items-end">
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（起）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateFrom}
                                onChange={e => setDateFrom(e.target.value)} />
                        </Col>
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（迄）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateTo}
                                onChange={e => setDateTo(e.target.value)} />
                        </Col>
                        <Col xs={6} md={2}>
                            <Button variant="primary" size="sm" className="w-100" onClick={applyFilter}>套用篩選</Button>
                        </Col>
                        <Col xs={6} md={2}>
                            <Button variant="outline-secondary" size="sm" className="w-100" onClick={resetFilter}>清除</Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            {anyLoading ? (
                <div className="text-center py-5">
                    <Spinner animation="border" />
                    <div className="mt-2 text-muted">統計資料載入中…</div>
                </div>
            ) : (
                <Row className="g-4">
                    {/* 月趨勢折線圖 */}
                    <Col md={12}>
                        <Card className="shadow-sm">
                            <Card.Header className="fw-semibold">每月客訴件數趨勢</Card.Header>
                            <Card.Body>
                                {byMonth && byMonth.length > 0 ? (
                                    <Line
                                        data={{
                                            labels: byMonth.map(d => d.year_month),
                                            datasets: [{
                                                label: '客訴件數',
                                                data: byMonth.map(d => d.total),
                                                borderColor: CHART_COLORS[0],
                                                backgroundColor: CHART_COLORS[0] + '33',
                                                tension: 0.3,
                                                fill: true,
                                            }],
                                        }}
                                        options={{
                                            responsive: true,
                                            plugins: { legend: { position: 'top' } },
                                            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                        }}
                                        height={80}
                                    />
                                ) : <p className="text-muted text-center py-3">無資料</p>}
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* 客戶別橫條圖 */}
                    <Col md={6}>
                        <Card className="shadow-sm">
                            <Card.Header className="fw-semibold">客戶別客訴件數（Top 10）</Card.Header>
                            <Card.Body>
                                {byCustomer && byCustomer.length > 0 ? (
                                    <Bar
                                        data={{
                                            labels: byCustomer.slice(0, 10).map(d => d.customer),
                                            datasets: [
                                                {
                                                    label: '客訴件數',
                                                    data: byCustomer.slice(0, 10).map(d => d.total),
                                                    backgroundColor: CHART_COLORS[0],
                                                },
                                                {
                                                    label: '重複客訴',
                                                    data: byCustomer.slice(0, 10).map(d => d.repeat_count),
                                                    backgroundColor: CHART_COLORS[3],
                                                },
                                            ],
                                        }}
                                        options={{
                                            responsive: true,
                                            plugins: { legend: { position: 'top' } },
                                            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                        }}
                                    />
                                ) : <p className="text-muted text-center py-3">無資料</p>}
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* 料號別橫條圖 */}
                    <Col md={6}>
                        <Card className="shadow-sm">
                            <Card.Header className="fw-semibold">料號別客訴件數（Top 10）</Card.Header>
                            <Card.Body>
                                {byProduct && byProduct.length > 0 ? (
                                    <Bar
                                        data={{
                                            labels: byProduct.slice(0, 10).map(d => d.product_no),
                                            datasets: [
                                                {
                                                    label: '客訴件數',
                                                    data: byProduct.slice(0, 10).map(d => d.total),
                                                    backgroundColor: CHART_COLORS[1],
                                                },
                                                {
                                                    label: '重複客訴',
                                                    data: byProduct.slice(0, 10).map(d => d.repeat_count),
                                                    backgroundColor: CHART_COLORS[4],
                                                },
                                            ],
                                        }}
                                        options={{
                                            responsive: true,
                                            plugins: { legend: { position: 'top' } },
                                            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                        }}
                                    />
                                ) : <p className="text-muted text-center py-3">無資料</p>}
                            </Card.Body>
                        </Card>
                    </Col>

                    {/* 保固 / 現場故障統計 */}
                    {warranty && (
                        <Col md={12}>
                            <Card className="shadow-sm">
                                <Card.Header className="fw-semibold">保固 / 現場故障統計</Card.Header>
                                <Card.Body>
                                    <Row className="g-3 mb-4">
                                        <Col xs={6} md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-primary">{warranty.total}</div>
                                                <div className="small text-muted">總件數</div>
                                            </div>
                                        </Col>
                                        <Col xs={6} md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-warning">{warranty.warranty_count}</div>
                                                <div className="small text-muted">保固申請</div>
                                            </div>
                                        </Col>
                                        <Col xs={6} md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-danger">{warranty.field_failure_count}</div>
                                                <div className="small text-muted">現場故障</div>
                                            </div>
                                        </Col>
                                        <Col xs={6} md={3}>
                                            <div className="text-center border rounded p-3">
                                                <div className="fs-3 fw-bold text-info">
                                                    {warranty.avg_failure_hours != null
                                                        ? Number(warranty.avg_failure_hours).toFixed(0)
                                                        : '—'}
                                                </div>
                                                <div className="small text-muted">平均故障時數</div>
                                            </div>
                                        </Col>
                                    </Row>

                                    {warranty.by_product && warranty.by_product.length > 0 && (
                                        <>
                                            <h6 className="fw-semibold mb-3">料號別保固 / 故障件數</h6>
                                            <Bar
                                                data={{
                                                    labels: warranty.by_product.slice(0, 10).map(d => d.product_no),
                                                    datasets: [{
                                                        label: '件數',
                                                        data: warranty.by_product.slice(0, 10).map(d => d.total),
                                                        backgroundColor: CHART_COLORS[2],
                                                    }],
                                                }}
                                                options={{
                                                    responsive: true,
                                                    plugins: { legend: { display: false } },
                                                    scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
                                                }}
                                                height={60}
                                            />
                                        </>
                                    )}
                                </Card.Body>
                            </Card>
                        </Col>
                    )}
                </Row>
            )}
        </Container>
    );
};

export default ComplaintStatsPage;
