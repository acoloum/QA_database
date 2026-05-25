import { Card, Badge, Table, Spinner } from 'react-bootstrap';
import { useOverdueCapas, CAPA_SEVERITY_VARIANT } from '../../hooks/useCapa';

const OverdueCapaWidget = () => {
    const { data: capas = [], isLoading } = useOverdueCapas();

    return (
        <Card className="h-100 shadow-sm">
            <Card.Header className="d-flex justify-content-between align-items-center py-2">
                <span className="fw-semibold">
                    <i className="bi bi-clock-history me-2 text-danger" />
                    逾期 CAPA
                </span>
                <Badge bg={capas.length > 0 ? 'danger' : 'success'}>
                    {capas.length} 筆
                </Badge>
            </Card.Header>

            <Card.Body className="p-0" style={{ maxHeight: '280px', overflowY: 'auto' }}>
                {isLoading ? (
                    <div className="text-center py-4">
                        <Spinner animation="border" size="sm" className="me-2" />
                        <span className="text-muted small">載入中…</span>
                    </div>
                ) : capas.length === 0 ? (
                    <div className="text-center py-4 text-muted small">
                        <i className="bi bi-check-circle fs-3 d-block mb-2 text-success" />
                        目前沒有逾期 CAPA
                    </div>
                ) : (
                    <Table size="sm" hover className="mb-0">
                        <thead className="table-light sticky-top">
                            <tr>
                                <th>單號</th>
                                <th>嚴重度</th>
                                <th>客戶要求結案日</th>
                                <th>進度</th>
                            </tr>
                        </thead>
                        <tbody>
                            {capas.map(c => (
                                <tr key={c.id} className="table-danger">
                                    <td className="small fw-semibold">{c.no}</td>
                                    <td>
                                        {c.severity && (
                                            <Badge bg={CAPA_SEVERITY_VARIANT[c.severity] ?? 'secondary'}>
                                                {c.severity}
                                            </Badge>
                                        )}
                                    </td>
                                    <td className="small text-danger fw-semibold">{c.deadline ?? '—'}</td>
                                    <td className="small">{c.progress_percent}%</td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Card.Body>

            <Card.Footer className="py-2 text-end">
                <a href="/capa" className="small text-muted text-decoration-none">
                    查看全部 CAPA →
                </a>
            </Card.Footer>
        </Card>
    );
};

export default OverdueCapaWidget;
