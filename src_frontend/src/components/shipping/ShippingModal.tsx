import { useState, useEffect, useMemo } from 'react';
import { Modal, Button, Form, Table, Alert } from 'react-bootstrap';
import toast from 'react-hot-toast';
import type { ToleranceResult, ShippingCreateInput } from '../../types';
import {
    useInspectors,
    useVendors,
    useShippingDetail,
    useCreateShipping,
    useUpdateShipping,
    useCheckTolerance
} from '../../hooks/useShipping';
import { parseSpec } from '../../utils/parseSpec';

interface ShippingModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

interface ItemConfig {
    label: string;
    key: string;
    type: 'minmax' | 'single';
    /** 公差比對用的測量項目名稱，不設則與 key 相同 */
    toleranceKey?: string;
}

// Base items for all vendors
const BASE_ITEMS: ItemConfig[] = [
    { label: "外徑", key: "外徑", type: "minmax" },
    { label: "內徑", key: "內徑", type: "minmax" },
    { label: "厚度", key: "厚度", type: "minmax" },
    { label: "同心度", key: "同心度", type: "single" },
    { label: "長度", key: "長度", type: "single" },
    { label: "硬度", key: "硬度", type: "single" },
    { label: "真直度", key: "真直度", type: "single" }
];

// Additional items for 安泰 vendor
const ROUNDNESS_ITEM: ItemConfig = { label: "真圓度", key: "真圓度", type: "single" };
const VICKERS_HARDNESS_ITEM: ItemConfig = { label: "韋伯氏硬度(HW)", key: "韋伯氏硬度", type: "single" };

// Vendor name that requires extra features
const ANTAI_VENDOR_NAME = "安泰";

const DEFAULT_GROUP_COUNT = 5;

const ShippingModal = ({ show, handleClose, onSuccess, editId }: ShippingModalProps) => {
    // Hooks
    const { data: inspectors = [] } = useInspectors();
    const { data: vendors = [] } = useVendors();
    const { data: detailData, isLoading: isLoadingDetail } = useShippingDetail(editId);

    const createMutation = useCreateShipping();
    const updateMutation = useUpdateShipping();
    const { mutateAsync: checkToleranceMutate } = useCheckTolerance();

    // Form State
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [inspectorName, setInspectorName] = useState('');
    const [vendorName, setVendorName] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [orderNo, setOrderNo] = useState('');
    const [groupCount, setGroupCount] = useState(DEFAULT_GROUP_COUNT);

    // Measurement Data
    const [measurements, setMeasurements] = useState<Record<string, string>>({});

    // Tolerance State
    const [tolerance, setTolerance] = useState<ToleranceResult | null>(null);
    const [violations, setViolations] = useState<Record<string, boolean>>({});

    // 欄位格式錯誤（key: 欄位名稱, value: 錯誤訊息）
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

    // Determine if current vendor is 安泰
    const isAntai = vendorName === ANTAI_VENDOR_NAME;

    // Active items based on vendor
    // 安泰：真圓度插入內徑後、硬度改標示為洛氏硬度(HRB)、新增韋伯氏硬度(HW)
    const ITEMS = useMemo(() => {
        if (!isAntai) return BASE_ITEMS;
        const items = [...BASE_ITEMS];
        // 真圓度插在內徑後面（index 2）
        items.splice(2, 0, ROUNDNESS_ITEM);
        // 將硬度改標示為洛氏硬度(HRB)，並設 toleranceKey 對應公差表中的「洛氏硬度」
        const hardnessIdx = items.findIndex(item => item.key === '硬度');
        if (hardnessIdx !== -1) {
            items[hardnessIdx] = { ...items[hardnessIdx], label: '洛氏硬度(HRB)', toleranceKey: '洛氏硬度' };
            // 韋伯氏硬度(HW) 插在洛氏硬度後面
            items.splice(hardnessIdx + 1, 0, VICKERS_HARDNESS_ITEM);
        }
        return items;
    }, [isAntai]);

    // Dynamic group indices
    const groupIndices = useMemo(() => {
        return Array.from({ length: groupCount }, (_, i) => i + 1);
    }, [groupCount]);

    // Pre-calculate offsets for tab index (Vertical Traversal)
    const { ITEM_OFFSETS, TOTAL_INPUTS_PER_GROUP } = useMemo(() => {
        const offsets = ITEMS.reduce((acc, _, index) => {
            const prevOffset = index > 0 ? acc[index - 1] : 0;
            const prevCount = index > 0 ? (ITEMS[index - 1].type === 'minmax' ? 2 : 1) : 0;
            acc.push(prevOffset + prevCount);
            return acc;
        }, [] as number[]);
        const total = offsets[ITEMS.length - 1] + (ITEMS[ITEMS.length - 1].type === 'minmax' ? 2 : 1);
        return { ITEM_OFFSETS: offsets, TOTAL_INPUTS_PER_GROUP: total };
    }, [ITEMS]);

    const resetForm = () => {
        setDate(new Date().toISOString().split('T')[0]);
        setInspectorName('');
        setVendorName('');
        setMaterial('');
        setSpec('');
        setOrderNo('');
        setGroupCount(DEFAULT_GROUP_COUNT);
        setMeasurements({});
        setTolerance(null);
        setViolations({});
        setFieldErrors({});
    };

    // Populate form when detailData loads or when modal opens
    useEffect(() => {
        if (show) {
            if (editId && detailData) {
                // eslint-disable-next-line react-hooks/set-state-in-effect
                setDate(detailData.檢驗日期);
                 
                setInspectorName(String(detailData.檢驗人員 ?? '') || String(detailData.檢驗人員姓名 ?? '') || '');

                setVendorName(String(detailData.廠商中文名稱 ?? ''));

                setMaterial(String(detailData.材質 ?? ''));

                setSpec(String(detailData.檢驗規格 ?? ''));
                 
                setOrderNo(detailData.訂單號碼 || '');

                // Restore group count from saved data
                const savedGroupCount = (detailData as unknown as { 組數?: number }).組數 || DEFAULT_GROUP_COUNT;
                 
                setGroupCount(savedGroupCount);

                // Determine items based on vendor for loading measurements
                const loadVendor = detailData.廠商中文名稱;
                const loadItems = loadVendor === ANTAI_VENDOR_NAME
                    ? [...BASE_ITEMS, ROUNDNESS_ITEM, VICKERS_HARDNESS_ITEM]
                    : BASE_ITEMS;

                const m: Record<string, string> = {};
                loadItems.forEach(item => {
                    for (let g = 1; g <= 10; g++) {
                        const rawVal = (detailData as unknown as Record<string, unknown>)[`${item.key}${g}`];
                        if (item.type === 'minmax') {
                            m[`${item.key}${g}-min`] = (detailData as unknown as Record<string, unknown>)[`${item.key}${g}-min`] == null ? '' : String((detailData as unknown as Record<string, unknown>)[`${item.key}${g}-min`]);
                            m[`${item.key}${g}-max`] = (detailData as unknown as Record<string, unknown>)[`${item.key}${g}-max`] == null ? '' : String((detailData as unknown as Record<string, unknown>)[`${item.key}${g}-max`]);
                        } else {
                            m[`${item.key}${g}`] = rawVal == null ? '' : String(rawVal);
                        }
                    }
                });
                 
                setMeasurements(m);
            } else if (!editId) {
                resetForm();
            }
        }
    }, [show, editId, detailData]);

    // Reset groupCount when vendor changes (only for new records)
    useEffect(() => {
        if (!editId) {
            if (vendorName === ANTAI_VENDOR_NAME) {
                // Keep current groupCount or default — user can change via dropdown
            } else {
                // eslint-disable-next-line react-hooks/set-state-in-effect
                setGroupCount(DEFAULT_GROUP_COUNT);
            }
        }
    }, [vendorName, editId]);

    // Check tolerance when specific fields change
    useEffect(() => {
        const checkTolerance = async () => {
            if (!material || !spec || !vendorName) {
                 
                setTolerance(null);
                return;
            }

            const vendorObj = vendors.find(v => v.name === vendorName);
            const vendorId = vendorObj ? vendorObj.id : '';

            try {
                const result = await checkToleranceMutate({
                    vendor_id: vendorId,
                    material,
                    spec
                });

                if (result.success && result.found) {
                     
                    setTolerance(result);
                } else {
                     
                    setTolerance(null);
                }
            } catch (e) {
                console.error(e);
                 
                setTolerance(null);
            }
        };

        const timeout = setTimeout(checkTolerance, 500);
        return () => clearTimeout(timeout);
    }, [material, spec, vendorName, vendors, checkToleranceMutate]);

    // Validate measurements against tolerance
    useEffect(() => {
        if (!tolerance) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setViolations({});
            return;
        }

        const newViolations: Record<string, boolean> = {};
        const specValues = parseSpec(spec);

        ITEMS.forEach(item => {
            const tolItem = tolerance.tolerances.find(t => t.項目 === (item.toleranceKey ?? item.key));
            if (!tolItem) return;

            let lsl = -Infinity, usl = Infinity;

            if (tolItem.尺寸下限 !== null && tolItem.尺寸上限 !== null) {
                lsl = tolItem.尺寸下限;
                usl = tolItem.尺寸上限;
            } else if (tolItem.公差下限 !== null && tolItem.公差上限 !== null) {
                let std: number = specValues[item.key] ?? 0;
                if (std === 0 && tolItem.標準值 !== null) {
                    std = tolItem.標準值;
                }
                std = std || 0;
                if (std === 0) return;
                lsl = std + (tolItem.公差下限 ?? 0);
                usl = std + (tolItem.公差上限 ?? 0);
            } else if (tolItem.尺寸上限 !== null) {
                lsl = 0;
                usl = tolItem.尺寸上限;
            } else if (tolItem.尺寸下限 !== null) {
                lsl = tolItem.尺寸下限 ?? -Infinity;
                usl = Infinity;
            } else {
                return;
            }

            for (const g of groupIndices) {
                if (item.type === 'minmax') {
                    const minKey = `${item.key}${g}-min`;
                    const maxKey = `${item.key}${g}-max`;
                    const minVal = parseFloat(measurements[minKey]);
                    const maxVal = parseFloat(measurements[maxKey]);

                    if (!isNaN(minVal) && (minVal < lsl || minVal > usl)) newViolations[minKey] = true;
                    if (!isNaN(maxVal) && (maxVal < lsl || maxVal > usl)) newViolations[maxKey] = true;
                } else {
                    const key = `${item.key}${g}`;
                    const val = parseFloat(measurements[key]);
                    if (!isNaN(val) && (val < lsl || val > usl)) newViolations[key] = true;
                }
            }
        });

         
        setViolations(newViolations);

    }, [measurements, tolerance, spec, groupIndices, ITEMS]);

    // 呼吸動畫：每 750ms 切換 breathing-active class（JS 驅動，繞過 CSS animation 屬性衝突）
    // 依賴 hasViolations 而非 violations 物件，避免每次 keystroke 重啟 interval 導致 class 永遠是 active
    const hasViolations = Object.keys(violations).length > 0;
    useEffect(() => {
        if (!hasViolations) {
            document.querySelectorAll<HTMLInputElement>('.shipping-input.is-invalid-breathing')
                .forEach(el => el.classList.remove('breathing-active'));
            return;
        }

        let active = false;
        const interval = setInterval(() => {
            active = !active;
            const els = document.querySelectorAll<HTMLInputElement>('.shipping-input.is-invalid-breathing');
            els.forEach(el => {
                if (active) el.classList.add('breathing-active');
                else el.classList.remove('breathing-active');
            });
        }, 750);

        return () => clearInterval(interval);
    }, [hasViolations]);

    const handleMeasurementChange = (key: string, val: string) => {
        setMeasurements(prev => ({ ...prev, [key]: val }));
    };

    const handleSubmit = async () => {
        // Client-side validation
        const validationErrors: string[] = [];
        if (!date) validationErrors.push('請選擇檢驗日期');
        if (!inspectorName) validationErrors.push('請選擇檢驗人員');
        if (!vendorName) validationErrors.push('請選擇廠商');
        if (!spec) validationErrors.push('請輸入檢驗規格');
        if (!material) validationErrors.push('請輸入材質');

        // 測量欄位數字格式驗證（使用嚴格 regex，避免 parseFloat("40.06+") → 40.06 的問題）
        const newFieldErrors: Record<string, string> = {};
        const numPattern = /^[+-]?\d+(\.\d+)?$/;
        ITEMS.forEach(item => {
            for (let g = 1; g <= groupCount; g++) {
                if (item.type === 'minmax') {
                    const minKey = `${item.key}${g}-min`;
                    const maxKey = `${item.key}${g}-max`;
                    const minVal = measurements[minKey];
                    const maxVal = measurements[maxKey];

                    if (minVal && !numPattern.test(minVal)) {
                        newFieldErrors[minKey] = `「${item.label}${g}最小值」需為有效數字`;
                    }
                    if (maxVal && !numPattern.test(maxVal)) {
                        newFieldErrors[maxKey] = `「${item.label}${g}最大值」需為有效數字`;
                    }
                } else {
                    const key = `${item.key}${g}`;
                    const val = measurements[key];
                    if (val && !numPattern.test(val)) {
                        newFieldErrors[key] = `「${item.label}${g}」需為有效數字`;
                    }
                }
            }
        });

        setFieldErrors(newFieldErrors);

        if (validationErrors.length > 0) {
            toast.error(validationErrors.join('、'));
            return;
        }

        if (Object.keys(newFieldErrors).length > 0) {
            // 顯示第一個欄位錯誤
            const firstError = Object.values(newFieldErrors)[0];
            toast.error(firstError);
            return;
        }

        const basePayload: ShippingCreateInput = {
            "檢驗日期": date,
            "檢驗人員姓名": inspectorName,
            "廠商中文名稱": vendorName,
            "檢驗規格": spec,
            "材質": material,
            "訂單號碼": orderNo,
            "組數": groupCount,
            ...measurements
        };

        try {
            if (editId) {
                // 更新時加入識別碼以符合 ShippingUpdateInput 要求
                const updatePayload = { ...basePayload, 識別碼: editId };
                await updateMutation.mutateAsync({ id: editId, data: updatePayload });
            } else {
                await createMutation.mutateAsync(basePayload);
            }
            onSuccess();
            handleClose();
        } catch (error: unknown) {
            const err = error as { field?: string; message?: string; _toasted?: boolean };
            const fieldInfo = err?.field;
            if (fieldInfo) {
                setFieldErrors({ [fieldInfo]: err.message ?? '欄位驗證失敗' });
            } else {
                setFieldErrors({});
                // 若 api.ts 尚未顯示 toast（_toasted 不為 true），才顯示
                if (!err?._toasted) {
                    toast.error(err?.message || '發生未知錯誤');
                }
            }
            console.error(error);
        }
    };

    const isSaving = createMutation.isPending || updateMutation.isPending;

    return (
        <Modal show={show} onHide={handleClose} size="xl" dialogClassName="modal-shipping-wide">
            <Modal.Header closeButton>
                <Modal.Title>{editId ? `編輯紀錄 #${editId}` : '新增檢驗紀錄'}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {editId && isLoadingDetail ? (
                    <div className="text-center py-5">
                        <div className="spinner-border text-primary" role="status">
                            <span className="visually-hidden">Loading...</span>
                        </div>
                    </div>
                ) : (
                    <Form>
                        {/* Basic Info */}
                        <div className="row g-3 mb-4 bg-light p-3 rounded">
                            <div className="col-md-2">
                                <Form.Label>日期</Form.Label>
                                <Form.Control type="date" value={date} onChange={e => setDate(e.target.value)} />
                            </div>
                            <div className="col-md-2">
                                <Form.Label>檢驗人員</Form.Label>
                                <Form.Select value={inspectorName} onChange={e => setInspectorName(e.target.value)}>
                                    <option value="">請選擇</option>
                                    {inspectors.map(i => <option key={i.id} value={i.name}>{i.name}</option>)}
                                </Form.Select>
                            </div>
                            <div className="col-md-2">
                                <Form.Label>廠商</Form.Label>
                                <Form.Select value={vendorName} onChange={e => setVendorName(e.target.value)}>
                                    <option value="">請選擇</option>
                                    {vendors.map(v => <option key={v.id} value={v.name}>{v.name}</option>)}
                                </Form.Select>
                            </div>
                            <div className="col-md-2">
                                <Form.Label>規格</Form.Label>
                                <Form.Control value={spec} onChange={e => setSpec(e.target.value)} />
                            </div>
                            <div className="col-md-2">
                                <Form.Label>材質</Form.Label>
                                <Form.Control value={material} onChange={e => setMaterial(e.target.value)} />
                            </div>
                            <div className="col-md-2">
                                <Form.Label>訂單</Form.Label>
                                <Form.Control value={orderNo} onChange={e => setOrderNo(e.target.value)} />
                            </div>
                        </div>

                        {/* Group Count Selector — Only for 安泰 */}
                        {isAntai && (
                            <div className="row g-3 mb-3">
                                <div className="col-md-3">
                                    <Form.Label className="fw-bold text-primary">
                                        <i className="bi bi-sliders me-1"></i>
                                        檢驗組數
                                    </Form.Label>
                                    <Form.Select
                                        value={groupCount}
                                        onChange={e => setGroupCount(parseInt(e.target.value))}
                                    >
                                        {Array.from({ length: 8 }, (_, i) => i + 3).map(n => (
                                            <option key={n} value={n}>{n} 組</option>
                                        ))}
                                    </Form.Select>
                                </div>
                                <div className="col-md-9 d-flex align-items-end">
                                    <small className="text-muted">
                                        📋 安泰廠商可自訂檢驗組數（3~10組），其他廠商固定為 5 組
                                    </small>
                                </div>
                            </div>
                        )}

                        {/* Tolerance Info */}
                        {tolerance && (
                            <Alert variant="info" className="mb-4">
                                <h6 className="alert-heading">📐 公差標準已載入</h6>
                                <div className="d-flex flex-wrap gap-3">
                                    {tolerance.tolerances.map((t, idx) => {
                                        let rangeDisplay = '';
                                        if (t.尺寸下限 !== null && t.尺寸上限 !== null) {
                                            rangeDisplay = `${t.尺寸下限}~${t.尺寸上限}`;
                                        } else if (t.公差上限 !== null && t.公差下限 !== null) {
                                            const max = t.公差上限;
                                            const min = t.公差下限;
                                            if (max === min) {
                                                rangeDisplay = `±${max}`;
                                            } else if (min === 0 && max > 0) {
                                                rangeDisplay = `+${max}/-${min}`;
                                            } else if (max === 0 && min < 0) {
                                                rangeDisplay = `+${max}/${min}`;
                                            } else {
                                                rangeDisplay = `+${max}/${min}`;
                                            }
                                        } else if (t.尺寸上限 !== null) {
                                            rangeDisplay = `最大${t.尺寸上限}`;
                                        } else if (t.尺寸下限 !== null) {
                                            rangeDisplay = `最小${t.尺寸下限}`;
                                        } else if (t.公差上限 !== null) {
                                            rangeDisplay = `±${t.公差上限}`;
                                        } else if (t.公差下限 !== null) {
                                            rangeDisplay = `${t.公差下限}`;
                                        }
                                        return (
                                            <span key={idx} className="badge bg-primary">
                                                {t.項目}: {rangeDisplay} {t.單位}
                                            </span>
                                        );
                                    })}
                                </div>
                            </Alert>
                        )}

                        {/* Measurements Table */}
                        <div className="table-responsive">
                            <Table bordered className="text-center align-middle shipping-table">
                                <thead className="table-primary">
                                    <tr>
                                        <th className="text-nowrap">項目 \ 組別</th>
                                        {groupIndices.map(i => <th key={i}>{i}</th>)}
                                    </tr>
                                </thead>
                                <tbody>
                                    {ITEMS.map((item, idx) => (
                                        <tr key={item.key}>
                                            <th className="bg-light text-nowrap">{item.label}</th>
                                            {groupIndices.map(g => (
                                                <td key={g} className={item.type === 'minmax' ? 'shipping-cell-double' : 'shipping-cell-single'}>
                                                    {item.type === 'minmax' ? (
                                                        <div className="d-flex gap-2 justify-content-center flex-nowrap">
                                                            <Form.Control
                                                                size="sm"
                                                                placeholder="Min"
                                                                style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                                className={`text-center shipping-input ${fieldErrors[`${item.key}${g}-min`] ? 'is-invalid-format' : ''} ${violations[`${item.key}${g}-min`] ? 'is-invalid-breathing' : ''}`}
                                                                value={measurements[`${item.key}${g}-min`] ?? ''}
                                                                onChange={e => {
                                                                    handleMeasurementChange(`${item.key}${g}-min`, e.target.value);
                                                                    if (fieldErrors[`${item.key}${g}-min`]) {
                                                                        setFieldErrors(prev => {
                                                                            const next = { ...prev };
                                                                            delete next[`${item.key}${g}-min`];
                                                                            return next;
                                                                        });
                                                                    }
                                                                }}
                                                                tabIndex={100 + (g - 1) * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx]}
                                                            />
                                                            <Form.Control
                                                                size="sm"
                                                                placeholder="Max"
                                                                style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                                className={`text-center shipping-input ${fieldErrors[`${item.key}${g}-max`] ? 'is-invalid-format' : ''} ${violations[`${item.key}${g}-max`] ? 'is-invalid-breathing' : ''}`}
                                                                value={measurements[`${item.key}${g}-max`] ?? ''}
                                                                onChange={e => {
                                                                    handleMeasurementChange(`${item.key}${g}-max`, e.target.value);
                                                                    if (fieldErrors[`${item.key}${g}-max`]) {
                                                                        setFieldErrors(prev => {
                                                                            const next = { ...prev };
                                                                            delete next[`${item.key}${g}-max`];
                                                                            return next;
                                                                        });
                                                                    }
                                                                }}
                                                                tabIndex={100 + (g - 1) * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx] + 1}
                                                            />
                                                        </div>
                                                    ) : (
                                                        <Form.Control
                                                            size="sm"
                                                            style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                            className={`text-center mx-auto shipping-input ${fieldErrors[`${item.key}${g}`] ? 'is-invalid-format' : ''} ${violations[`${item.key}${g}`] ? 'is-invalid-breathing' : ''}`}
                                                            value={measurements[`${item.key}${g}`] ?? ''}
                                                            onChange={e => {
                                                                handleMeasurementChange(`${item.key}${g}`, e.target.value);
                                                                if (fieldErrors[`${item.key}${g}`]) {
                                                                    setFieldErrors(prev => {
                                                                        const next = { ...prev };
                                                                        delete next[`${item.key}${g}`];
                                                                        return next;
                                                                    });
                                                                }
                                                            }}
                                                            tabIndex={100 + (g - 1) * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx]}
                                                        />
                                                    )}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </Table>
                        </div>
                    </Form>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={isSaving}>
                    {isSaving ? '儲存中...' : '儲存紀錄'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ShippingModal;
