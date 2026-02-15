import { useState, useEffect } from 'react';
import { Modal, Button, Form, Table, Alert } from 'react-bootstrap';
import api from '../../services/api';
import type { Inspector, Vendor, ShippingInspection, ToleranceResult } from '../../types';

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
// Group 1: Item 1 -> Item 2 -> ... -> Item N
// Group 2: ...
const ITEM_OFFSETS = ITEMS.reduce((acc, _, index) => {
    const prevOffset = index > 0 ? acc[index - 1] : 0;
    const prevCount = index > 0 ? (ITEMS[index - 1].type === 'minmax' ? 2 : 1) : 0;
    acc.push(prevOffset + prevCount);
    return acc;
}, [] as number[]);
const TOTAL_INPUTS_PER_GROUP = ITEM_OFFSETS[ITEMS.length - 1] + (ITEMS[ITEMS.length - 1].type === 'minmax' ? 2 : 1);

// 解析檢驗規格，取得各項目標準值
// 支援格式: 外徑*厚度*長度 (如 31.9*2.2*667) 或 外徑*內徑*長度 (如 25.4*19*5500)
const parseSpec = (spec: string): Record<string, number> => {
    if (!spec) return {};

    const parts = spec.replace(/×/g, '*').replace(/x/g, '*').split('*').map(p => parseFloat(p.trim()));
    const result: Record<string, number> = {};

    if (parts.length >= 2 && !isNaN(parts[0])) {
        // 第一個通常是外徑
        result['外徑'] = parts[0];

        if (parts[1] && !isNaN(parts[1])) {
            const val2 = parts[1];
            // 判斷第二個值是厚度還是內徑
            // 一般管材：厚度 < 外徑/2. 若數值很小則視為厚度，否則視為內徑
            // 增強邏輯：互推
            if (val2 < (parts[0] / 2)) {
                // 認定為厚度
                result['厚度'] = val2;
                result['內徑'] = parts[0] - (val2 * 2); // 推算內徑
            } else {
                // 認定為內徑
                result['內徑'] = val2;
                result['厚度'] = (parts[0] - val2) / 2; // 推算厚度
            }
        }

        if (parts[2] && !isNaN(parts[2])) {
            result['長度'] = parts[2];
        }
    }

    return result;
};

const ShippingModal = ({ show, handleClose, onSuccess, editId }: ShippingModalProps) => {
    const [inspectors, setInspectors] = useState<Inspector[]>([]);
    const [vendors, setVendors] = useState<Vendor[]>([]);

    // Form State
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [inspectorName, setInspectorName] = useState('');
    const [vendorName, setVendorName] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [orderNo, setOrderNo] = useState('');

    // Measurement Data: Key format: "外徑1-min", "同心度2"
    const [measurements, setMeasurements] = useState<Record<string, string>>({});

    // Tolerance State
    const [tolerance, setTolerance] = useState<ToleranceResult | null>(null);
    const [violations, setViolations] = useState<Record<string, boolean>>({});

    const loadOptions = async () => {
        try {
            const [insRes, venRes] = await Promise.all([
                api.get<Inspector[]>('/inspectors'),
                api.get<Vendor[]>('/vendors')
            ]);
            setInspectors(insRes.data);
            setVendors(venRes.data);
        } catch (e) {
            console.error(e);
        }
    };

    const loadEditData = async (id: number) => {
        try {
            const res = await api.get<ShippingInspection>(`/data/${id}`);
            const data = res.data;
            setDate(data.檢驗日期);
            setInspectorName(data.檢驗人員 || data.檢驗人員姓名 || '');
            setVendorName(data.廠商中文名稱);
            setMaterial(data.材質);
            setSpec(data.檢驗規格);
            setOrderNo(data.訂單號碼 || '');

            // Flatten measurements
            const m: Record<string, string> = {};
            ITEMS.forEach(item => {
                for (let g = 1; g <= 5; g++) {
                    if (item.type === 'minmax') {
                        m[`${item.key}${g}-min`] = data[`${item.key}${g}-min`] || '';
                        m[`${item.key}${g}-max`] = data[`${item.key}${g}-max`] || '';
                    } else {
                        m[`${item.key}${g}`] = data[`${item.key}${g}`] || '';
                    }
                }
            });
            setMeasurements(m);
        } catch (e) {
            console.error(e);
        }
    };

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

    useEffect(() => {
        if (show) {
            loadOptions();
            if (editId) {
                loadEditData(editId);
            } else {
                resetForm();
            }
        }
    }, [show, editId]);

    // Check tolerance when specific fields change
    useEffect(() => {
        const checkTolerance = async () => {
            if (!material || !spec || !vendorName) {
                setTolerance(null);
                return;
            }

            // Find vendor ID from name
            const vendorObj = vendors.find(v => v.name === vendorName);
            const vendorId = vendorObj ? vendorObj.id : '';

            try {
                const res = await api.get<ToleranceResult>(`/tolerance/check?vendor_id=${vendorId}&material=${encodeURIComponent(material)}&spec=${encodeURIComponent(spec)}`);
                if (res.data.success && res.data.found) {
                    setTolerance(res.data);
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
                let std = specValues[item.key];
                if (std === undefined || std === 0) {
                    std = tolItem.標準值;
                }
                std = std || 0;
                if (std === 0) return;
                lsl = std + (tolItem.公差下限 ?? 0);
                usl = std + (tolItem.公差上限 ?? 0);
            } else if (tolItem.尺寸上限 !== null) {
                // 只有尺寸上限（如同心度：最大 0.25）
                lsl = 0;
                usl = tolItem.尺寸上限;
            } else if (tolItem.尺寸下限 !== null) {
                // 只有尺寸下限
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
        // Collect payload
        const payload: any = {
            "檢驗日期": date,
            "檢驗人員姓名": inspectorName,
            "廠商中文名稱": vendorName,
            "檢驗規格": spec,
            "材質": material,
            "訂單號碼": orderNo,
            // Add flattened measurements
            ...measurements
        };

        if (editId) payload['識別碼'] = editId;

        const url = editId ? '/update' : '/add';

        try {
            await api.post(url, payload);
            alert('儲存成功');
            onSuccess();
            handleClose();
        } catch (error: any) {
            console.error(error);
            alert(error.response?.data?.error || '儲存失敗');
        }
    };

    return (
        <Modal show={show} onHide={handleClose} fullscreen>
            <Modal.Header closeButton>
                <Modal.Title>{editId ? `編輯紀錄 #${editId}` : '新增檢驗紀錄'}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    {/* Basic Info */}
                    <div className="row g-3 mb-4 bg-light p-3 rounded">
                        <div className="col-md-2">
                            <Form.Label>日期</Form.Label>
                            <Form.Control type="date" value={date} onChange={e => setDate(e.target.value)} />
                        </div>
                        <div className="col-md-2">
                            <Form.Label>人員</Form.Label>
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
                                        rangeDisplay = `尺寸${t.尺寸下限}~${t.尺寸上限}`;
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
                                                            className={`text-center shipping-input ${violations[`${item.key}${g}-min`] ? 'is-invalid-breathing' : ''}`}
                                                            value={measurements[`${item.key}${g}-min`] || ''}
                                                            onChange={e => handleMeasurementChange(`${item.key}${g}-min`, e.target.value)}
                                                            tabIndex={100 + (g - 1) * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx]}
                                                        />
                                                        <Form.Control
                                                            size="sm"
                                                            placeholder="Max"
                                                            className={`text-center shipping-input ${violations[`${item.key}${g}-max`] ? 'is-invalid-breathing' : ''}`}
                                                            value={measurements[`${item.key}${g}-max`] || ''}
                                                            onChange={e => handleMeasurementChange(`${item.key}${g}-max`, e.target.value)}
                                                            tabIndex={100 + (g - 1) * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx] + 1}
                                                        />
                                                    </div>
                                                ) : (
                                                    <Form.Control
                                                        size="sm"
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
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit}>儲存紀錄</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ShippingModal;
