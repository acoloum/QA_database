import { useState } from 'react';
import {
    Container, Row, Col, Card, Table, Badge, Button, Form,
} from 'react-bootstrap';
import {
    useComplaintList,
    useDeleteComplaint,
    useOpenCapaFromComplaint,
    COMPLAINT_TYPE_LABELS,
    COMPLAINT_STATUS_VARIANT,
} from '../../hooks/useComplaint';
import ComplaintModal from '../../components/complaint/ComplaintModal';
import type { CustomerComplaint } from '../../types';

const PAGE_SIZE = 20;

const ComplaintPage = () => {
    // 篩選
    const [customerFilter,  setCustomerFilter]  = useState('');
    const [productFilter,   setProductFilter]   = useState('');
    const [statusFilter,    setStatusFilter]    = useState('');
    const [typeFilter,      setTypeFilter]      = useState('');
    const [dateFromFilter,  setDateFromFilter]  = useState('');
    const [dateToFilter,    setDateToFilter]    = useState('');
    const [repeatFilter,    setRepeatFilter]    = useState<'' | 'true' | 'false'>('');
    const [page,            setPage]            = useState(1);

    // Modal 狀態
    const [showModal, setShowModal] = useState(false);
    const [editData,  setEditData]  = useState<CustomerComplaint | null>(null);

    const params = {
        customer:       customerFilter  || undefined,
        product_no:     productFilter   || undefined,
        status:         statusFilter    || undefined,
        complaint_type: typeFilter      || undefined,
        date_from:      dateFromFilter  || undefined,
        date_to:        dateToFilter    || undefined,
        is_repeat:      repeatFilter === 'true' ? true : repeatFilter === 'false' ? false : undefined,
        page,
        per_page: PAGE_SIZE,
    };

    const { data, isLoading }   = useComplaintList(params);
    const deleteMutation        = useDeleteComplaint();
    const openCapaMutation      = useOpenCapaFromComplaint();

    const complaints  = data?.data ?? [];
    const totalPages  = Math.ceil((data?.total ?? 0) / PAGE_SIZE);

    const handleNew  = () => { setEditData(null); setShowModal(true); };
    const handleEdit = (c: CustomerComplaint) => { setEditData(c); setShowModal(true); };

    const handleDelete = (c: CustomerComplaint) => {
        if (window.confirm(`確定刪除客訴「${c.complaint_no}」嗎？`)) {
            deleteMutation.mutate(c.id);
        }
    };

    const handleOpenCapa = (c: CustomerComplaint) => {
        if (c.related_capa_id) {
            alert(`此客訴已開立 CAPA（ID: ${c.related_capa_id}）`);
            return;
        }
        if (window.confirm(`確定從客訴「${c.complaint_no}」開立 CAPA？`)) {
            openCapaMutation.mutate(c.id);
        }
    };

    const handleReset = () => {
        setCustomerFilter('');
        setProductFilter('');
        setStatusFilter('');
        setTypeFilter('');
        setDateFromFilter('');
        setDateToFilter('');
        setRepeatFilter('');
        setPage(1);
    };

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="bi bi-megaphone me-2 text-warning" />
                    客訴管理
                </h4>
                <Button variant="primary" onClick={handleNew}>
                    <i className="bi bi-plus-lg me-1" />
                    新增客訴
                </Button>
            </div>

            {/* 篩選列 */}
            <Card className="mb-3 shadow-sm">
                <Card.Body className="py-2">
                    <Row className="g-2 align-items-end">
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">客戶</Form.Label>
                            <Form.Control size="sm" placeholder="搜尋客戶…"
                                value={customerFilter} onChange={e => { setCustomerFilter(e.target.value); setPage(1); }} />
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">料號</Form.Label>
                            <Form.Control size="sm" placeholder="搜尋料號…"
                                value={productFilter} onChange={e => { setProductFilter(e.target.value); setPage(1); }} />
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">狀態</Form.Label>
                            <Form.Select size="sm" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
                                <option value="">全部</option>
                                {['待處理', '處理中', '已結案'].map(s => <option key={s} value={s}>{s}</option>)}
                            </Form.Select>
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">類型</Form.Label>
                            <Form.Select size="sm" value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(1); }}>
                                <option value="">全部</option>
                                {Object.entries(COMPLAINT_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                            </Form.Select>
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">重複客訴</Form.Label>
                            <Form.Select size="sm" value={repeatFilter} onChange={e => { setRepeatFilter(e.target.value as '' | 'true' | 'false'); setPage(1); }}>
                                <option value="">全部</option>
                                <option value="true">僅重複</option>
                                <option value="false">非重複</option>
                            </Form.Select>
                        </Col>
                        <Col xs={6} md={1}>
                            <Button variant="outline-secondary" size="sm" className="w-100" onClick={handleReset}>清除</Button>
                        </Col>
                    </Row>
                    <Row className="g-2 mt-1">
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（起）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateFromFilter}
                                onChange={e => { setDateFromFilter(e.target.value); setPage(1); }} />
                        </Col>
                        <Col xs={6} md={3}>
                            <Form.Label className="small mb-1">日期（迄）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateToFilter}
                                onChange={e => { setDateToFilter(e.target.value); setPage(1); }} />
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            {/* 表格 */}
            <Card className="shadow-sm">
                <Card.Body className="p-0">
                    <div className="table-responsive">
                        <Table hover className="mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th>單號</th>
                                    <th>客戶</th>
                                    <th>料號</th>
                                    <th>日期</th>
                                    <th>類型</th>
                                    <th>嚴重度</th>
                                    <th>初回期限</th>
                                    <th>狀態</th>
                                    <th>重複</th>
                                    <th>CAPA</th>
                                    <th style={{ width: '120px' }}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isLoading ? (
                                    <tr><td colSpan={11} className="text-center py-4 text-muted">載入中…</td></tr>
                                ) : complaints.length === 0 ? (
                                    <tr>
                                        <td colSpan={11} className="text-center py-4 text-muted">
                                            <i className="bi bi-inbox fs-3 d-block mb-2" />
                                            查無符合條件的客訴
                                        </td>
                                    </tr>
                                ) : complaints.map(c => (
                                    <tr key={c.id} className={c.is_overdue ? 'table-warning' : ''}>
                                        <td className="small fw-semibold">{c.complaint_no}</td>
                                        <td className="small">{c.customer}</td>
                                        <td className="small">{c.product_no}</td>
                                        <td className="small">{c.complaint_date}</td>
                                        <td className="small">
                                            <Badge bg="light" text="dark">
                                                {COMPLAINT_TYPE_LABELS[c.complaint_type] ?? c.complaint_type}
                                            </Badge>
                                        </td>
                                        <td className="small">
                                            <Badge bg={
                                                c.severity === 'Critical' ? 'danger' :
                                                c.severity === 'Major'    ? 'warning' : 'info'
                                            } text={c.severity === 'Minor' ? 'dark' : undefined}>
                                                {c.severity ?? '—'}
                                            </Badge>
                                        </td>
                                        <td className="small">
                                            {c.initial_reply_deadline ? (
                                                <span className={c.is_overdue ? 'text-danger fw-semibold' : ''}>
                                                    {c.initial_reply_deadline}
                                                    {c.is_overdue && (
                                                        <Badge bg="danger" className="ms-1" style={{ fontSize: '0.65rem' }}>
                                                            +{c.overdue_days}天
                                                        </Badge>
                                                    )}
                                                </span>
                                            ) : '—'}
                                        </td>
                                        <td>
                                            <Badge bg={COMPLAINT_STATUS_VARIANT[c.status] ?? 'secondary'}>
                                                {c.status}
                                            </Badge>
                                        </td>
                                        <td>
                                            {c.is_repeat && (
                                                <Badge bg="danger" title="12 個月內重複客訴">重複</Badge>
                                            )}
                                        </td>
                                        <td>
                                            {c.related_capa_id ? (
                                                <Badge bg="success">已開立</Badge>
                                            ) : (
                                                <Button
                                                    variant="outline-warning"
                                                    size="sm"
                                                    style={{ fontSize: '0.7rem' }}
                                                    onClick={() => handleOpenCapa(c)}
                                                    disabled={openCapaMutation.isPending}
                                                >
                                                    開立 CAPA
                                                </Button>
                                            )}
                                        </td>
                                        <td>
                                            <Button
                                                variant="outline-primary"
                                                size="sm"
                                                className="me-1"
                                                onClick={() => handleEdit(c)}
                                            >
                                                編輯
                                            </Button>
                                            <Button
                                                variant="outline-danger"
                                                size="sm"
                                                onClick={() => handleDelete(c)}
                                                disabled={deleteMutation.isPending}
                                            >
                                                刪除
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    </div>

                    {totalPages > 1 && (
                        <div className="d-flex justify-content-between align-items-center px-3 py-2 border-top">
                            <span className="small text-muted">共 {data?.total ?? 0} 筆，第 {page}/{totalPages} 頁</span>
                            <div>
                                <Button variant="outline-secondary" size="sm" className="me-1"
                                    disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一頁</Button>
                                <Button variant="outline-secondary" size="sm"
                                    disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一頁</Button>
                            </div>
                        </div>
                    )}
                </Card.Body>
            </Card>

            <ComplaintModal
                show={showModal}
                onHide={() => setShowModal(false)}
                editData={editData}
                onSuccess={() => setShowModal(false)}
            />
        </Container>
    );
};

export default ComplaintPage;
