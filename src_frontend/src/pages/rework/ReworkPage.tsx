import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import type { ReworkExecutionDetail, ReworkInspectionDetail, ReworkCostDetail } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import ReworkStatisticsDashboard from '../../components/rework/ReworkStatisticsDashboard';
import ApplyModal from '../../components/rework/ApplyModal';
import ApproveModal from '../../components/rework/ApproveModal';
import CostModal from '../../components/rework/CostModal';
import EditBasicInfoModal from '../../components/rework/EditBasicInfoModal';
import EditCostModal from '../../components/rework/EditCostModal';
import EditExecutionModal from '../../components/rework/EditExecutionModal';
import EditInspectionModal from '../../components/rework/EditInspectionModal';
import ExecutionModal from '../../components/rework/ExecutionModal';
import InspectionModal from '../../components/rework/InspectionModal';
import ReworkFollowUpModal from '../../components/rework/ReworkFollowUpModal';
import ReworkListTable from './ReworkListTable';
import ReworkDetailModal from './ReworkDetailModal';
import { useReworkActions } from './useReworkActions';
import { useReworkDetail } from './useReworkDetail';
import { useReworkPageData } from './useReworkPageData';
import { useAuth } from '../../context/useAuth';

// 目前開啟的 Modal（互斥，一次只開一個）
type ReworkModalType =
    | 'apply'
    | 'approve'
    | 'execution'
    | 'inspection'
    | 'cost'
    | 'editExecution'
    | 'editInspection'
    | 'editCost'
    | 'editBasic'
    | null;

const ReworkPage = () => {
    const { hasPermission } = useAuth();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    // Modals
    const [activeModal, setActiveModal] = useState<ReworkModalType>(null);
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
        hasPermission,
    });

    useEffect(() => {
        const ncmrId = searchParams.get('ncmr_id');
        const ncmrNo = searchParams.get('ncmr_no');
        if (ncmrId && hasPermission('rework.create')) {
            let cancelled = false;
            queueMicrotask(() => {
                if (cancelled) return;
                setInitialNcmrId(ncmrId);
                setInitialNcmrNo(ncmrNo || '');
                setActiveModal('apply');
            });
            return () => {
                cancelled = true;
            };
        }
    }, [searchParams, hasPermission]);

    const handleCloseApplyModal = () => {
        setActiveModal(null);
        setInitialNcmrId('');
        setInitialNcmrNo('');
        navigate('/rework', { replace: true });
    };

    const handleApproveClick = (id: number) => {
        setSelectedReworkId(id);
        setActiveModal('approve');
    };

    const handleEditExecution = (execution: ReworkExecutionDetail) => {
        setSelectedExecution(execution);
        setActiveModal('editExecution');
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
        setActiveModal('editInspection');
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
        setActiveModal('editCost');
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

            <ReworkListTable
                loading={loading}
                applications={applications}
                onOpenDetail={openDetail}
                onApprove={handleApproveClick}
                onDelete={handleDeleteRework}
            />

            <ApplyModal
                show={activeModal === 'apply' && hasPermission('rework.create')}
                handleClose={handleCloseApplyModal}
                onSuccess={loadData}
                initialNcmrId={initialNcmrId}
                initialNcmrNo={initialNcmrNo}
            />
            <ApproveModal
                show={activeModal === 'approve' && hasPermission('rework.approve')}
                handleClose={() => setActiveModal(null)}
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
                onEditBasic={() => setActiveModal('editBasic')}
                onCloseRework={handleCloseRework}
                onAddExecution={() => setActiveModal('execution')}
                onEditExecution={handleEditExecution}
                onDeleteExecution={handleDeleteExecution}
                onAddInspection={() => setActiveModal('inspection')}
                onEditInspection={handleEditInspection}
                onDeleteInspection={handleDeleteInspection}
                onAddCost={() => setActiveModal('cost')}
                onEditCost={handleEditCost}
                onDeleteCost={handleDeleteCost}
            />
            <ExecutionModal
                show={activeModal === 'execution' && hasPermission('rework.create')}
                handleClose={() => setActiveModal(null)}
                onSuccess={() => reloadDetailData()}
                reworkNumber={selectedReworkDetail?.申請單號 || ''}
            />
            <InspectionModal
                show={activeModal === 'inspection' && hasPermission('rework.create')}
                handleClose={() => setActiveModal(null)}
                onSuccess={() => reloadDetailData()}
                reworkNumber={selectedReworkDetail?.申請單號 || ''}
            />
            <CostModal
                show={activeModal === 'cost' && hasPermission('rework.create')}
                handleClose={() => setActiveModal(null)}
                onSuccess={() => { reloadDetailData(); loadData(); }}
                reworkNumber={selectedReworkDetail?.申請單號 || ''}
            />
            <EditExecutionModal
                show={activeModal === 'editExecution' && hasPermission('rework.create')}
                handleClose={() => setActiveModal(null)}
                onSuccess={() => reloadDetailData()}
                execution={selectedExecution}
            />
            <EditInspectionModal
                show={activeModal === 'editInspection' && hasPermission('rework.create')}
                handleClose={() => setActiveModal(null)}
                onSuccess={() => reloadDetailData()}
                inspection={selectedInspection}
            />
            <EditCostModal
                show={activeModal === 'editCost' && hasPermission('rework.create')}
                handleClose={() => setActiveModal(null)}
                onSuccess={() => { reloadDetailData(); loadData(); }}
                cost={selectedCost}
            />
            <EditBasicInfoModal
                show={activeModal === 'editBasic' && hasPermission('rework.create')}
                handleClose={() => setActiveModal(null)}
                onSuccess={() => reloadDetailData()}
                application={selectedReworkDetail}
            />
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
