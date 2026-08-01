import { useState, useEffect } from 'react';
import { Container, Card, Table, Badge, Button, Form, Row, Col, ProgressBar } from 'react-bootstrap';
import { useNavigate, useSearchParams } from 'react-router';
import {
    useCapaList,
    useDeleteCapa,
    CAPA_SEVERITY_VARIANT,
    CAPA_STATUS_VARIANT,
} from '../../hooks/useCapa';
import CAPAModal from '../../components/capa/CAPAModal';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import type { CAPAListItem } from '../../types';
import { parseCapaOpenId } from './capaPageUtils';
import PermissionAction from '../../components/PermissionAction';

const PAGE_SIZE = 20;

const CAPAPage = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const initialOpenId = parseCapaOpenId(searchParams);

    // 篩選
    const [sourceType,  setSourceType]  = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [dateFrom,    setDateFrom]    = useState('');
    const [dateTo,      setDateTo]      = useState('');
    const [page,        setPage]        = useState(1);

    // Modal
    const [showModal, setShowModal] = useState(initialOpenId !== null);
    const [editId,    setEditId]    = useState<number | null>(
        initialOpenId
    );
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    // URL 參數觸發開啟（來自 NCMR / 客訴頁開立後跳轉）
    useEffect(() => {
        const openId = parseCapaOpenId(searchParams);
        const hasOpenParam = searchParams.has('editId') || searchParams.has('openId');
        if (openId !== null) {
            queueMicrotask(() => {
                setEditId(openId);
                setShowModal(true);
            });
        }
        if (hasOpenParam) {
            navigate('/capa', { replace: true });
        }
    }, [searchParams, navigate]);

    const params = {
        source_type: sourceType  || undefined,
        status:      statusFilter || undefined,
        date_from:   dateFrom    || undefined,
        date_to:     dateTo      || undefined,
        page,
        per_page: PAGE_SIZE,
    };

    const { data, isLoading } = useCapaList(params);
    const deleteMutation      = useDeleteCapa();
    const capas               = data?.data ?? [];
    const totalPages          = Math.ceil((data?.total ?? 0) / PAGE_SIZE);

    const handleEdit   = (item: CAPAListItem) => { setEditId(item.id); setShowModal(true); };
    const handleDelete = (item: CAPAListItem) => {
        setConfirmAction({
            title: '刪除 CAPA',
            message: `確定刪除 CAPA「${item.no}」嗎？`,
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => deleteMutation.mutateAsync(item.id),
        });
    };
    const handleReset = () => {
        setSourceType('');
        setStatusFilter('');
        setDateFrom('');
        setDateTo('');
        setPage(1);
    };

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="bi bi-shield-check me-2 text-primary" />
                    異常矯正措施（CAPA）
                </h4>
                <div className="d-flex gap-2">
                    <Button variant="outline-secondary" size="sm" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left me-1" />
                        回首頁
                    </Button>
                    <span className="small text-muted align-self-center">
                        <i className="bi bi-info-circle me-1" />
                        CAPA 請從 NCMR 或客訴頁面開立
                    </span>
                </div>
            </div>

            {/* 篩選列 */}
            <Card className="mb-3 shadow-sm">
                <Card.Body className="py-2">
                    <Row className="g-2 align-items-end">
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">來源類型</Form.Label>
                            <Form.Select size="sm" value={sourceType}
                                onChange={e => { setSourceType(e.target.value); setPage(1); }}>
                                <option value="">全部</option>
                                <option value="ncmr">NCMR</option>
                                <option value="complaint">客訴</option>
                            </Form.Select>
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">狀態</Form.Label>
                            <Form.Select size="sm" value={statusFilter}
                                onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
                                <option value="">全部</option>
                                <option value="進行中">進行中</option>
                                <option value="已結案">已結案</option>
                            </Form.Select>
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">建立日期（起）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateFrom}
                                onChange={e => { setDateFrom(e.target.value); setPage(1); }} />
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">建立日期（迄）</Form.Label>
                            <Form.Control type="date" size="sm" value={dateTo}
                                onChange={e => { setDateTo(e.target.value); setPage(1); }} />
                        </Col>
                        <Col xs={12} md={2}>
                            <Button variant="outline-secondary" size="sm" className="w-100" onClick={handleReset}>
                                清除篩選
                            </Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            {/* CAPA 表格 */}
            <Card className="shadow-sm">
                <Card.Body className="p-0">
                    <div className="table-responsive">
                        <Table hover className="mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th>8D 單號</th>
                                    <th>來源</th>
                                    <th>廠商</th>
                                    <th>不良描述</th>
                                    <th>嚴格度</th>
                                    <th>嚴重度</th>
                                    <th>負責人</th>
                                    <th>客戶要求結案日</th>
                                    <th>進度</th>
                                    <th>狀態</th>
                                    <th style={{ width: '120px' }}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isLoading ? (
                                    <tr><td colSpan={11} className="text-center py-4 text-muted">載入中…</td></tr>
                                ) : capas.length === 0 ? (
                                    <tr>
                                        <td colSpan={11} className="text-center py-4 text-muted">
                                            <i className="bi bi-inbox fs-3 d-block mb-2" />
                                            查無 CAPA 資料
                                        </td>
                                    </tr>
                                ) : capas.map(item => (
                                    <tr key={item.id}>
                                        <td className="fw-semibold small">{item.no}</td>
                                        <td className="small">
                                            <Badge bg="light" text="dark">
                                                {item.source_type === 'ncmr' ? 'NCMR' : '客訴'}
                                            </Badge>
                                        </td>
                                        <td className="small">{item.vendor ?? '—'}</td>
                                        <td className="small" style={{ maxWidth: '180px' }}>
                                            <span className="text-truncate d-block" title={item.ncmr_description ?? ''}>
                                                {item.ncmr_description ?? '—'}
                                            </span>
                                        </td>
                                        <td className="small">
                                            <Badge bg={item.rigor === '完整8D' ? 'primary' : 'info'}>
                                                {item.rigor}
                                            </Badge>
                                        </td>
                                        <td>
                                            {item.severity && (
                                                <Badge bg={CAPA_SEVERITY_VARIANT[item.severity] ?? 'secondary'}>
                                                    {item.severity}
                                                </Badge>
                                            )}
                                        </td>
                                        <td className="small">{item.owner ?? '—'}</td>
                                        <td className="small">{item.deadline ?? '—'}</td>
                                        <td style={{ minWidth: '100px' }}>
                                            <div className="d-flex align-items-center gap-2">
                                                <ProgressBar
                                                    now={item.progress_percent}
                                                    variant={
                                                        item.progress_percent >= 100 ? 'success' :
                                                        item.progress_percent >= 50  ? 'primary' : 'warning'
                                                    }
                                                    style={{ height: '6px', flex: 1 }}
                                                />
                                                <span className="small text-muted" style={{ whiteSpace: 'nowrap' }}>
                                                    {item.progress_percent}%
                                                </span>
                                            </div>
                                        </td>
                                        <td>
                                            <Badge bg={CAPA_STATUS_VARIANT[item.status] ?? 'secondary'}>
                                                {item.status}
                                            </Badge>
                                        </td>
                                        <td>
                                            <PermissionAction permission="capa.view"><Button
                                                variant="outline-primary"
                                                size="sm"
                                                className="me-1"
                                                onClick={() => handleEdit(item)}
                                            >
                                                處理
                                            </Button></PermissionAction>
                                            <PermissionAction permission="capa.close"><Button
                                                variant="outline-danger"
                                                size="sm"
                                                onClick={() => handleDelete(item)}
                                                disabled={deleteMutation.isPending}
                                            >
                                                刪除
                                            </Button></PermissionAction>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    </div>

                    {totalPages > 1 && (
                        <div className="d-flex justify-content-between align-items-center px-3 py-2 border-top">
                            <span className="small text-muted">
                                共 {data?.total ?? 0} 筆，第 {page}/{totalPages} 頁
                            </span>
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

            <CAPAModal
                show={showModal}
                capaId={editId}
                onHide={() => { setShowModal(false); setEditId(null); }}
            />
            <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </Container>
    );
};

export default CAPAPage;
