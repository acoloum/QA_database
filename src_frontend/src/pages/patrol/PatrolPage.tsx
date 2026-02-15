import { useState, useEffect } from 'react';
import api from '../../services/api';
import type { PatrolInspection } from '../../types';
import PatrolModal from '../../components/patrol/PatrolModal';
import ImportModal from '../../components/shipping/ImportModal'; // Reuse import modal
import PatrolCharts from '../../components/patrol/PatrolCharts';
import { Button, Form, Card, Row, Col, Table, Badge, Pagination } from 'react-bootstrap';

import { useNavigate } from 'react-router-dom';

const PatrolPage = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<PatrolInspection[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);

    // Filters
    const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0]);
    const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0]);
    const [machine, setMachine] = useState('');
    const [operator, setOperator] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');

    // Options
    const [machines, setMachines] = useState<{ id: number, name: string }[]>([]);
    const [operators, setOperators] = useState<{ id: number, name: string }[]>([]);

    // Modal State
    const [showModal, setShowModal] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    useEffect(() => {
        fetchOptions();
    }, []);

    useEffect(() => {
        loadData();
    }, [page]); // Reload when page changes

    const fetchOptions = async () => {
        try {
            const res = await api.get('/patrol/options');
            setMachines(res.data.machines);
            setOperators(res.data.operators);
        } catch (error) {
            console.error("Failed to load options", error);
        }
    };

    const loadData = async () => {
        setLoading(true);
        try {
            const params = {
                page,
                per_page: 20,
                s_date: startDate,
                e_date: endDate,
                m_id: machine,
                op_id: operator,
                mat: material,
                spec: spec
            };
            const res = await api.get('/patrol/history', { params });
            setData(res.data.data);
            setTotalPages(res.data.pages);
        } catch (error) {
            console.error("Failed to load data", error);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = () => {
        setPage(1);
        loadData();
    };

    const handleExport = () => {
        const token = localStorage.getItem('authToken');
        const qs = new URLSearchParams({
            s_date: startDate,
            e_date: endDate,
            m_id: machine,
            op_id: operator,
            mat: material,
            spec: spec,
            token: token || ''
        });
        window.location.href = `${api.defaults.baseURL}/patrol/export?${qs.toString()}`;
    };

    const handleDelete = async (id: number) => {
        if (window.confirm('確定要刪除此筆資料嗎？')) {
            try {
                await api.post('/patrol/delete', { id });
                loadData();
            } catch (error) {
                console.error("Delete failed", error);
                alert('刪除失敗');
            }
        }
    };

    const handleAdd = () => {
        setEditId(null);
        setShowModal(true);
    };

    const handleEdit = (id: number) => {
        setEditId(id);
        setShowModal(true);
    };

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold"><i className="bi bi-shield-check"></i> 現場巡檢管理</h2>
                <div>
                    <button className="btn btn-back-home me-2" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </button>
                    <button className="btn btn-outline-success me-2" onClick={handleExport}>
                        <i className="bi bi-file-earmark-excel"></i> 匯出 Excel
                    </button>
                    <button className="btn btn-outline-info me-2" onClick={() => setShowImportModal(true)}>
                        <i className="bi bi-upload"></i> 匯入 Excel
                    </button>
                    <button className="btn btn-primary" onClick={handleAdd}>
                        <i className="bi bi-plus-lg"></i> 新增巡檢
                    </button>
                </div>
            </div>

            {/* Filter Section */}
            <Card className="mb-4 shadow-sm">
                <Card.Body className="bg-light">
                    <Row className="g-3">
                        <Col md={2}>
                            <Form.Label>開始日期</Form.Label>
                            <Form.Control type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
                        </Col>
                        <Col md={2}>
                            <Form.Label>結束日期</Form.Label>
                            <Form.Control type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
                        </Col>
                        <Col md={2}>
                            <Form.Label>機台</Form.Label>
                            <Form.Select value={machine} onChange={e => setMachine(e.target.value)}>
                                <option value="">所有機台</option>
                                {machines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                            </Form.Select>
                        </Col>
                        <Col md={2}>
                            <Form.Label>主機手</Form.Label>
                            <Form.Select value={operator} onChange={e => setOperator(e.target.value)}>
                                <option value="">所有人員</option>
                                {operators.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                            </Form.Select>
                        </Col>
                        <Col md={2}>
                            <Form.Label>材質</Form.Label>
                            <Form.Control type="text" placeholder="材質" value={material} onChange={e => setMaterial(e.target.value)} />
                        </Col>
                        <Col md={2}>
                            <Form.Label>規格</Form.Label>
                            <Form.Control type="text" placeholder="規格" value={spec} onChange={e => setSpec(e.target.value)} />
                        </Col>
                        <Col md={12} className="text-end">
                            <Button variant="primary" onClick={handleSearch} className="px-4">
                                <i className="bi bi-search"></i> 查詢
                            </Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            {/* Charts Section */}
            <PatrolCharts
                machine={machine}
                operator={operator}
                material={material}
                spec={spec}
                startDate={startDate}
                endDate={endDate}
            />

            {/* Data Table */}
            <Card className="shadow-sm">
                <Card.Body>
                    <Table hover responsive className="align-middle">
                        <thead className="table-dark">
                            <tr>
                                <th>ID</th>
                                <th>日期</th>
                                <th>機台</th>
                                <th>主機手</th>
                                <th>材質</th>
                                <th>規格</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr><td colSpan={7} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={7} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map(item => (
                                    <tr key={item.id}>
                                        <td>{item.id}</td>
                                        <td>{item.date}</td>
                                        <td><Badge bg="info">{item.m_name || item.machine_name || '-'}</Badge></td>
                                        <td>{item.op_name || item.operator_name || '-'}</td>
                                        <td>{item.mat || item.material || '-'}</td>
                                        <td>{item.spec}</td>
                                        <td>
                                            <Button variant="outline-primary" size="sm" className="me-2" onClick={() => handleEdit(item.id)}>
                                                <i className="bi bi-pencil"></i> 編輯
                                            </Button>
                                            <Button variant="outline-danger" size="sm" onClick={() => handleDelete(item.id)}>
                                                <i className="bi bi-trash"></i> 刪除
                                            </Button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="d-flex justify-content-center mt-3">
                            <Pagination>
                                <Pagination.First onClick={() => setPage(1)} disabled={page === 1} />
                                <Pagination.Prev onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} />
                                {[...Array(totalPages)].map((_, idx) => (
                                    <Pagination.Item key={idx + 1} active={idx + 1 === page} onClick={() => setPage(idx + 1)}>
                                        {idx + 1}
                                    </Pagination.Item>
                                ))}
                                <Pagination.Next onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} />
                                <Pagination.Last onClick={() => setPage(totalPages)} disabled={page === totalPages} />
                            </Pagination>
                        </div>
                    )}
                </Card.Body>
            </Card>

            <PatrolModal
                show={showModal}
                handleClose={() => setShowModal(false)}
                onSuccess={loadData}
                editId={editId}
            />

            <ImportModal
                show={showImportModal}
                handleClose={() => setShowImportModal(false)}
                onSuccess={loadData}
            />
        </div>
    );
};

export default PatrolPage;
