import { Card, Badge, Table, Spinner } from 'react-bootstrap';
import { useOverdueComplaints, COMPLAINT_TYPE_LABELS } from '../../hooks/useComplaint';

const OverdueComplaintWidget = () => {
    const { data: items = [], isLoading } = useOverdueComplaints();

    return (
        <Card className="h-100 shadow-sm">
            <Card.Header className="d-flex justify-content-between align-items-center py-2">
                <span className="fw-semibold">
                    <i className="bi bi-megaphone me-2 text-warning" />
                    逾期客訴
                </span>
                <Badge bg={items.length > 0 ? 'warning' : 'success'} text={items.length > 0 ? 'dark' : undefined}>
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
                        目前沒有逾期客訴
                    </div>
                ) : (
                    <Table size="sm" hover className="mb-0">
                        <thead className="table-light sticky-top">
                            <tr>
                                <th>單號</th>
                                <th>客戶</th>
                                <th>類型</th>
                                <th>期限</th>
                                <th>逾期</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.map(c => (
                                <tr key={c.id} className="table-warning">
                                    <td className="small fw-semibold">{c.complaint_no}</td>
                                    <td className="small">{c.customer}</td>
                                    <td className="small">
                                        <Badge bg="light" text="dark">
                                            {COMPLAINT_TYPE_LABELS[c.complaint_type] ?? c.complaint_type}
                                        </Badge>
                                    </td>
                                    <td className="small text-danger fw-semibold">
                                        {c.initial_reply_deadline ?? '—'}
                                    </td>
                                    <td className="small text-danger">
                                        +{c.overdue_days ?? 0} 天
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Card.Body>

            <Card.Footer className="py-2 text-end">
                <a href="/complaints" className="small text-muted text-decoration-none">
                    查看全部客訴 →
                </a>
            </Card.Footer>
        </Card>
    );
};

export default OverdueComplaintWidget;
