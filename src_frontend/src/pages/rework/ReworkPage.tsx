import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Modal, Button } from 'react-bootstrap';
import api from '../../services/api';
import type { ReworkApplication, ReworkStatistics, ReworkExecutionDetail, ReworkInspectionDetail, ReworkCostDetail } from '../../types';
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

const ReworkPage = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [applications, setApplications] = useState<ReworkApplication[]>([]);
    const [stats, setStats] = useState<ReworkStatistics | null>(null);
    const [loading, setLoading] = useState(true);

    // Modals
    const [showApplyModal, setShowApplyModal] = useState(false);
    const [showApproveModal, setShowApproveModal] = useState(false);
    const [showDetailModal, setShowDetailModal] = useState(false);
    const [showExecutionModal, setShowExecutionModal] = useState(false);
    const [showInspectionModal, setShowInspectionModal] = useState(false);
    const [showCostModal, setShowCostModal] = useState(false);
    const [showEditExecutionModal, setShowEditExecutionModal] = useState(false);
    const [showEditInspectionModal, setShowEditInspectionModal] = useState(false);
    const [showEditCostModal, setShowEditCostModal] = useState(false);
    const [showEditBasicModal, setShowEditBasicModal] = useState(false);
    const [selectedReworkId, setSelectedReworkId] = useState<number | null>(null);
    const [selectedReworkDetail, setSelectedReworkDetail] = useState<ReworkApplication | null>(null);
    const [selectedExecution, setSelectedExecution] = useState<ReworkExecutionDetail | null>(null);
    const [selectedInspection, setSelectedInspection] = useState<ReworkInspectionDetail | null>(null);
    const [selectedCost, setSelectedCost] = useState<ReworkCostDetail | null>(null);

    // Detail modal tabs data
    const [executions, setExecutions] = useState<ReworkExecutionDetail[]>([]);
    const [inspections, setInspections] = useState<ReworkInspectionDetail[]>([]);
    const [costs, setCosts] = useState<ReworkCostDetail[]>([]);
    const [activeTab, setActiveTab] = useState('basic');

    const [initialNcmrId, setInitialNcmrId] = useState<string>('');
    const [initialNcmrNo, setInitialNcmrNo] = useState<string>('');

    // Filters
    const [statusFilter, setStatusFilter] = useState('');
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');

    const loadData = async () => {
        setLoading(true);
        try {
            // Load List
            const params = new URLSearchParams();
            if (statusFilter) params.append('status', statusFilter);
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);

            const listRes = await api.get<ReworkApplication[]>(`/rework/applications?${params.toString()}`);
            setApplications(listRes.data);

            // Load Stats
            const statsRes = await api.get<ReworkStatistics>('/rework/statistics');
            setStats(statsRes.data);

        } catch (error) {
            console.error('Error loading rework data:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [statusFilter, startDate, endDate]);

    useEffect(() => {
        const ncmrId = searchParams.get('ncmr_id');
        const ncmrNo = searchParams.get('ncmr_no');
        if (ncmrId) {
            setInitialNcmrId(ncmrId);
            setInitialNcmrNo(ncmrNo || '');
            setShowApplyModal(true);
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

    const reloadDetailData = async () => {
        if (!selectedReworkDetail) return;
        const reworkId = selectedReworkDetail.識別碼;
        try {
            const [appRes, execRes, inspRes, costRes] = await Promise.all([
                api.get(`/rework/applications?rework_id=${reworkId}`),
                api.get(`/rework/executions?rework_id=${reworkId}`),
                api.get(`/rework/inspections?rework_id=${reworkId}`),
                api.get(`/rework/costs?rework_id=${reworkId}`)
            ]);
            if (appRes.data && appRes.data.length > 0) {
                setSelectedReworkDetail(appRes.data[0]);
            }
            setExecutions(execRes.data || []);
            setInspections(inspRes.data || []);
            setCosts(costRes.data || []);
            await loadData();
        } catch (error) {
            console.error('Failed to reload rework detail data', error);
        }
    };

    const handleDetailClick = async (item: ReworkApplication) => {
        setSelectedReworkDetail(item);
        setShowDetailModal(true);

        const reworkId = item.識別碼;

        try {
            const [execRes, inspRes, costRes] = await Promise.all([
                api.get(`/rework/executions?rework_id=${reworkId}`),
                api.get(`/rework/inspections?rework_id=${reworkId}`),
                api.get(`/rework/costs?rework_id=${reworkId}`)
            ]);
            setExecutions(execRes.data || []);
            setInspections(inspRes.data || []);
            setCosts(costRes.data || []);
        } catch (error) {
            console.error('Failed to load rework detail data', error);
            setExecutions([]);
            setInspections([]);
            setCosts([]);
        }
    };

    const handleEditExecution = (execution: ReworkExecutionDetail) => {
        setSelectedExecution(execution);
        setShowEditExecutionModal(true);
    };

    const handleDeleteExecution = async (executionId: number) => {
        if (!confirm('確定要刪除此執行記錄嗎？')) return;
        try {
            await api.delete(`/rework/execution/${executionId}`);
            alert('刪除成功');
            reloadDetailData();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } } };
            alert(err.response?.data?.error || '刪除失敗');
        }
    };

    const handleEditInspection = (inspection: ReworkInspectionDetail) => {
        setSelectedInspection(inspection);
        setShowEditInspectionModal(true);
    };

    const handleDeleteInspection = async (inspectionId: number) => {
        if (!confirm('確定要刪除此品檢記錄嗎？')) return;
        try {
            await api.delete(`/rework/inspection/${inspectionId}`);
            alert('刪除成功');
            reloadDetailData();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } } };
            alert(err.response?.data?.error || '刪除失敗');
        }
    };

    const handleEditCost = (cost: ReworkCostDetail) => {
        setSelectedCost(cost);
        setShowEditCostModal(true);
    };

    const handleDeleteCost = async (costId: number) => {
        if (!confirm('確定要刪除此成本記錄嗎？')) return;
        try {
            await api.delete(`/rework/cost/${costId}`);
            alert('刪除成功');
            reloadDetailData();
            loadData();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } } };
            alert(err.response?.data?.error || '刪除失敗');
        }
    };

    const handleCloseRework = async (reworkId: number) => {
        if (!confirm('確定要結案此重工申請嗎？')) return;
        try {
            await api.post('/rework/close', { rework_id: reworkId });
            alert('結案成功');
            reloadDetailData();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } } };
            alert(err.response?.data?.error || '結案失敗');
        }
    };

    const handleDeleteRework = async (reworkId: number) => {
        if (!confirm('確定要刪除此重工申請嗎？此動作無法復原。')) return;
        try {
            await api.post('/rework/delete', { rework_id: reworkId });
            alert('刪除成功');
            loadData();
        } catch (error: any) {
            alert(error.response?.data?.error || '刪除失敗');
        }
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
                                                    {item.ncmr_number || `#${item.NCMR_ID}`}
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
                                                    <button className="btn btn-outline-info" onClick={() => handleDetailClick(item)}>詳情</button>
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
            <Modal show={showDetailModal} onHide={() => setShowDetailModal(false)} dialogClassName="modal-rework-detail">
                <Modal.Header closeButton>
                    <Modal.Title>重工申請詳情 - {selectedReworkDetail?.申請單號}</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {selectedReworkDetail && (
                        <>
                            <ul className="nav nav-tabs" role="tablist">
                                <li className="nav-item">
                                    <button className={`nav-link ${activeTab === 'basic' ? 'active' : ''}`} onClick={() => setActiveTab('basic')}>基本資訊</button>
                                </li>
                                <li className="nav-item">
                                    <button className={`nav-link ${activeTab === 'execution' ? 'active' : ''}`} onClick={() => setActiveTab('execution')}>執行記錄</button>
                                </li>
                                <li className="nav-item">
                                    <button className={`nav-link ${activeTab === 'inspection' ? 'active' : ''}`} onClick={() => setActiveTab('inspection')}>品檢記錄</button>
                                </li>
                                <li className="nav-item">
                                    <button className={`nav-link ${activeTab === 'cost' ? 'active' : ''}`} onClick={() => setActiveTab('cost')}>成本分析</button>
                                </li>
                            </ul>
                            <div className="tab-content mt-3">
                                {activeTab === 'basic' && (
                                    <div className="tab-pane fade show active">
                                        <div className="d-flex justify-content-between align-items-center mb-3">
                                            <h6 className="mb-0">基本資訊</h6>
                                            <div className="btn-group">
                                                <Button variant="primary" size="sm" onClick={() => setShowEditBasicModal(true)}>
                                                    <i className="bi bi-pencil"></i> 編輯
                                                </Button>
                                                {selectedReworkDetail.狀態 !== '已完成' && (
                                                    <Button variant="success" size="sm" onClick={() => handleCloseRework(selectedReworkDetail.識別碼)}>
                                                        <i className="bi bi-check-circle"></i> 結案
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                        <div className="row">
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">申請單號</label>
                                                <p>{selectedReworkDetail.申請單號}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">申請日期</label>
                                                <p>{selectedReworkDetail.申請日期}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">NCMR單號</label>
                                                <p>{selectedReworkDetail.ncmr_number || `#${selectedReworkDetail.NCMR_ID}`}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">申請人員</label>
                                                <p>{selectedReworkDetail.申請人員姓名}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">部門</label>
                                                <p>{selectedReworkDetail.部門}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">緊急程度</label>
                                                <p>{selectedReworkDetail.緊急程度}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">廠商</label>
                                                <p>{selectedReworkDetail.廠商 || '-'}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">材質</label>
                                                <p>{selectedReworkDetail.材質 || '-'}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">規格</label>
                                                <p>{selectedReworkDetail.產品資訊 || '-'}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">批號</label>
                                                <p>{selectedReworkDetail.批號 || '-'}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">重工數量</label>
                                                <p>{selectedReworkDetail.重工數量}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">預計完成日期</label>
                                                <p>{selectedReworkDetail.預計完成日期 || '-'}</p>
                                            </div>
                                            <div className="col-md-6 mb-3">
                                                <label className="form-label fw-bold">狀態</label>
                                                <p><span className={`badge ${getStatusBadge(selectedReworkDetail.狀態)}`}>{selectedReworkDetail.狀態}</span></p>
                                            </div>
                                            <div className="col-12 mb-3">
                                                <label className="form-label fw-bold">申請原因</label>
                                                <p>{selectedReworkDetail.申請原因 || '-'}</p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'execution' && (
                                    <div className="tab-pane fade show active">
                                        <div className="d-flex justify-content-between align-items-center mb-3">
                                            <h6 className="mb-0">執行記錄</h6>
                                            <Button variant="primary" size="sm" onClick={() => setShowExecutionModal(true)}>
                                                <i className="bi bi-plus-lg"></i> 新增
                                            </Button>
                                        </div>
                                        {executions.length > 0 ? (
                                            <table className="table table-sm table-bordered">
                                                <thead>
                                                    <tr>
                                                        <th>負責人員</th>
                                                        <th>執行部門</th>
                                                        <th>開始時間</th>
                                                        <th>完成數量</th>
                                                        <th>執行狀況</th>
                                                        <th style={{ width: '100px' }}>操作</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {executions.map((exec: any, idx: number) => (
                                                        <tr key={idx}>
                                                            <td>{exec.負責人員姓名 || '-'}</td>
                                                            <td>{exec.執行部門 || '-'}</td>
                                                            <td>{exec.開始時間 ? new Date(exec.開始時間).toLocaleString('zh-TW') : '-'}</td>
                                                            <td>{exec.完成數量 || '0'}</td>
                                                            <td>{exec.執行狀況 || '-'}</td>
                                                            <td>
                                                                <div className="btn-group btn-group-sm">
                                                                    <button className="btn btn-outline-primary" onClick={() => handleEditExecution(exec)}>編輯</button>
                                                                    <button className="btn btn-outline-danger" onClick={() => handleDeleteExecution(exec.識別碼)}>刪除</button>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        ) : (
                                            <p className="text-muted">暂无執行記錄</p>
                                        )}
                                    </div>
                                )}

                                {activeTab === 'inspection' && (
                                    <div className="tab-pane fade show active">
                                        <div className="d-flex justify-content-between align-items-center mb-3">
                                            <h6 className="mb-0">品檢記錄</h6>
                                            <Button variant="primary" size="sm" onClick={() => setShowInspectionModal(true)}>
                                                <i className="bi bi-plus-lg"></i> 新增
                                            </Button>
                                        </div>
                                        {inspections.length > 0 ? (
                                            <table className="table table-sm table-bordered">
                                                <thead>
                                                    <tr>
                                                        <th>檢驗項目</th>
                                                        <th>檢驗結果</th>
                                                        <th>不良數量</th>
                                                        <th>檢驗人員</th>
                                                        <th>檢驗日期</th>
                                                        <th style={{ width: '100px' }}>操作</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {inspections.map((insp: any, idx: number) => (
                                                        <tr key={idx}>
                                                            <td>{insp.檢驗項目 || '-'}</td>
                                                            <td>{insp.檢驗結果 || '-'}</td>
                                                            <td>{insp.不良數量 || '0'}</td>
                                                            <td>{insp.檢驗人員 || '-'}</td>
                                                            <td>{insp.檢驗日期 || '-'}</td>
                                                            <td>
                                                                <div className="btn-group btn-group-sm">
                                                                    <button className="btn btn-outline-primary" onClick={() => handleEditInspection(insp)}>編輯</button>
                                                                    <button className="btn btn-outline-danger" onClick={() => handleDeleteInspection(insp.識別碼)}>刪除</button>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        ) : (
                                            <p className="text-muted">暂无品檢記錄</p>
                                        )}
                                    </div>
                                )}

                                {activeTab === 'cost' && (
                                    <div className="tab-pane fade show active">
                                        <div className="d-flex justify-content-between align-items-center mb-3">
                                            <h6 className="mb-0">成本分析</h6>
                                            <Button variant="primary" size="sm" onClick={() => setShowCostModal(true)}>
                                                <i className="bi bi-plus-lg"></i> 新增
                                            </Button>
                                        </div>
                                        {costs.length > 0 ? (
                                            <>
                                                <table className="table table-sm table-bordered">
                                                    <thead>
                                                        <tr>
                                                            <th>成本類型</th>
                                                            <th>成本項目</th>
                                                            <th>單位成本</th>
                                                            <th>數量</th>
                                                            <th>總成本</th>
                                                            <th>記錄日期</th>
                                                            <th style={{ width: '100px' }}>操作</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {costs.map((cost: any, idx: number) => (
                                                            <tr key={idx}>
                                                                <td>{cost.成本類型 || '-'}</td>
                                                                <td>{cost.成本項目 || '-'}</td>
                                                                <td>${parseFloat(cost.單位成本 || 0).toFixed(2)}</td>
                                                                <td>{cost.數量 || '0'}</td>
                                                                <td>${parseFloat(cost.總成本 || 0).toFixed(2)}</td>
                                                                <td>{cost.記錄日期 || '-'}</td>
                                                                <td>
                                                                    <div className="btn-group btn-group-sm">
                                                                        <button className="btn btn-outline-primary" onClick={() => handleEditCost(cost)}>編輯</button>
                                                                        <button className="btn btn-outline-danger" onClick={() => handleDeleteCost(cost.識別碼)}>刪除</button>
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                    <tfoot>
                                                        <tr className="table-secondary">
                                                            <td colSpan={4}><strong>總成本</strong></td>
                                                            <td colSpan={3}>
                                                                <strong>${costs.reduce((sum: number, c: any) => sum + parseFloat(c.總成本 || 0), 0).toFixed(2)}</strong>
                                                            </td>
                                                        </tr>
                                                    </tfoot>
                                                </table>
                                            </>
                                        ) : (
                                            <p className="text-muted">暂无成本記錄</p>
                                        )}
                                    </div>
                                )}
                            </div>
                        </>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowDetailModal(false)}>關閉</Button>
                </Modal.Footer>
            </Modal>

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
        </div>
    );
};

export default ReworkPage;
