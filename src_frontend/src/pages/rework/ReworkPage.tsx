import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ReworkExecutionDetail, ReworkInspectionDetail, ReworkCostDetail } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import ApplyModal from '../../components/rework/ApplyModal';
import ApproveModal from '../../components/rework/ApproveModal';
import ExecutionModal from '../../components/rework/ExecutionModal';
import InspectionModal from '../../components/rework/InspectionModal';
import CostModal from '../../components/rework/CostModal';
import EditExecutionModal from '../../components/rework/EditExecutionModal';
import EditInspectionModal from '../../components/rework/EditInspectionModal';
import EditCostModal from '../../components/rework/EditCostModal';
import EditBasicInfoModal from '../../components/rework/EditBasicInfoModal';
import ReworkStatisticsDashboard from '../../components/rework/ReworkStatisticsDashboard';
import ReworkFollowUpModal from '../../components/rework/ReworkFollowUpModal';
import ReworkDetailModal from './ReworkDetailModal';
import { useReworkActions } from './useReworkActions';
import { useReworkDetail } from './useReworkDetail';
import { useReworkPageData } from './useReworkPageData';

const ReworkPage = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    // Modals
    const [showApplyModal, setShowApplyModal] = useState(false);
    const [showApproveModal, setShowApproveModal] = useState(false);
    const [showExecutionModal, setShowExecutionModal] = useState(false);
    const [showInspectionModal, setShowInspectionModal] = useState(false);
    const [showCostModal, setShowCostModal] = useState(false);
    const [showEditExecutionModal, setShowEditExecutionModal] = useState(false);
    const [showEditInspectionModal, setShowEditInspectionModal] = useState(false);
    const [showEditCostModal, setShowEditCostModal] = useState(false);
    const [showEditBasicModal, setShowEditBasicModal] = useState(false);
    const [selectedReworkId, setSelectedReworkId] = useState<number | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);
    const [selectedExecution, setSelectedExecution] = useState<ReworkExecutionDetail | null>(null);
    const [selectedInspection, setSelectedInspection] = useState<ReworkInspectionDetail | null>(null);
    const [selectedCost, setSelectedCost] = useState<ReworkCostDetail | null>(null);

    const [initialNcmrId, setInitialNcmrId] = useState<string>('');
    const [initialNcmrNo, setInitialNcmrNo] = useState<string>('');

    // 結案後追蹤 Modal（若 NCMR 尚未開 CAPA 則提示）
    const [followUpModal, setFollowUpModal] = useState<{
        show: boolean;
        ncmrId: number;
        ncmrNumber: string;
    } | null>(null);

    // Filters
    const [statusFilter, setStatusFilter] = useState('');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');

    const { applications, stats, loading, loadData } = useReworkPageData({
        statusFilter,
        startDate,
        endDate,
    });
    const {
        showDetailModal,
        setShowDetailModal,
        selectedReworkDetail,
        executions,
        inspections,
        costs,
        activeTab,
        setActiveTab,
        openDetail,
        reloadDetailData,
    } = useReworkDetail(loadData);
    const reworkActions = useReworkActions({
        applications,
        selectedReworkDetail,
        reloadDetailData,
        loadData,
        setFollowUpModal,
    });

    useEffect(() => {
        const ncmrId = searchParams.get('ncmr_id');
        const ncmrNo = searchParams.get('ncmr_no');
        if (ncmrId) {
            let cancelled = false;
            queueMicrotask(() => {
                if (cancelled) return;
                setInitialNcmrId(ncmrId);
                setInitialNcmrNo(ncmrNo || '');
                setShowApplyModal(true);
            });
            return () => {
                cancelled = true;
            };
        }
    }, [searchParams]);

    const handleCloseApplyModal = () => {
        setShowApplyModal(false);
        setInitialNcmrId('');
        setInitialNcmrNo('');
        navigate('/rework', { replace: true });
    };

    const handleApproveClick = (id: number) => {
        setSelectedReworkId(id);
        setShowApproveModal(true);
    };

    const handleEditExecution = (execution: ReworkExecutionDetail) => {
        setSelectedExecution(execution);
        setShowEditExecutionModal(true);
    };

    const handleDeleteExecution = async (executionId: number) => {
        setConfirmAction({
            title: '刪除執行記錄',
            message: '確定要刪除此執行記錄嗎？',
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => reworkActions.deleteExecution(executionId),
        });
    };

    const handleEditInspection = (inspection: ReworkInspectionDetail) => {
        setSelectedInspection(inspection);
        setShowEditInspectionModal(true);
    };

    const handleDeleteInspection = async (inspectionId: number) => {
        setConfirmAction({
            title: '刪除品檢記錄',
            message: '確定要刪除此品檢記錄嗎？',
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => reworkActions.deleteInspection(inspectionId),
        });
    };

    const handleEditCost = (cost: ReworkCostDetail) => {
        setSelectedCost(cost);
        setShowEditCostModal(true);
    };

    const handleDeleteCost = async (costId: number) => {
        setConfirmAction({
            title: '刪除成本記錄',
            message: '確定要刪除此成本記錄嗎？',
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => reworkActions.deleteCost(costId),
        });
    };

    const handleCloseRework = async (reworkId: number) => {
        setConfirmAction({
            title: '重工結案',
            message: '確定要結案此重工申請嗎？',
            confirmLabel: '結案',
            confirmVariant: 'success',
            onConfirm: () => reworkActions.closeRework(reworkId),
        });
    };

    const handleDeleteRework = async (reworkId: number) => {
        setConfirmAction({
            title: '刪除重工申請',
            message: '確定要刪除此重工申請嗎？此動作無法復原。',
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => reworkActions.deleteRework(reworkId),
        });
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case '已完成': return 'bg-info text-dark';
            case '已核准': return 'bg-success';
            case '已拒絕': return 'bg-danger';
            case '執行中': return 'bg-primary';
            default: return 'bg-warning text-dark'; // 申請中
        }
    };

    const getUrgencyBadge = (urgency: string) => {
        switch (urgency) {
            case '緊急': return 'bg-danger';
            case '重要': return 'bg-warning text-dark';
            default: return 'bg-secondary';
        }
    };

    return (
        <div className="container-fluid">
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary"><i className="bi bi-rotate"></i> 重工管理系統</h2>
                <div>
                    <button className="btn btn-back-home" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </button>
                </div>
            </div>

            {/* Statistics Dashboard */}
            <ReworkStatisticsDashboard stats={stats} />

            {/* Filters */}
            <div className="card mb-4 shadow-sm">
                <div className="card-body">
                    <div className="row g-3">
                        <div className="col-md-3">
                            <label className="form-label">狀態篩選</label>
                            <select
                                className="form-select"
                                value={statusFilter}
                                onChange={(e) => setStatusFilter(e.target.value)}
                            >
                                <option value="">全部狀態</option>
                                <option value="申請中">申請中</option>
                                <option value="已核准">已核准</option>
                                <option value="執行中">執行中</option>
                                <option value="已完成">已完成</option>
                                <option value="已拒絕">已拒絕</option>
                            </select>
                        </div>
                        <div className="col-md-3">
                            <label className="form-label">開始日期</label>
                            <input
                                type="date"
                                className="form-control"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                            />
                        </div>
                        <div className="col-md-3">
                            <label className="form-label">結束日期</label>
                            <input
                                type="date"
                                className="form-control"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                            />
                        </div>
                        <div className="col-md-3 d-flex align-items-end">
                            <button
                                className="btn btn-outline-secondary w-100"
                                onClick={() => {
                                    setStatusFilter('');
                                    setStartDate('');
                                    setEndDate('');
                                }}
                            >
                                <i className="bi bi-x-lg"></i> 清除篩選
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Data Table */}
            <div className="card shadow-sm">
                <div className="card-body">
                    <div className="table-responsive">
                        <table className="table table-hover align-middle">
                            <thead className="table-light">
                                <tr>
                                    <th>申請單號</th>
                                    <th>申請日期</th>
                                    <th>NCMR單號</th>
                                    <th>申請人</th>
                                    <th>規格</th>
                                    <th>重工數量</th>
                                    <th>緊急程度</th>
                                    <th>狀態</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr>
                                        <td colSpan={9} className="text-center py-5">
                                            <div className="spinner-border text-primary" role="status">
                                                <span className="visually-hidden">Loading...</span>
                                            </div>
                                        </td>
                                    </tr>
                                ) : applications.length === 0 ? (
                                    <tr>
                                        <td colSpan={9} className="text-center py-5 text-muted">
                                            查無資料
                                        </td>
                                    </tr>
                                ) : (
                                    applications.map((item) => (
                                        <tr key={item.識別碼}>
                                            <td className="fw-bold">{item.申請單號}</td>
                                            <td>{item.申請日期?.substring(0, 10)}</td>
                                            <td>
                                                <span className="badge bg-secondary">
                                                    {item.ncmr_number || item.客訴單號 || (item.NCMR_ID ? `#${item.NCMR_ID}` : '-')}
                                                </span>
                                            </td>
                                            <td>{item.申請人員姓名}</td>
                                            <td>{item.產品資訊 || '-'}</td>
                                            <td>{item.重工數量}</td>
                                            <td>
                                                <span className={`badge ${getUrgencyBadge(item.緊急程度)}`}>
                                                    {item.緊急程度}
                                                </span>
                                            </td>
                                            <td>
                                                <span className={`badge ${getStatusBadge(item.狀態)}`}>
                                                    {item.狀態}
                                                </span>
                                            </td>
                                            <td>
                                                <div className="btn-group btn-group-sm">
                                                    <button className="btn btn-outline-info" onClick={() => openDetail(item)}>詳情</button>
                                                    {(item.狀態 === '申請中') && (
                                                        <button
                                                            className="btn btn-outline-success"
                                                            onClick={() => handleApproveClick(item.識別碼)}
                                                        >
                                                            審核
                                                        </button>
                                                    )}
                                                    <button className="btn btn-outline-danger" onClick={() => handleDeleteRework(item.識別碼)}>刪除</button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Modals */}
            <ApplyModal
                show={showApplyModal}
                handleClose={handleCloseApplyModal}
                onSuccess={loadData}
                initialNcmrId={initialNcmrId}
                initialNcmrNo={initialNcmrNo}
            />
            <ApproveModal
                show={showApproveModal}
                handleClose={() => setShowApproveModal(false)}
                onSuccess={loadData}
                reworkId={selectedReworkId}
            />
            <ReworkDetailModal
                show={showDetailModal}
                onHide={() => setShowDetailModal(false)}
                detail={selectedReworkDetail}
                activeTab={activeTab}
                onTabChange={setActiveTab}
                executions={executions}
                inspections={inspections}
                costs={costs}
                onEditBasic={() => setShowEditBasicModal(true)}
                onCloseRework={handleCloseRework}
                onAddExecution={() => setShowExecutionModal(true)}
                onEditExecution={handleEditExecution}
                onDeleteExecution={handleDeleteExecution}
                onAddInspection={() => setShowInspectionModal(true)}
                onEditInspection={handleEditInspection}
                onDeleteInspection={handleDeleteInspection}
                onAddCost={() => setShowCostModal(true)}
                onEditCost={handleEditCost}
                onDeleteCost={handleDeleteCost}
            />
            {/* Execution Modal */}
            <ExecutionModal
                show={showExecutionModal}
                handleClose={() => setShowExecutionModal(false)}
                onSuccess={() => reloadDetailData()}
                reworkNumber={selectedReworkDetail?.申請單號 || ''}
            />

            {/* Inspection Modal */}
            <InspectionModal
                show={showInspectionModal}
                handleClose={() => setShowInspectionModal(false)}
                onSuccess={() => reloadDetailData()}
                reworkNumber={selectedReworkDetail?.申請單號 || ''}
            />

            {/* Cost Modal */}
            <CostModal
                show={showCostModal}
                handleClose={() => setShowCostModal(false)}
                onSuccess={() => { reloadDetailData(); loadData(); }}
                reworkNumber={selectedReworkDetail?.申請單號 || ''}
            />

            <EditExecutionModal
                show={showEditExecutionModal}
                handleClose={() => setShowEditExecutionModal(false)}
                onSuccess={() => reloadDetailData()}
                execution={selectedExecution}
            />

            <EditInspectionModal
                show={showEditInspectionModal}
                handleClose={() => setShowEditInspectionModal(false)}
                onSuccess={() => reloadDetailData()}
                inspection={selectedInspection}
            />

            <EditCostModal
                show={showEditCostModal}
                handleClose={() => setShowEditCostModal(false)}
                onSuccess={() => { reloadDetailData(); loadData(); }}
                cost={selectedCost}
            />

            <EditBasicInfoModal
                show={showEditBasicModal}
                handleClose={() => setShowEditBasicModal(false)}
                onSuccess={() => reloadDetailData()}
                application={selectedReworkDetail}
            />

            {/* 結案後追蹤：若 NCMR 尚未開 CAPA 則提示 */}
            {followUpModal && (
                <ReworkFollowUpModal
                    show={followUpModal.show}
                    onHide={() => setFollowUpModal(null)}
                    ncmrId={followUpModal.ncmrId}
                    ncmrNumber={followUpModal.ncmrNumber}
                />
            )}
            <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </div>
    );
};

export default ReworkPage;
