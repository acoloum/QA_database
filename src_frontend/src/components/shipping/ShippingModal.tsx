import { useState, useEffect } from 'react';
import { Modal, Button, Form, Table, Alert } from 'react-bootstrap';
import toast from 'react-hot-toast';
import type { ToleranceResult } from '../../types';
import {
    useInspectors,
    useVendors,
    useShippingDetail,
    useCreateShipping,
    useUpdateShipping,
    useCheckTolerance
} from '../../hooks/useShipping';

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
}

const ITEMS: ItemConfig[] = [
    { label: "外徑", key: "外徑", type: "minmax" },
    { label: "內徑", key: "內徑", type: "minmax" },
    { label: "厚度", key: "厚度", type: "minmax" },
    { label: "同心度", key: "同心度", type: "single" },
    { label: "長度", key: "長度", type: "single" },
    { label: "硬度", key: "硬度", type: "single" },
    { label: "真直度", key: "真直度", type: "single" }
];

// Pre-calculate offsets for tab index (Vertical Traversal)
const ITEM_OFFSETS = ITEMS.reduce((acc, _, index) => {
    const prevOffset = index > 0 ? acc[index - 1] : 0;
    const prevCount = index > 0 ? (ITEMS[index - 1].type === 'minmax' ? 2 : 1) : 0;
    acc.push(prevOffset + prevCount);
    return acc;
}, [] as number[]);
const TOTAL_INPUTS_PER_GROUP = ITEM_OFFSETS[ITEMS.length - 1] + (ITEMS[ITEMS.length - 1].type === 'minmax' ? 2 : 1);

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

const ShippingModal = ({ show, handleClose, onSuccess, editId }: ShippingModalProps) => {
    // Hooks
    const { data: inspectors = [] } = useInspectors();
    const { data: vendors = [] } = useVendors();
    const { data: detailData, isLoading: isLoadingDetail } = useShippingDetail(editId);

    const createMutation = useCreateShipping();
    const updateMutation = useUpdateShipping();
    const checkToleranceMutation = useCheckTolerance();

    // Form State
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [inspectorName, setInspectorName] = useState('');
    const [vendorName, setVendorName] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [orderNo, setOrderNo] = useState('');

    // Measurement Data
    const [measurements, setMeasurements] = useState<Record<string, string>>({});

    // Tolerance State
    const [tolerance, setTolerance] = useState<ToleranceResult | null>(null);
    const [violations, setViolations] = useState<Record<string, boolean>>({});

    const resetForm = () => {
        setDate(new Date().toISOString().split('T')[0]);
        setInspectorName('');
        setVendorName('');
        setMaterial('');
        setSpec('');
        setOrderNo('');
        setMeasurements({});
        setTolerance(null);
        setViolations({});
    };

    // Populate form when detailData loads or when modal opens
    useEffect(() => {
        if (show) {
            if (editId && detailData) {
                setDate(detailData.檢驗日期);
                setInspectorName(detailData.檢驗人員 || detailData.檢驗人員姓名 || '');
                setVendorName(detailData.廠商中文名稱);
                setMaterial(detailData.材質);
                setSpec(detailData.檢驗規格);
                setOrderNo(detailData.訂單號碼 || '');

                const m: Record<string, string> = {};
                ITEMS.forEach(item => {
                    for (let g = 1; g <= 5; g++) {
                        if (item.type === 'minmax') {
                            m[`${item.key}${g}-min`] = (detailData as any)[`${item.key}${g}-min`] || '';
                            m[`${item.key}${g}-max`] = (detailData as any)[`${item.key}${g}-max`] || '';
                        } else {
                            m[`${item.key}${g}`] = (detailData as any)[`${item.key}${g}`] || '';
                        }
                    }
                });
                setMeasurements(m);
            } else if (!editId) {
                resetForm();
            }
        }
    }, [show, editId, detailData]);

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
                const result = await checkToleranceMutation.mutateAsync({
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
    }, [material, spec, vendorName, vendors]);

    // Validate measurements against tolerance
    useEffect(() => {
        if (!tolerance) {
            setViolations({});
            return;
        }

        const newViolations: Record<string, boolean> = {};
        const specValues = parseSpec(spec);

        ITEMS.forEach(item => {
            const tolItem = tolerance.tolerances.find(t => t.項目 === item.key);
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

            for (let g = 1; g <= 5; g++) {
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

    }, [measurements, tolerance, spec]);

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

        if (validationErrors.length > 0) {
            toast.error(validationErrors.join('、'));
            return;
        }

        const payload: any = {
            "檢驗日期": date,
            "檢驗人員姓名": inspectorName,
            "廠商中文名稱": vendorName,
            "檢驗規格": spec,
            "材質": material,
            "訂單號碼": orderNo,
            ...measurements
        };

        if (editId) payload['識別碼'] = editId;

        try {
            if (editId) {
                await updateMutation.mutateAsync({ id: editId, data: payload });
            } else {
                await createMutation.mutateAsync(payload);
            }
            onSuccess();
            handleClose();
        } catch (error) {
            // Error is already handled by mutation's onError
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
                                        {[1, 2, 3, 4, 5].map(i => <th key={i}>{i}</th>)}
                                    </tr>
                                </thead>
                                <tbody>
                                    {ITEMS.map((item, idx) => (
                                        <tr key={item.key}>
                                            <th className="bg-light text-nowrap">{item.label}</th>
                                            {[1, 2, 3, 4, 5].map(g => (
                                                <td key={g} className={item.type === 'minmax' ? 'shipping-cell-double' : 'shipping-cell-single'}>
                                                    {item.type === 'minmax' ? (
                                                        <div className="d-flex gap-2 justify-content-center flex-nowrap">
                                                            <Form.Control
                                                                size="sm"
                                                                placeholder="Min"
                                                                style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                                className={`text-center shipping-input ${violations[`${item.key}${g}-min`] ? 'is-invalid-breathing' : ''}`}
                                                                value={measurements[`${item.key}${g}-min`] || ''}
                                                                onChange={e => handleMeasurementChange(`${item.key}${g}-min`, e.target.value)}
                                                                tabIndex={100 + (g - 1) * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx]}
                                                            />
                                                            <Form.Control
                                                                size="sm"
                                                                placeholder="Max"
                                                                style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                                className={`text-center shipping-input ${violations[`${item.key}${g}-max`] ? 'is-invalid-breathing' : ''}`}
                                                                value={measurements[`${item.key}${g}-max`] || ''}
                                                                onChange={e => handleMeasurementChange(`${item.key}${g}-max`, e.target.value)}
                                                                tabIndex={100 + (g - 1) * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx] + 1}
                                                            />
                                                        </div>
                                                    ) : (
                                                        <Form.Control
                                                            size="sm"
                                                            style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                            className={`text-center mx-auto shipping-input ${violations[`${item.key}${g}`] ? 'is-invalid-breathing' : ''}`}
                                                            value={measurements[`${item.key}${g}`] || ''}
                                                            onChange={e => handleMeasurementChange(`${item.key}${g}`, e.target.value)}
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
