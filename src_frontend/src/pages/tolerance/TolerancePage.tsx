import { useState, useEffect } from 'react';
import { Button, Card, Table, Form, Row, Col, Pagination, Badge } from 'react-bootstrap';
import api from '../../services/api';
import ToleranceModal from '../../components/tolerance/ToleranceModal';
import ViewToleranceModal from '../../components/tolerance/ViewToleranceModal';

interface ToleranceData {
    id: number;
    material: string;
    spec: string;
    vendor_name: string;
    create_date: string;
    remark?: string;
}

import { useNavigate } from 'react-router-dom';

const TolerancePage = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<ToleranceData[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    // const [totalRecords, setTotalRecords] = useState(0); // Unused

    // Filters
    const [material, setMaterial] = useState('');
    const [vendor, setVendor] = useState('');
    const [spec, setSpec] = useState('');
    const [vendors, setVendors] = useState<any[]>([]);

    // Modal
    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    // View Modal
    const [showViewModal, setShowViewModal] = useState(false);
    const [viewId, setViewId] = useState<number | null>(null);

    useEffect(() => {
        loadOptions();
    }, []);

    useEffect(() => {
        loadData();
    }, [page]);

    const loadOptions = async () => {
        try {
            const res = await api.get('/tolerance/options');
            setVendors(res.data.vendors || []);
        } catch (error) {
            console.error("Failed to load options", error);
        }
    };

    const loadData = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (material) params.append('material', material);
            if (vendor) params.append('vendor_id', vendor);
            if (spec) params.append('spec', spec);
            params.append('page', page.toString());
            params.append('page_size', '20');

            const res = await api.get(`/tolerance/search?${params.toString()}`);
            const result = res.data;

            if (result.success) {
                const mapped = result.data.map((item: any) => ({
                    id: item.識別碼,
                    material: item.材質,
                    spec: item.規格,
                    vendor_name: item.廠商名稱,
                    create_date: item.建立日期,
                    remark: item.備註
                }));
                setData(mapped);
                setTotalPages(result.total_pages);
                // setTotalRecords(result.total);
            }
        } catch (error) {
            console.error("Failed to load tolerance data", error);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = () => {
        setPage(1);
        loadData();
    };

    const handleDelete = async (id: number) => {
        if (!window.confirm(`確定要刪除此筆公差資料嗎？此操作無法復原！`)) return;
        try {
            const res = await api.post(`/tolerance/delete/${id}`);
            if (res.data.success) {
                alert('刪除成功');
                loadData();
            } else {
                alert('刪除失敗');
            }
        } catch (error) {
            console.error("Delete failed", error);
            alert('刪除失敗');
        }
    };

    const handleEdit = (id: number) => {
        setEditId(id);
        setShowModal(true);
    };

    const handleView = (id: number) => {
        setViewId(id);
        setShowViewModal(true);
    };

    const handleAdd = () => {
        setEditId(null);
        setShowModal(true);
    };

    const handleExport = async () => {
        try {
            const params = new URLSearchParams();
            if (material) params.append('material', material);
            if (vendor) params.append('vendor_id', vendor);
            if (spec) params.append('spec', spec);

            // Get token
            const token = localStorage.getItem('authToken');
            const url = `${api.defaults.baseURL?.replace('/api', '')}/api/tolerance/export?${params.toString()}&token=${token}`;
            window.location.href = url;
        } catch (error) {
            console.error("Export failed", error);
            alert('匯出失敗');
        }
    };

    const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await api.post('/tolerance/import', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            if (res.data.success) {
                alert(res.data.message || '匯入成功');
                loadData();
            } else {
                alert(res.data.error || '匯入失敗');
            }
        } catch (error) {
            console.error("Import failed", error);
            alert('匯入失敗');
        }
        e.target.value = ''; // Reset input
    };

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold"><i className="bi bi-rulers"></i> 廠商公差管理系統</h2>
                <div>
                    <Button className="btn-back-home me-2" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </Button>
                    <input type="file" id="importFile" hidden accept=".xlsx,.xls" onChange={handleImport} />
                    <Button variant="outline-success" className="me-2" onClick={handleExport}><i className="bi bi-download"></i> 匯出 Excel</Button>
                    <Button variant="outline-primary" className="me-2" onClick={() => document.getElementById('importFile')?.click()}><i className="bi bi-upload"></i> 匯入 Excel</Button>
                    <Button variant="warning" className="text-white" onClick={handleAdd}><i className="bi bi-plus-lg"></i> 新增公差資料</Button>
                </div>
            </div>

            <Card className="shadow-sm mb-4">
                <Card.Body>
                    <Row className="g-3 align-items-end">
                        <Col md={3}>
                            <Form.Label>材質</Form.Label>
                            <Form.Control value={material} onChange={e => setMaterial(e.target.value)} placeholder="請輸入材質" />
                        </Col>
                        <Col md={3}>
                            <Form.Label>廠商</Form.Label>
                            <Form.Select value={vendor} onChange={e => setVendor(e.target.value)}>
                                <option value="">-- 全部廠商 --</option>
                                {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                            </Form.Select>
                        </Col>
                        <Col md={3}>
                            <Form.Label>規格</Form.Label>
                            <Form.Control value={spec} onChange={e => setSpec(e.target.value)} placeholder="請輸入規格" />
                        </Col>
                        <Col md={3}>
                            <Button variant="primary" className="w-100" onClick={handleSearch}><i className="bi bi-search"></i> 查詢</Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            <Card className="shadow-sm">
                <Card.Body>
                    <Table hover responsive className="align-middle">
                        <thead className="table-light">
                            <tr>
                                <th>ID</th>
                                <th>材質</th>
                                <th>規格</th>
                                <th>廠商</th>
                                <th>建立日期</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr><td colSpan={6} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={6} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map(item => (
                                    <tr key={item.id}>
                                        <td>{item.id}</td>
                                        <td><Badge bg="primary">{item.material}</Badge></td>
                                        <td>{item.spec || '-'}</td>
                                        <td>{item.vendor_name || '-'}</td>
                                        <td>{item.create_date?.substring(0, 10) || '-'}</td>
                                        <td>
                                            <Button variant="outline-info" size="sm" className="me-2" onClick={() => handleView(item.id)}>查看</Button>
                                            <Button variant="outline-primary" size="sm" className="me-2" onClick={() => handleEdit(item.id)}>編輯</Button>
                                            <Button variant="outline-danger" size="sm" onClick={() => handleDelete(item.id)}>刪除</Button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>

                    {totalPages > 1 && (
                        <div className="d-flex justify-content-center mt-3">
                            <Pagination>
                                <Pagination.First onClick={() => setPage(1)} disabled={page === 1} />
                                <Pagination.Prev onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} />
                                <Pagination.Item active>{page} / {totalPages}</Pagination.Item>
                                <Pagination.Next onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} />
                                <Pagination.Last onClick={() => setPage(totalPages)} disabled={page === totalPages} />
                            </Pagination>
                        </div>
                    )}
                </Card.Body>
            </Card>

            <ToleranceModal
                show={showModal}
                handleClose={() => setShowModal(false)}
                onSuccess={loadData}
                editId={editId}
                vendors={vendors}
            />

            <ViewToleranceModal
                show={showViewModal}
                handleClose={() => setShowViewModal(false)}
                viewId={viewId}
            />
        </div>
    );
};

export default TolerancePage;
