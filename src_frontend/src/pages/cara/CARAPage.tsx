import { useState } from 'react';
import { Button, Card, Col, Form, Table, Badge } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import CARAModal from '../../components/cara/CARAModal';
import FilterBar from '../../components/common/FilterBar';
import PaginationBar from '../../components/common/PaginationBar';
import { useCARAList } from '../../hooks/useNCMR';
import { useDeleteCARA } from '../../hooks/useCARA';
import type { CARListParams } from '../../hooks/useNCMR';

// 篩選欄位（排除分頁參數）
type CARFilters = Omit<CARListParams, 'page' | 'per_page'>;

const EMPTY_FILTERS: CARFilters = {
    date_from: '',
    date_to: '',
    vendor: '',
    material: '',
    product_info: '',
    status: '',
};

const CARAPage = () => {
    const navigate = useNavigate();
    const deleteCARA = useDeleteCARA();

    const [filters, setFilters] = useState<CARFilters>(EMPTY_FILTERS);
    const [page, setPage] = useState(1);
    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    // 組合查詢參數，空字串欄位不傳給 API
    const activeParams: CARListParams = {
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
        page,
        per_page: 20,
    };

    const { data: result, isLoading } = useCARAList(activeParams);
    const rows = result?.data ?? [];

    const handleFilterChange = (key: keyof CARFilters, value: string) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPage(1);
    };

    const handleReset = () => {
        setFilters(EMPTY_FILTERS);
        setPage(1);
    };

    const handleDelete = (id: number) => {
        if (!window.confirm(`確定要刪除 CAR #${id} 嗎？`)) return;
        deleteCARA.mutate(id);
    };

    const handleEdit = (id: number) => {
        setEditId(id);
        setShowModal(true);
    };

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold">
                    <i className="bi bi-shield-check"></i> 矯正措施要求 (CAR)
                </h2>
                <Button className="btn-back-home" onClick={() => navigate('/')}>
                    <i className="bi bi-arrow-left"></i> 回首頁
                </Button>
            </div>

            {/* 篩選列 */}
            <FilterBar onReset={handleReset}>
                <Col xs={12} sm={6} md={2}>
                    <Form.Label className="small mb-1">日期（起）</Form.Label>
                    <Form.Control
                        type="date"
                        size="sm"
                        value={filters.date_from ?? ''}
                        onChange={e => handleFilterChange('date_from', e.target.value)}
                    />
                </Col>
                <Col xs={12} sm={6} md={2}>
                    <Form.Label className="small mb-1">日期（迄）</Form.Label>
                    <Form.Control
                        type="date"
                        size="sm"
                        value={filters.date_to ?? ''}
                        onChange={e => handleFilterChange('date_to', e.target.value)}
                    />
                </Col>
                <Col xs={12} sm={6} md={2}>
                    <Form.Label className="small mb-1">廠商</Form.Label>
                    <Form.Control
                        type="text"
                        size="sm"
                        placeholder="輸入廠商"
                        value={filters.vendor ?? ''}
                        onChange={e => handleFilterChange('vendor', e.target.value)}
                    />
                </Col>
                <Col xs={12} sm={6} md={2}>
                    <Form.Label className="small mb-1">材質</Form.Label>
                    <Form.Control
                        type="text"
                        size="sm"
                        placeholder="輸入材質"
                        value={filters.material ?? ''}
                        onChange={e => handleFilterChange('material', e.target.value)}
                    />
                </Col>
                <Col xs={12} sm={6} md={2}>
                    <Form.Label className="small mb-1">規格</Form.Label>
                    <Form.Control
                        type="text"
                        size="sm"
                        placeholder="輸入規格"
                        value={filters.product_info ?? ''}
                        onChange={e => handleFilterChange('product_info', e.target.value)}
                    />
                </Col>
                <Col xs={12} sm={6} md={2}>
                    <Form.Label className="small mb-1">狀態</Form.Label>
                    <Form.Select
                        size="sm"
                        value={filters.status ?? ''}
                        onChange={e => handleFilterChange('status', e.target.value)}
                    >
                        <option value="">全部</option>
                        <option value="進行中">進行中</option>
                        <option value="已結案">已結案</option>
                    </Form.Select>
                </Col>
            </FilterBar>

            {/* 資料表 */}
            <Card className="shadow-sm">
                <Card.Body>
                    <Table hover responsive className="align-middle">
                        <thead className="table-light">
                            <tr>
                                <th>單號</th>
                                <th>關聯異常單</th>
                                <th>廠商</th>
                                <th>材質</th>
                                <th>規格</th>
                                <th>建立日期</th>
                                <th>負責人</th>
                                <th>狀態</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr>
                                    <td colSpan={9} className="text-center py-4">載入中...</td>
                                </tr>
                            ) : rows.length === 0 ? (
                                <tr>
                                    <td colSpan={9} className="text-center py-4">無資料</td>
                                </tr>
                            ) : (
                                rows.map(item => (
                                    <tr key={item.id}>
                                        <td className="fw-bold">{String(item.no ?? '')}</td>
                                        <td>#{String(item.ncmr_no ?? '')} ({String(item.source ?? '')})</td>
                                        <td>{String(item.vendor ?? '') || '-'}</td>
                                        <td>{String(item.material ?? '') || '-'}</td>
                                        <td>{String(item.product ?? '') || '-'}</td>
                                        <td>{String(item.create_date ?? '').substring(0, 10) || '-'}</td>
                                        <td>{String(item.owner ?? '') || '-'}</td>
                                        <td>
                                            <Badge bg={item.status === '已結案' ? 'success' : 'primary'}>
                                                {String(item.status ?? '')}
                                            </Badge>
                                        </td>
                                        <td>
                                            <Button
                                                variant="outline-primary"
                                                size="sm"
                                                className="me-2"
                                                onClick={() => handleEdit(item.id)}
                                            >
                                                處理
                                            </Button>
                                            <Button
                                                variant="outline-danger"
                                                size="sm"
                                                onClick={() => handleDelete(item.id)}
                                            >
                                                刪除
                                            </Button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            {/* 分頁列 */}
            <PaginationBar
                page={page}
                perPage={activeParams.per_page ?? 20}
                total={result?.total ?? 0}
                onPageChange={setPage}
            />

            <CARAModal
                show={showModal}
                caraId={editId}
                onHide={() => { setShowModal(false); setEditId(null); }}
            />
        </div>
    );
};

export default CARAPage;
