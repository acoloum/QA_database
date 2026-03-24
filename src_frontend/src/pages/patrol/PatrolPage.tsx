
import { useState } from 'react';
import PatrolModal from '../../components/patrol/PatrolModal';
import PatrolCharts from '../../components/patrol/PatrolCharts';
import { Button, Form, Card, Row, Col, Table, Badge, Pagination } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { usePatrolList, usePatrolOptions, useDeletePatrol, useImportPatrol } from '../../hooks/usePatrol';
import api from '../../services/api';

const PatrolPage = () => {
    const navigate = useNavigate();

    // Filters
    const [page, setPage] = useState(1);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [machine, setMachine] = useState('');
    const [operator, setOperator] = useState('');
    const [customer, setCustomer] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');

    // Hooks
    const { data: optionsData } = usePatrolOptions();
    const machines = optionsData?.machines || [];
    const operators = optionsData?.operators || [];
    const customers = optionsData?.customers || [];

    const { data: patrolData, isLoading } = usePatrolList({
        page,
        per_page: 20,
        s_date: startDate,
        e_date: endDate,
        m_id: machine,
        op_id: operator,
        cust_id: customer,
        mat: material,
        spec: spec
    });

    const deleteMutation = useDeletePatrol();

    // We can reuse the shipping import modal if we pass a different mutation to it? 
    // Actually the ImportModal handles its own upload logic internally via api call.
    // But we should use the new ImportModal which uses useImportShipping... wait.
    // The ImportModal I refactored was for Shipping (`src/components/shipping/ImportModal.tsx`).
    // PatrolPage imports `../../components/shipping/ImportModal`.
    // If I want to reuse it, I should probably make it generic or create a PatrolImportModal.
    // However, the current `ImportModal` in shipping hardcodes `useImportShipping`.
    // So I should probably create a specific `ImportModal` for Patrol or make the existing one generic.
    // For now, I'll create a local implementation or use a clone to avoid breaking Shipping.
    // Actually, looking at PatrolPage imports: `import ImportModal from '../../components/shipping/ImportModal';`
    // This connects to the Shipping import logic! That's a bug in the original code or a reused component that was generic before I refactored it.
    // Before my refactor, ImportModal took `api.post('/import')`... but which import?
    // The previous ImportModal had `/import` hardcoded.
    // If ShippingPage used it, it would hit the base URL + `/import`?
    // Wait, `api.ts` usually has a baseURL.
    // If `PatrolPage` was using `components/shipping/ImportModal`, and that modal hit `/import`, it might have been hitting the wrong endpoint if not careful?
    // Actually `routes/shipping.py` has `/api/import` and `routes/patrol.py` has `/api/patrol/import`.
    // If the old `ImportModal` used `/import`, it likely hit `/api/import` (Shipping).
    // So PatrolPage was likely importing into Shipping table? That sounds like a bug I should fix.
    // I should create a dedicated ImportModal for Patrol or make it accept a mutation.

    // Let's create a specialized ImportModal for Patrol inside PatrolPage or a separate file.
    // Since I can't easily change the shared one without checking all usages (ShippingPage uses it), 
    // and I just hardcoded `useImportShipping` in it, I should definitely NOT use `components/shipping/ImportModal` for Patrol.

    // SPC 圖表的測量項目與位置（與匯出共用）
    const [statsItem, setStatsItem] = useState('外徑');
    const [statsPos, setStatsPos] = useState('前段');

    const [showModal, setShowModal] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    const handleSearch = () => {
        setPage(1);
    };

    const handleExport = () => {
        const token = localStorage.getItem('authToken');
        // 僅匯出原始檢驗數據，不含 SPC 分析
        const qs = new URLSearchParams({
            s_date: startDate,
            e_date: endDate,
            m_id: machine,
            op_id: operator,
            cust_id: customer,
            mat: material,
            spec: spec,
            token: token || ''
        });
        window.location.href = `${api.defaults.baseURL}/patrol/export?${qs.toString()}`;
    };

    const handleDelete = async (id: number) => {
        if (window.confirm('確定要刪除此筆資料嗎？')) {
            deleteMutation.mutate(id);
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

    const data = patrolData?.data || [];
    const totalPages = patrolData?.pages || 1;

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
                            <Form.Label>客戶名稱</Form.Label>
                            <Form.Select value={customer} onChange={e => setCustomer(e.target.value)}>
                                <option value="">所有客戶</option>
                                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
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
                customer={customer}
                material={material}
                spec={spec}
                startDate={startDate}
                endDate={endDate}
                onEditPoint={handleEdit}
                statsItem={statsItem}
                statsPos={statsPos}
                onItemChange={setStatsItem}
                onPosChange={setStatsPos}
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
                                <th>客戶</th>
                                <th>材質</th>
                                <th>規格</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={8} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={8} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map(item => (
                                    <tr key={item.id}>
                                        <td>{item.id}</td>
                                        <td>{item.date}</td>
                                        <td><Badge bg="info">{item.m_name || item.machine_name || '-'}</Badge></td>
                                        <td>{item.op_name || item.operator_name || '-'}</td>
                                        <td>{item.cust_name || '-'}</td>
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
                handleClose={() => { setShowModal(false); setEditId(null); }}
                onSuccess={() => { }} // React Query handles invalidation
                editId={editId}
            />

            <PatrolImportModal
                show={showImportModal}
                handleClose={() => setShowImportModal(false)}
                onSuccess={() => { }} // React Query handles invalidation
            />

        </div>
    );
};

// Internal component for import to avoid modifying shared one for now
import { Modal as BSModal, Alert } from 'react-bootstrap';
import { useRef } from 'react';

const PatrolImportModal = ({ show, handleClose, onSuccess }: { show: boolean, handleClose: () => void, onSuccess: () => void }) => {
    const [file, setFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const importMutation = useImportPatrol();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
            setError(null);
        }
    };

    const handleUpload = async () => {
        if (!file) {
            setError('請選擇檔案');
            return;
        }
        setError(null);
        try {
            await importMutation.mutateAsync(file);
            onSuccess();
            handleClose();
            setFile(null);
            if (fileInputRef.current) fileInputRef.current.value = '';
        } catch (err: unknown) {
            const error = err as { response?: { data?: { error?: string } } };
            setError(error.response?.data?.error || '匯入失敗');
        }
    };

    return (
        <BSModal show={show} onHide={handleClose}>
            <BSModal.Header closeButton><BSModal.Title>匯入巡檢數據</BSModal.Title></BSModal.Header>
            <BSModal.Body>
                <Alert variant="info">請上傳符合格式的 Excel 檔案。</Alert>
                <Form.Group className="mb-3">
                    <Form.Label>選擇檔案</Form.Label>
                    <Form.Control type="file" accept=".xlsx,.xls" onChange={handleFileChange} ref={fileInputRef} />
                </Form.Group>
                {error && <Alert variant="danger">{error}</Alert>}
                {importMutation.isError && !error && <Alert variant="danger">匯入發生錯誤</Alert>}
            </BSModal.Body>
            <BSModal.Footer>
                <Button variant="secondary" onClick={handleClose} disabled={importMutation.isPending}>取消</Button>
                <Button variant="success" onClick={handleUpload} disabled={!file || importMutation.isPending}>
                    {importMutation.isPending ? '匯入中...' : '開始匯入'}
                </Button>
            </BSModal.Footer>
        </BSModal>
    );
};

export default PatrolPage;
