import { useState } from 'react';
import { Button, Card, Table, Form, Row, Col } from 'react-bootstrap';
import {
    useExtrusionToleranceList,
    useDeleteExtrusionTolerance,
    type ExtrusionToleranceItem,
} from '../../hooks/useExtrusionTolerance';
import ExtrusionToleranceModal from '../../components/extrusion-tolerance/ExtrusionToleranceModal';
import ViewExtrusionToleranceModal from '../../components/extrusion-tolerance/ViewExtrusionToleranceModal';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import PaginationBar from '../../components/common/PaginationBar';
import PermissionAction from '../../components/PermissionAction';
import QueryErrorAlert from '../../components/common/QueryErrorAlert';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';

const ExtrusionTolerancePage = () => {
    const [page, setPage] = useState(1);
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [vendor, setVendor] = useState('');

    // 搜尋欄位防抖：輸入框即時顯示，停止輸入後才送進查詢鍵，避免每個按鍵都打一次 API
    const debouncedMaterial = useDebouncedValue(material);
    const debouncedSpec = useDebouncedValue(spec);
    const debouncedVendor = useDebouncedValue(vendor);

    const { data: result, isLoading, isError, refetch } = useExtrusionToleranceList({
        page, page_size: 20, material: debouncedMaterial, spec: debouncedSpec, vendor: debouncedVendor,
    });
    const deleteMutation = useDeleteExtrusionTolerance();

    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [showViewModal, setShowViewModal] = useState(false);
    const [viewId, setViewId] = useState<number | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    // 篩選條件一變就回到第 1 頁，否則停在後面的頁碼可能查不到資料
    const handleFilterChange = (setter: (value: string) => void) =>
        (e: React.ChangeEvent<HTMLInputElement>) => { setter(e.target.value); setPage(1); };
    const handleAdd = () => { setEditId(null); setShowModal(true); };
    const handleEdit = (id: number) => { setEditId(id); setShowModal(true); };
    const handleView = (id: number) => { setViewId(id); setShowViewModal(true); };
    const handleDelete = (id: number) => {
        setConfirmAction({
            title: '刪除擠壓公差',
            message: '確定要刪除此筆擠壓公差資料？',
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => deleteMutation.mutateAsync(id),
        });
    };

    const rows: ExtrusionToleranceItem[] = result?.data || [];
    const totalPages = result?.total_pages || 1;

    return (
        <div>
            <QueryErrorAlert show={isError} onRetry={refetch} />
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h4>擠壓公差管理</h4>
                <PermissionAction permission="tolerance.manage"><Button variant="primary" size="sm" onClick={handleAdd}>+ 新增</Button></PermissionAction>
            </div>

            <Card className="mb-3">
                <Card.Body>
                    <Row className="g-2 align-items-end">
                        <Col md={4}>
                            <Form.Label>材質</Form.Label>
                            <Form.Control size="sm" value={material} onChange={handleFilterChange(setMaterial)} placeholder="模糊搜尋" />
                        </Col>
                        <Col md={4}>
                            <Form.Label>規格</Form.Label>
                            <Form.Control size="sm" value={spec} onChange={handleFilterChange(setSpec)} placeholder="如 62.5*2.3" />
                        </Col>
                        <Col md={4}>
                            <Form.Label>廠商</Form.Label>
                            <Form.Control size="sm" value={vendor} onChange={handleFilterChange(setVendor)} placeholder="模糊搜尋" />
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
                                    <th>建立日期</th>
                                    <th>廠商</th>
                                    <th>材質</th>
                                    <th>規格</th>
                                    <th>備註</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.length === 0 ? (
                                    <tr><td colSpan={6} className="text-center text-muted">無資料</td></tr>
                                ) : rows.map((r) => (
                                    <tr key={r.識別碼}>
                                        <td>{r.建立日期}</td>
                                        <td>{r.廠商}</td>
                                        <td>{r.材質}</td>
                                        <td>{r.規格 || <span className="text-muted">（通用）</span>}</td>
                                        <td>{r.備註}</td>
                                        <td>
                                            <Button size="sm" variant="outline-info" className="me-1" onClick={() => handleView(r.識別碼)}>查看</Button>
                                            <PermissionAction permission="tolerance.manage" reasonDisplay="tooltip"><Button size="sm" variant="outline-primary" className="me-1" onClick={() => handleEdit(r.識別碼)}>編輯</Button></PermissionAction>
                                            <PermissionAction permission="tolerance.manage" reasonDisplay="tooltip"><Button size="sm" variant="outline-danger" onClick={() => handleDelete(r.識別碼)}>刪除</Button></PermissionAction>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    )}

                    <PaginationBar page={page} perPage={20} total={result?.total ?? 0} totalPages={totalPages} onPageChange={setPage} />
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
            <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </div>
    );
};

export default ExtrusionTolerancePage;
