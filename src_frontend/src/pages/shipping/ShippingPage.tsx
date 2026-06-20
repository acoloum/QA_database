import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import type { ShippingInspection } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import ShippingModal from '../../components/shipping/ShippingModal';
import ImportModal from '../../components/shipping/ImportModal';
import ShippingCharts from '../../components/shipping/ShippingCharts';
import { useShippingList, useDeleteShipping } from '../../hooks/useShipping';
import { useShippingToleranceMap } from '../../hooks/useShippingToleranceMap';
import { downloadResponseBlob } from '../../utils/downloadFile';

const ShippingPage = () => {
    const navigate = useNavigate();
    const [page, setPage] = useState(1);

    // Modal State
    const [showModal, setShowModal] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    // Filters
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [vendor, setVendor] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');

    // Hooks
    const searchParams = {
        page,
        start_date: startDate,
        end_date: endDate,
        vendor,
        material,
        spec
    };

    const { data: searchResult, isLoading } = useShippingList(searchParams);
    const deleteMutation = useDeleteShipping();

    const inspections = searchResult?.data || [];
    const totalPages = searchResult?.total_pages || 1;
    const { data: tolerances = {} } = useShippingToleranceMap(inspections);

    // Refresh list when filters change is handled by React Query key

    const checkViolation = (item: ShippingInspection) => {
        const combo = `${item.材質 ?? item.material}|||${item.檢驗規格 ?? item.spec ?? ''}|||${item.廠商中文名稱 ?? item.vendor_name ?? ''}`;
        const std = tolerances[combo];
        if (!std) return { hasViolation: false, found: false };

        const MINMAX_ITEMS = new Set(["外徑", "內徑", "厚度"]);
        const ALL_ITEMS = ["外徑", "內徑", "真圓度", "厚度", "同心度", "長度", "硬度", "真直度", "韋伯氏硬度"];
        let hasViolation = false;

        // 量測值一律使用 measurements 巢狀物件
        if (item.measurements && Object.keys(item.measurements).length > 0) {
            outer: for (const [, groupData] of Object.entries(item.measurements)) {
                for (const itName of ALL_ITEMS) {
                    const tol = std[itName];
                    if (!tol) continue;
                    const measItem = groupData[itName];
                    if (!measItem) continue;

                    if (MINMAX_ITEMS.has(itName)) {
                        const minV = measItem.value_min != null ? Number(measItem.value_min) : NaN;
                        const maxV = measItem.value_max != null ? Number(measItem.value_max) : NaN;
                        if (!isNaN(minV) && (minV < tol.lsl || minV > tol.usl)) {
                            hasViolation = true;
                            break outer;
                        }
                        if (!isNaN(maxV) && (maxV < tol.lsl || maxV > tol.usl)) {
                            hasViolation = true;
                            break outer;
                        }
                    } else {
                        const v = measItem.value_single != null ? Number(measItem.value_single) : NaN;
                        if (!isNaN(v) && (v < tol.lsl || v > tol.usl)) {
                            hasViolation = true;
                            break outer;
                        }
                    }
                }
            }
        }

        return { hasViolation, found: true };
    };

    const handleExport = async () => {
        try {
            const response = await api.get('/export/excel', {
                params: { vendor, material, spec, start_date: startDate, end_date: endDate },
                responseType: 'blob'
            });
            downloadResponseBlob(response.data as BlobPart, '出貨檢驗數據.xlsx');
        } catch (error) {
            console.error('Export failed:', error);
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

    const handleDelete = async (id: number) => {
        setConfirmAction({
            title: '刪除出貨檢驗',
            message: `確定刪除 ID: ${id} 的出貨檢驗資料？`,
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => deleteMutation.mutateAsync(id),
        });
    };

    // Handler for successful modal operations (create/update)
    // React query invalidation handles the refresh, so we just close the modal
    const handleSuccess = () => {
        // refetch(); // Optional, but mutation invalidation should handle it
        // If we want to be sure or reset page:
        // refetch();
    };

    return (
        <div className="container-fluid px-4 py-4">
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold"><i className="bi bi-clipboard-check"></i> 出貨檢驗數據系統</h2>
                <div>
                    <button className="btn btn-outline-success me-2" onClick={handleExport}>
                        <i className="bi bi-file-earmark-excel"></i> 匯出 Excel
                    </button>
                    <button className="btn btn-outline-info me-2" onClick={() => setShowImportModal(true)}>
                        <i className="bi bi-upload"></i> 匯入 Excel
                    </button>
                    <button className="btn btn-primary me-2" onClick={handleAdd}>
                        <i className="bi bi-plus-lg"></i> 新增檢驗
                    </button>
                    <button className="btn btn-back-home" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="card mb-4 shadow-sm border-0 bg-light-subtle">
                <div className="card-body">
                    <div className="row g-3">
                        <div className="col-md-2">
                            <label className="form-label fw-semibold">開始日期</label>
                            <input
                                type="date"
                                className="form-control"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                            />
                        </div>
                        <div className="col-md-2">
                            <label className="form-label fw-semibold">結束日期</label>
                            <input
                                type="date"
                                className="form-control"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                            />
                        </div>
                        <div className="col-md-2">
                            <label className="form-label fw-semibold">廠商</label>
                            <input
                                type="text"
                                className="form-control"
                                placeholder="搜尋廠商..."
                                value={vendor}
                                onChange={(e) => setVendor(e.target.value)}
                            />
                        </div>
                        <div className="col-md-2">
                            <label className="form-label fw-semibold">材質</label>
                            <input
                                type="text"
                                className="form-control"
                                placeholder="搜尋材質..."
                                value={material}
                                onChange={(e) => setMaterial(e.target.value)}
                            />
                        </div>
                        <div className="col-md-2">
                            <label className="form-label fw-semibold">規格</label>
                            <input
                                type="text"
                                className="form-control"
                                placeholder="搜尋規格..."
                                value={spec}
                                onChange={(e) => setSpec(e.target.value)}
                            />
                        </div>
                        <div className="col-md-2 d-flex align-items-end">
                            <button
                                className="btn btn-secondary w-100"
                                onClick={() => {
                                    setStartDate('');
                                    setEndDate('');
                                    setVendor('');
                                    setMaterial('');
                                    setSpec('');
                                    setPage(1);
                                }}
                            >
                                <i className="bi bi-eraser"></i> 清除
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Charts Section */}
            {(vendor || material || spec) && (
                <div className="mb-4">
                    <ShippingCharts
                        vendor={vendor}
                        material={material}
                        spec={spec}
                        startDate={startDate}
                        endDate={endDate}
                        onPointClick={handleEdit}
                    />
                </div>
            )}

            {/* Data Table */}
            <div className="card shadow-sm border-0">
                <div className="card-body p-0">
                    <div className="table-responsive">
                        <table className="table table-hover align-middle table-compact mb-0">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>日期</th>
                                    <th>廠商</th>
                                    <th>材質</th>
                                    <th>規格</th>
                                    <th className="text-center">狀態</th>
                                    <th className="action-column">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isLoading ? (
                                    <tr>
                                        <td colSpan={7} className="text-center py-5">
                                            <div className="spinner-border text-primary" role="status">
                                                <span className="visually-hidden">Loading...</span>
                                            </div>
                                        </td>
                                    </tr>
                                ) : inspections.length === 0 ? (
                                    <tr>
                                        <td colSpan={7} className="text-center py-5 text-muted">
                                            查無資料
                                        </td>
                                    </tr>
                                ) : (
                                    inspections.map((item) => {
                                        const { hasViolation, found } = checkViolation(item);
                                        const itemId = item.識別碼 ?? item.id;
                                        const itemDate = item.檢驗日期 ?? item.date;
                                        const itemVendor = item.廠商中文名稱 ?? item.vendor_name;
                                        const itemMaterial = item.材質 ?? item.material;
                                        const itemSpec = item.檢驗規格 ?? item.spec;
                                        return (
                                            <tr key={itemId} className={hasViolation ? 'table-danger-subtle' : ''}>
                                                <td>{itemId}</td>
                                                <td>{itemDate?.substring(0, 10)}</td>
                                                <td>{itemVendor}</td>
                                                <td>{itemMaterial}</td>
                                                <td>{itemSpec}</td>
                                                <td className="text-center">
                                                    {!found ? (
                                                        <span className="badge bg-secondary">-</span>
                                                    ) : hasViolation ? (
                                                        <span className="badge bg-danger">⚠️ 超差</span>
                                                    ) : (
                                                        <span className="badge bg-success">✓ 合格</span>
                                                    )}
                                                </td>
                                                <td>
                                                    <div className="action-buttons">
                                                        <button
                                                            className="btn btn-sm btn-outline-primary"
                                                            onClick={() => handleEdit(itemId)}
                                                        >
                                                            編輯
                                                        </button>
                                                        <button
                                                            className="btn btn-sm btn-outline-danger"
                                                            onClick={() => handleDelete(itemId)}
                                                        >
                                                            刪除
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })
                                )}
                            </tbody>
                        </table>
                    </div>

                    {/* Pagination */}
                    <div className="d-flex justify-content-center py-4 bg-light-subtle rounded-bottom">
                        <nav>
                            <ul className="pagination mb-0">
                                <li className={`page-item ${page === 1 ? 'disabled' : ''}`}>
                                    <button className="page-link" onClick={() => setPage(p => Math.max(1, p - 1))}>
                                        上一頁
                                    </button>
                                </li>
                                <li className="page-item active">
                                    <span className="page-link">
                                        第 {page} / {totalPages} 頁
                                    </span>
                                </li>
                                <li className={`page-item ${page === totalPages ? 'disabled' : ''}`}>
                                    <button className="page-link" onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
                                        下一頁
                                    </button>
                                </li>
                            </ul>
                        </nav>
                    </div>
                </div>
            </div>

            <ShippingModal
                show={showModal}
                handleClose={() => setShowModal(false)}
                onSuccess={handleSuccess}
                editId={editId}
            />

            <ImportModal
                show={showImportModal}
                handleClose={() => setShowImportModal(false)}
                onSuccess={handleSuccess}
            />
            <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </div>
    );
};

export default ShippingPage;
