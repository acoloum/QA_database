import { useState } from 'react';
import { Button, Card, Table, Form, Row, Col, Pagination } from 'react-bootstrap';
import {
    useExtrusionToleranceList,
    useDeleteExtrusionTolerance,
    type ExtrusionToleranceItem,
} from '../../hooks/useExtrusionTolerance';
import ExtrusionToleranceModal from '../../components/extrusion-tolerance/ExtrusionToleranceModal';
import ViewExtrusionToleranceModal from '../../components/extrusion-tolerance/ViewExtrusionToleranceModal';

const ExtrusionTolerancePage = () => {
    const [page, setPage] = useState(1);
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');

    const { data: result, isLoading, refetch } = useExtrusionToleranceList({
        page, page_size: 20, material, spec,
    });
    const deleteMutation = useDeleteExtrusionTolerance();

    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [showViewModal, setShowViewModal] = useState(false);
    const [viewId, setViewId] = useState<number | null>(null);

    const handleSearch = () => { setPage(1); refetch(); };
    const handleAdd = () => { setEditId(null); setShowModal(true); };
    const handleEdit = (id: number) => { setEditId(id); setShowModal(true); };
    const handleView = (id: number) => { setViewId(id); setShowViewModal(true); };
    const handleDelete = (id: number) => {
        if (!window.confirm('確定要刪除此筆擠壓公差資料？')) return;
        deleteMutation.mutate(id);
    };

    const rows: ExtrusionToleranceItem[] = result?.data || [];
    const totalPages = result?.total_pages || 1;

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h4>擠壓公差管理</h4>
                <Button variant="primary" size="sm" onClick={handleAdd}>+ 新增</Button>
            </div>

            <Card className="mb-3">
                <Card.Body>
                    <Row className="g-2 align-items-end">
                        <Col md={3}>
                            <Form.Label>材質</Form.Label>
                            <Form.Control size="sm" value={material} onChange={(e) => setMaterial(e.target.value)} placeholder="模糊搜尋" />
                        </Col>
                        <Col md={3}>
                            <Form.Label>規格</Form.Label>
                            <Form.Control size="sm" value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="如 62.5*2.3" />
                        </Col>
                        <Col md={2}>
                            <Button size="sm" onClick={handleSearch}>查詢</Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            <Card>
                <Card.Body>
                    {isLoading ? (
                        <p>載入中…</p>
                    ) : (
                        <Table bordered hover size="sm">
                            <thead className="table-secondary">
                                <tr>
                                    <th>材質</th>
                                    <th>規格</th>
                                    <th>備註</th>
                                    <th>建立日期</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.length === 0 ? (
                                    <tr><td colSpan={5} className="text-center text-muted">無資料</td></tr>
                                ) : rows.map((r) => (
                                    <tr key={r.識別碼}>
                                        <td>{r.材質}</td>
                                        <td>{r.規格 || <span className="text-muted">（通用）</span>}</td>
                                        <td>{r.備註}</td>
                                        <td>{r.建立日期}</td>
                                        <td>
                                            <Button size="sm" variant="outline-info" className="me-1" onClick={() => handleView(r.識別碼)}>查看</Button>
                                            <Button size="sm" variant="outline-primary" className="me-1" onClick={() => handleEdit(r.識別碼)}>編輯</Button>
                                            <Button size="sm" variant="outline-danger" onClick={() => handleDelete(r.識別碼)}>刪除</Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    )}

                    {totalPages > 1 && (
                        <Pagination size="sm">
                            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                                <Pagination.Item key={p} active={p === page} onClick={() => setPage(p)}>{p}</Pagination.Item>
                            ))}
                        </Pagination>
                    )}
                </Card.Body>
            </Card>

            <ExtrusionToleranceModal
                show={showModal}
                editId={editId}
                onClose={() => setShowModal(false)}
                onSuccess={() => refetch()}
            />
            <ViewExtrusionToleranceModal
                show={showViewModal}
                id={viewId}
                onClose={() => setShowViewModal(false)}
            />
        </div>
    );
};

export default ExtrusionTolerancePage;
