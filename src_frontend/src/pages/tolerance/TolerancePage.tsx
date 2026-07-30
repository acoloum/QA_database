import { useState } from 'react';
import { Button, Card, Table, Form, Row, Col, Pagination, Badge } from 'react-bootstrap';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import ToleranceModal from '../../components/tolerance/ToleranceModal';
import ViewToleranceModal from '../../components/tolerance/ViewToleranceModal';
import { useToleranceSearch, useToleranceOptions, useDeleteTolerance, useImportTolerance, useExportToleranceData } from '../../hooks/useTolerance';
import type { ToleranceStandard, Vendor } from '../../types';
import { useNavigate } from 'react-router';

const TolerancePage = () => {
    const navigate = useNavigate();
    const [page, setPage] = useState(1);

    // Filters
    const [material, setMaterial] = useState('');
    const [vendor, setVendor] = useState('');
    const [spec, setSpec] = useState('');

    // Hooks
    const { data: vendors = [] } = useToleranceOptions();

    const searchParams = {
        page,
        page_size: 20,
        material,
        vendor_id: vendor,
        spec
    };

    const { data: searchResult, isLoading, refetch } = useToleranceSearch(searchParams);
    const deleteMutation = useDeleteTolerance();
    const importMutation = useImportTolerance();
    const exportToleranceData = useExportToleranceData();

    // Modal
    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    // View Modal
    const [showViewModal, setShowViewModal] = useState(false);
    const [viewId, setViewId] = useState<number | null>(null);

    const handleSearch = () => {
        setPage(1);
        refetch();
    };

    const handleDelete = async (id: number) => {
        setConfirmAction({
            title: '刪除公差資料',
            message: '確定要刪除此筆公差資料嗎？此操作無法復原。',
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => deleteMutation.mutateAsync(id),
        });
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

    const handleExport = () => {
        exportToleranceData.mutate(searchParams);
    };

    const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        importMutation.mutate(file);
        e.target.value = ''; // Reset input
    };

    // 後端回傳中文欄位名，需轉換為前端使用的英文欄位
    const data = searchResult?.data?.map((item: Record<string, unknown>) => ({
        id: item['識別碼'] as number,
        material: item['材質'] as string,
        spec: item['規格'] as string,
        vendor_name: item['廠商名稱'] as string,
        create_date: item['建立日期'] as string,
        remark: item['備註'] as string
    })) || [];

    const totalPages = searchResult?.total_pages || 1;

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold"><i className="bi bi-rulers"></i> 廠商公差管理系統</h2>
                <div>
                    <Button className="btn-back-home me-2" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </Button>
                    <input type="file" id="importFile" hidden accept=".xlsx,.xls" onChange={handleImport} />
                    <Button variant="outline-success" className="me-2" onClick={handleExport} disabled={exportToleranceData.isPending}>
                        <i className="bi bi-download"></i> {exportToleranceData.isPending ? '匯出中...' : '匯出 Excel'}
                    </Button>
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
                                {vendors.map((v: Vendor) => <option key={v.id} value={v.id}>{v.name}</option>)}
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
                            {isLoading ? (
                                <tr><td colSpan={6} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={6} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map((item: ToleranceStandard) => (
                                    <tr key={item.id}>
                                        <td>{item.id}</td>
                                        <td><Badge bg="primary">{item.material}</Badge></td>
                                        <td>{item.spec || '-'}</td>
                                        <td>{item.vendor_name || '-'}</td>
                                        <td>{item.create_date?.substring(0, 10) || '-'}</td>
                                        <td>
                                            <Button variant="outline-info" size="sm" className="me-2" style={{ fontSize: '14px' }} onClick={() => handleView(item.id)}>查看</Button>
                                            <Button variant="outline-primary" size="sm" className="me-2" style={{ fontSize: '14px' }} onClick={() => handleEdit(item.id)}>編輯</Button>
                                            <Button variant="outline-danger" size="sm" style={{ fontSize: '14px' }} onClick={() => handleDelete(item.id)}>刪除</Button>
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
                // onSuccess is no longer needed to reload data manually, query invalidation handles it.
                // But keeping prop interface might be needed until modal is refactored.
                // Assuming modal will call onSuccess which can be empty or just close modal.
                onSuccess={() => { }}
                editId={editId}
                vendors={vendors}
            />

            <ViewToleranceModal
                show={showViewModal}
                handleClose={() => setShowViewModal(false)}
                viewId={viewId}
            />
            <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </div>
    );
};

export default TolerancePage;
