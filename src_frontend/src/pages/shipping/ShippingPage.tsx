import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import type { ShippingInspection } from '../../types';
import ShippingModal from '../../components/shipping/ShippingModal';
import ImportModal from '../../components/shipping/ImportModal';
import ShippingCharts from '../../components/shipping/ShippingCharts';
import { useShippingList, useDeleteShipping } from '../../hooks/useShipping';

const parseSpec = (spec: string): Record<string, number> => {
    if (!spec) return {};
    const parts = spec.replace(/×/g, '*').replace(/x/g, '*').split('*').map(p => parseFloat(p.trim()));
    const result: Record<string, number> = {};

    if (parts.length >= 2 && !isNaN(parts[0])) {
        result['外徑'] = parts[0];
        if (parts[1] && !isNaN(parts[1])) {
            const val2 = parts[1];
            if (val2 < (parts[0] / 2)) {
                result['厚度'] = val2;
                result['內徑'] = parts[0] - (val2 * 2);
            } else {
                result['內徑'] = val2;
                result['厚度'] = (parts[0] - val2) / 2;
            }
        }
        if (parts[2] && !isNaN(parts[2])) {
            result['長度'] = parts[2];
        }
    }
    return result;
};

const ShippingPage = () => {
    const navigate = useNavigate();
    const [page, setPage] = useState(1);

    // Modal State
    const [showModal, setShowModal] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    // Filters
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [vendor, setVendor] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');

    // Tolerance Standards for the current page
    const [tolerances, setTolerances] = useState<Record<string, any>>({});

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

    // Fetch tolerances for all unique combinations on the current page
    // Note: keeping this logic here as it's quite specific batch fetching
    const fetchTolerances = async () => {
        if (inspections.length === 0) return;

        const uniqueCombos = new Set<string>();
        inspections.forEach(item => {
            if (item.材質) {
                uniqueCombos.add(`${item.材質}|||${item.檢驗規格 || ''}|||${item.廠商中文名稱 || ''}`);
            }
        });

        const newTolerances: Record<string, any> = { ...tolerances };

        // This part needs vendors list, we could use useVendors hook but we need it here imperatively or just fetch once
        // For simplicity, let's just fetch it as before or optimistically assume we have IDs if backend provided them.
        // The original code fetched /vendors every time inspections changed, which is not ideal.
        // Let's rely on cached vendors if possible, or just fetch.

        try {
            const vendorsRes = await api.get<any[]>('/vendors');
            const vendorMap: Record<string, string> = {};
            vendorsRes.data.forEach(v => vendorMap[v.name] = v.id);

            await Promise.all(Array.from(uniqueCombos).map(async (combo) => {
                if (newTolerances[combo]) return;

                const [mat, sp, vName] = combo.split('|||');
                const vId = vendorMap[vName] || '';

                try {
                    const res = await api.get<any>(`/tolerance/check?material=${encodeURIComponent(mat)}&spec=${encodeURIComponent(sp)}&vendor_id=${vId}`);
                    if (res.data.success && res.data.found) {
                        const specValues = parseSpec(sp);
                        const std: Record<string, { lsl: number, usl: number }> = {};
                        res.data.tolerances.forEach((t: any) => {
                            let lsl = -Infinity, usl = Infinity;
                            if (t.尺寸下限 !== null && t.尺寸上限 !== null) {
                                lsl = t.尺寸下限;
                                usl = t.尺寸上限;
                            } else if (t.公差下限 !== null && t.公差上限 !== null) {
                                let standardValue = specValues[t.項目];
                                if (standardValue === undefined || standardValue === 0) {
                                    standardValue = t.標準值;
                                }
                                standardValue = standardValue || 0;
                                if (standardValue === 0) return;
                                lsl = standardValue + t.公差下限;
                                usl = standardValue + t.公差上限;
                            } else if (t.尺寸上限 !== null) {
                                lsl = 0;
                                usl = t.尺寸上限;
                            } else if (t.尺寸下限 !== null) {
                                lsl = t.尺寸下限;
                                usl = Infinity;
                            } else {
                                return;
                            }
                            std[t.項目] = { lsl, usl };
                        });
                        newTolerances[combo] = std;
                    } else {
                        newTolerances[combo] = null;
                    }
                } catch (e) {
                    console.error('Fetch tolerance failed for', combo, e);
                }
            }));

            setTolerances(newTolerances);
        } catch (e) {
            console.error("Error fetching vendors for tolerance check", e);
        }
    };

    useEffect(() => {
        // Trigger fetchTolerances when inspections change
        fetchTolerances();
    }, [inspections]);

    // Refresh list when filters change is handled by React Query key

    const checkViolation = (item: ShippingInspection) => {
        const combo = `${item.材質}|||${item.檢驗規格 || ''}|||${item.廠商中文名稱 || ''}`;
        const std = tolerances[combo];
        if (!std) return { hasViolation: false, found: false };

        const items = ["外徑", "內徑", "厚度", "同心度", "長度", "硬度", "真直度"];
        let hasViolation = false;

        for (const it of items) {
            const tol = std[it];
            if (!tol) continue;

            for (let g = 1; g <= 5; g++) {
                const keys = it === "外徑" || it === "內徑" || it === "厚度"
                    ? [`${it}${g}-min`, `${it}${g}-max`]
                    : [`${it}${g}`];

                for (const k of keys) {
                    const val = parseFloat((item as any)[k]);
                    if (!isNaN(val) && (val < tol.lsl || val > tol.usl)) {
                        hasViolation = true;
                        break;
                    }
                }
                if (hasViolation) break;
            }
            if (hasViolation) break;
        }

        return { hasViolation, found: true };
    };

    const handleExport = () => {
        const token = localStorage.getItem('authToken');
        const url = `${api.defaults.baseURL?.replace('/api', '')}/api/export/excel?vendor=${vendor}&material=${material}&spec=${spec}&start_date=${startDate}&end_date=${endDate}&token=${token}`;
        window.location.href = url;
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
        if (!confirm(`確定刪除 ID: ${id}?`)) return;
        deleteMutation.mutate(id);
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
                                        return (
                                            <tr key={item.識別碼} className={hasViolation ? 'table-danger-subtle' : ''}>
                                                <td>{item.識別碼}</td>
                                                <td>{item.檢驗日期?.substring(0, 10)}</td>
                                                <td>{item.廠商中文名稱}</td>
                                                <td>{item.材質}</td>
                                                <td>{item.檢驗規格}</td>
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
                                                            onClick={() => handleEdit(item.識別碼)}
                                                        >
                                                            編輯
                                                        </button>
                                                        <button
                                                            className="btn btn-sm btn-outline-danger"
                                                            onClick={() => handleDelete(item.識別碼)}
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
        </div>
    );
};

export default ShippingPage;
