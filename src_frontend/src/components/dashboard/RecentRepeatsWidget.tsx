import { Card, Badge, Table, Spinner } from 'react-bootstrap';
import { useRecentRepeats } from '../../hooks/useComplaint';

const RecentRepeatsWidget = () => {
    const { data: items = [], isLoading } = useRecentRepeats(30);

    return (
        <Card className="h-100 shadow-sm">
            <Card.Header className="d-flex justify-content-between align-items-center py-2">
                <span className="fw-semibold">
                    <i className="bi bi-arrow-repeat me-2 text-danger" />
                    近 30 天重複客訴
                </span>
                <Badge bg={items.length > 0 ? 'danger' : 'success'}>
                    {items.length} 筆
                </Badge>
            </Card.Header>

            <Card.Body className="p-0" style={{ maxHeight: '280px', overflowY: 'auto' }}>
                {isLoading ? (
                    <div className="text-center py-4">
                        <Spinner animation="border" size="sm" className="me-2" />
                        <span className="text-muted small">載入中…</span>
                    </div>
                ) : items.length === 0 ? (
                    <div className="text-center py-4 text-muted small">
                        <i className="bi bi-check-circle fs-3 d-block mb-2 text-success" />
                        近 30 天無重複客訴
                    </div>
                ) : (
                    <Table size="sm" hover className="mb-0">
                        <thead className="table-light sticky-top">
                            <tr>
                                <th>單號</th>
                                <th>客戶</th>
                                <th>料號</th>
                                <th>日期</th>
                                <th>歷史筆數</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map(c => (
                                <tr key={c.id}>
                                    <td className="small fw-semibold">{c.complaint_no}</td>
                                    <td className="small">{c.customer}</td>
                                    <td className="small">{c.product_no}</td>
                                    <td className="small">{c.complaint_date}</td>
                                    <td className="small">
                                        <Badge bg="danger">
                                            {(c.repeat_refs?.length ?? 0) + 1} 筆
                                        </Badge>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Card.Body>

            <Card.Footer className="py-2 text-end">
                <a href="/complaints?is_repeat=true" className="small text-muted text-decoration-none">
                    查看全部重複客訴 →
                </a>
            </Card.Footer>
        </Card>
    );
};

export default RecentRepeatsWidget;
