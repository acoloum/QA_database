import { useState } from 'react';
import { useNavigate } from 'react-router';
import {
    Container, Card, Button,
} from 'react-bootstrap';
import {
    useComplaintList,
    useDeleteComplaint,
    useOpenCapaFromComplaint,
    useOpenReworkFromComplaint,
} from '../../hooks/useComplaint';
import ComplaintModal from '../../components/complaint/ComplaintModal';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import PaginationBar from '../../components/common/PaginationBar';
import type { CustomerComplaint } from '../../types';
import { ComplaintFilterBar, ComplaintTable, type ComplaintFilters } from './ComplaintPageParts';
import PermissionAction from '../../components/PermissionAction';

const PAGE_SIZE = 20;

const ComplaintPage = () => {
    const navigate = useNavigate();
    // 篩選
    const [customerFilter,  setCustomerFilter]  = useState('');
    const [materialFilter,  setMaterialFilter]  = useState('');
    const [specFilter,      setSpecFilter]      = useState('');
    const [statusFilter,    setStatusFilter]    = useState('');
    const [typeFilter,      setTypeFilter]      = useState('');
    const [dateFromFilter,  setDateFromFilter]  = useState('');
    const [dateToFilter,    setDateToFilter]    = useState('');
    const [repeatFilter,    setRepeatFilter]    = useState<'' | 'true' | 'false'>('');
    const [page,            setPage]            = useState(1);

    // Modal 狀態
    const [showModal, setShowModal] = useState(false);
    const [editData,  setEditData]  = useState<CustomerComplaint | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    const params = {
        customer:       customerFilter  || undefined,
        material:       materialFilter  || undefined,
        spec:           specFilter      || undefined,
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
    const openReworkMutation    = useOpenReworkFromComplaint();

    const complaints  = data?.data ?? [];
    const totalPages  = Math.ceil((data?.total ?? 0) / PAGE_SIZE);

    const handleNew  = () => { setEditData(null); setShowModal(true); };
    const handleEdit = (c: CustomerComplaint) => { setEditData(c); setShowModal(true); };

    const handleDelete = (c: CustomerComplaint) => {
        setConfirmAction({
            title: '刪除客訴',
            message: `確定刪除客訴「${c.complaint_no}」嗎？`,
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => deleteMutation.mutateAsync(c.id),
        });
    };

    const handleOpenCapa = (c: CustomerComplaint) => {
        if (c.related_capa_id) {
            // 已開立 CAPA，直接跳轉
            navigate(`/capa?editId=${c.related_capa_id}`);
            return;
        }
        setConfirmAction({
            title: '開立 CAPA',
            message: `確定從客訴「${c.complaint_no}」開立 CAPA？`,
            confirmLabel: '開立',
            confirmVariant: 'primary',
            onConfirm: () => openCapaMutation.mutateAsync(c.id),
        });
    };

    const handleOpenRework = (c: CustomerComplaint) => {
        if (c.related_rework_id) {
            // 已開立重工單，直接跳轉
            navigate(`/rework?id=${c.related_rework_id}`);
            return;
        }
        setConfirmAction({
            title: '開立重工申請',
            message: `確定從客訴「${c.complaint_no}」開立重工申請單？`,
            confirmLabel: '開立',
            confirmVariant: 'primary',
            onConfirm: () => openReworkMutation.mutateAsync(c.id),
        });
    };

    const handleReset = () => {
        setCustomerFilter('');
        setMaterialFilter('');
        setSpecFilter('');
        setStatusFilter('');
        setTypeFilter('');
        setDateFromFilter('');
        setDateToFilter('');
        setRepeatFilter('');
        setPage(1);
    };

    const filters: ComplaintFilters = {
        customer: customerFilter,
        material: materialFilter,
        spec: specFilter,
        status: statusFilter,
        type: typeFilter,
        dateFrom: dateFromFilter,
        dateTo: dateToFilter,
        repeat: repeatFilter,
    };

    const handleFilterChange = (key: keyof ComplaintFilters, value: string) => {
        if (key === 'customer') setCustomerFilter(value);
        if (key === 'material') setMaterialFilter(value);
        if (key === 'spec') setSpecFilter(value);
        if (key === 'status') setStatusFilter(value);
        if (key === 'type') setTypeFilter(value);
        if (key === 'dateFrom') setDateFromFilter(value);
        if (key === 'dateTo') setDateToFilter(value);
        if (key === 'repeat') setRepeatFilter(value as '' | 'true' | 'false');
        setPage(1);
    };

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="bi bi-megaphone me-2 text-warning" />
                    客訴管理
                </h4>
                <div className="d-flex gap-2">
                    <Button variant="outline-primary" size="sm" onClick={() => navigate('/complaints/stats')}>
                        <i className="bi bi-bar-chart-fill me-1" />
                        統計分析
                    </Button>
                    <PermissionAction permission="complaint.create"><Button variant="primary" onClick={handleNew}>
                        <i className="bi bi-plus-lg me-1" />
                        新增客訴
                    </Button></PermissionAction>
                </div>
            </div>

            <ComplaintFilterBar filters={filters} onFilterChange={handleFilterChange} onReset={handleReset} />

            {/* 表格 */}
            <Card className="shadow-sm">
                <Card.Body className="p-0">
                    <ComplaintTable
                        loading={isLoading}
                        complaints={complaints}
                        capaPending={openCapaMutation.isPending}
                        reworkPending={openReworkMutation.isPending}
                        onEdit={handleEdit}
                        onDelete={handleDelete}
                        onOpenCapa={handleOpenCapa}
                        onOpenRework={handleOpenRework}
                        onNavigateToCapa={id => navigate(`/capa?editId=${id}`)}
                        onNavigateToRework={id => navigate(`/rework?id=${id}`)}
                    />

                    {totalPages > 1 && (
                        <div className="px-3 py-2 border-top">
                            <PaginationBar page={page} perPage={PAGE_SIZE} total={data?.total ?? 0} totalPages={totalPages} onPageChange={setPage} />
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
            <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </Container>
    );
};

export default ComplaintPage;
