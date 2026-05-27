import { useState, useEffect, useMemo } from 'react';
import { Modal, Button, Form, Table, Alert } from 'react-bootstrap';
import toast from 'react-hot-toast';
import type { ToleranceResult, ShippingCreateInput, ShippingMeasurementItem, ShippingMeasurements } from '../../types';
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

// 所有廠商的基本量測項目
const BASE_ITEMS: ItemConfig[] = [
    { label: "外徑", key: "外徑", type: "minmax" },
    { label: "內徑", key: "內徑", type: "minmax" },
    { label: "厚度", key: "厚度", type: "minmax" },
    { label: "同心度", key: "同心度", type: "single" },
    { label: "長度", key: "長度", type: "single" },
    { label: "硬度", key: "硬度", type: "single" },
    { label: "真直度", key: "真直度", type: "single" }
];

// 安泰廠商的額外量測項目
const ROUNDNESS_ITEM: ItemConfig = { label: "真圓度", key: "真圓度", type: "single" };
const VICKERS_HARDNESS_ITEM: ItemConfig = { label: "韋伯氏硬度(HW)", key: "韋伯氏硬度", type: "single" };

// 安泰廠商名稱
const ANTAI_VENDOR_NAME = "安泰";

const DEFAULT_GROUP_COUNT = 5;

/** 每組量測的資料結構 */
type GroupMeas = Record<string, Partial<ShippingMeasurementItem>>;

/** 建立空白的量測組（所有項目皆為空） */
const emptyGroup = (items: ItemConfig[]): GroupMeas =>
    Object.fromEntries(items.map(item => [item.key, { is_ng: false }]));

const ShippingModal = ({ show, handleClose, onSuccess, editId }: ShippingModalProps) => {
    // Hooks
    const { data: inspectors = [] } = useInspectors();
    const { data: vendors = [] } = useVendors();
    const { data: detailData, isLoading: isLoadingDetail } = useShippingDetail(editId);

    const createMutation = useCreateShipping();
    const updateMutation = useUpdateShipping();
    const { mutateAsync: checkToleranceMutate } = useCheckTolerance();

    // 表單基本欄位
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [inspectorName, setInspectorName] = useState('');
    const [vendorName, setVendorName] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [orderNo, setOrderNo] = useState('');
    const [groupCount, setGroupCount] = useState(DEFAULT_GROUP_COUNT);

    // 新格式量測資料：Record<組號字串, Record<項目名稱, Partial<ShippingMeasurementItem>>>
    const [groups, setGroups] = useState<Record<string, GroupMeas>>({});

    // 公差狀態
    const [tolerance, setTolerance] = useState<ToleranceResult | null>(null);
    const [violations, setViolations] = useState<Record<string, boolean>>({});

    // 欄位格式錯誤（key: 欄位名稱, value: 錯誤訊息）
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

    // 判斷是否為安泰廠商
    const isAntai = vendorName === ANTAI_VENDOR_NAME;

    // 依廠商決定量測項目清單
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

    // 以組號字串陣列（依 groupCount 決定）
    const groupKeys = useMemo(
        () => Array.from({ length: groupCount }, (_, i) => String(i + 1)),
        [groupCount]
    );

    // 預先計算 tab index 用的偏移量（垂直導覽）
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

    /** 初始化 groups（建立 groupCount 個空白組） */
    const initEmptyGroups = (count: number, items: ItemConfig[]): Record<string, GroupMeas> =>
        Object.fromEntries(
            Array.from({ length: count }, (_, i) => [String(i + 1), emptyGroup(items)])
        );

    const resetForm = () => {
        setDate(new Date().toISOString().split('T')[0]);
        setInspectorName('');
        setVendorName('');
        setMaterial('');
        setSpec('');
        setOrderNo('');
        setGroupCount(DEFAULT_GROUP_COUNT);
        setGroups(initEmptyGroups(DEFAULT_GROUP_COUNT, BASE_ITEMS));
        setTolerance(null);
        setViolations({});
        setFieldErrors({});
    };

    // 載入編輯資料，或開新增時重置表單
    useEffect(() => {
        if (show) {
            if (editId && detailData) {
                // eslint-disable-next-line react-hooks/set-state-in-effect
                setDate(detailData.檢驗日期 ?? detailData.date ?? '');
                setInspectorName(String(detailData.檢驗人員 ?? '') || String(detailData.檢驗人員姓名 ?? '') || String(detailData.inspector_name ?? '') || '');
                setVendorName(String(detailData.廠商中文名稱 ?? detailData.vendor_name ?? ''));
                setMaterial(String(detailData.材質 ?? detailData.material ?? ''));
                setSpec(String(detailData.檢驗規格 ?? detailData.spec ?? ''));
                setOrderNo(detailData.訂單號碼 ?? detailData.order_num ?? '');

                // 讀取組數
                const savedGroupCount = detailData.組數 ?? detailData.group_count ?? DEFAULT_GROUP_COUNT;
                setGroupCount(savedGroupCount);

                // 載入量測資料（新格式 measurements 優先）
                if (detailData.measurements && Object.keys(detailData.measurements).length > 0) {
                    // 新格式：直接使用 measurements 巢狀資料
                    setGroups(detailData.measurements as Record<string, GroupMeas>);
                } else {
                    // 舊格式回退：從平鋪欄位轉換為新格式
                    const loadVendor = detailData.廠商中文名稱 ?? detailData.vendor_name;
                    const loadItems = loadVendor === ANTAI_VENDOR_NAME
                        ? (() => {
                            const items = [...BASE_ITEMS];
                            items.splice(2, 0, ROUNDNESS_ITEM);
                            const hIdx = items.findIndex(i => i.key === '硬度');
                            if (hIdx !== -1) {
                                items[hIdx] = { ...items[hIdx], label: '洛氏硬度(HRB)', toleranceKey: '洛氏硬度' };
                                items.splice(hIdx + 1, 0, VICKERS_HARDNESS_ITEM);
                            }
                            return items;
                        })()
                        : BASE_ITEMS;

                    const loaded: Record<string, GroupMeas> = {};
                    for (let g = 1; g <= savedGroupCount; g++) {
                        const gKey = String(g);
                        const groupData: GroupMeas = {};
                        loadItems.forEach(item => {
                            const entry: Partial<ShippingMeasurementItem> = { is_ng: false };
                            const raw = detailData as unknown as Record<string, unknown>;
                            if (item.type === 'minmax') {
                                const minRaw = raw[`${item.key}${g}-min`];
                                const maxRaw = raw[`${item.key}${g}-max`];
                                entry.value_min = minRaw != null ? Number(minRaw) : null;
                                entry.value_max = maxRaw != null ? Number(maxRaw) : null;
                            } else {
                                const valRaw = raw[`${item.key}${g}`];
                                entry.value_single = valRaw != null ? Number(valRaw) : null;
                            }
                            groupData[item.key] = entry;
                        });
                        loaded[gKey] = groupData;
                    }
                    setGroups(loaded);
                }
            } else if (!editId) {
                resetForm();
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [show, editId, detailData]);

    // 廠商變更時（僅新增模式），重置量測組
    useEffect(() => {
        if (!editId) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setGroupCount(DEFAULT_GROUP_COUNT);
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setGroups(initEmptyGroups(DEFAULT_GROUP_COUNT, ITEMS));
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [vendorName, editId]);

    // 公差查詢
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

    // 公差違規偵測（新格式：從 groups 讀取量測值）
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

            // 遍歷所有量測組
            groupKeys.forEach(gKey => {
                const measItem = groups[gKey]?.[item.key];
                if (!measItem) return;

                if (item.type === 'minmax') {
                    const vkMin = `${gKey}:${item.key}:value_min`;
                    const vkMax = `${gKey}:${item.key}:value_max`;
                    if (measItem.value_min != null && !isNaN(measItem.value_min)) {
                        if (measItem.value_min < lsl || measItem.value_min > usl) newViolations[vkMin] = true;
                    }
                    if (measItem.value_max != null && !isNaN(measItem.value_max)) {
                        if (measItem.value_max < lsl || measItem.value_max > usl) newViolations[vkMax] = true;
                    }
                } else {
                    const vk = `${gKey}:${item.key}:value_single`;
                    if (measItem.value_single != null && !isNaN(measItem.value_single)) {
                        if (measItem.value_single < lsl || measItem.value_single > usl) newViolations[vk] = true;
                    }
                }
            });
        });

        setViolations(newViolations);

    }, [groups, tolerance, spec, groupKeys, ITEMS]);

    // 呼吸動畫：每 750ms 切換 breathing-active class
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

    /** 更新特定組、特定項目的量測值 */
    const updateMeasValue = (gKey: string, itemKey: string, field: keyof ShippingMeasurementItem, value: string) => {
        setGroups(prev => ({
            ...prev,
            [gKey]: {
                ...prev[gKey],
                [itemKey]: {
                    ...prev[gKey]?.[itemKey],
                    [field]: value === '' ? null : Number(value),
                },
            },
        }));

        // 清除該欄位的格式錯誤
        const errKey = `${gKey}:${itemKey}:${field}`;
        setFieldErrors(prev => {
            if (!prev[errKey]) return prev;
            const next = { ...prev };
            delete next[errKey];
            return next;
        });
    };

    /** 新增量測組 */
    const addGroup = () => {
        const nextNum = String(Math.max(...Object.keys(groups).map(Number)) + 1);
        setGroups(prev => ({ ...prev, [nextNum]: emptyGroup(ITEMS) }));
        setGroupCount(prev => prev + 1);
    };

    /** 移除指定量測組 */
    const removeGroup = (gKey: string) => {
        if (Object.keys(groups).length <= 1) return;
        setGroups(prev => {
            const next = { ...prev };
            delete next[gKey];
            return next;
        });
        setGroupCount(prev => Math.max(1, prev - 1));
    };

    const handleSubmit = async () => {
        // 基本欄位驗證
        const validationErrors: string[] = [];
        if (!date) validationErrors.push('請選擇檢驗日期');
        if (!inspectorName) validationErrors.push('請選擇檢驗人員');
        if (!vendorName) validationErrors.push('請選擇廠商');
        if (!spec) validationErrors.push('請輸入檢驗規格');
        if (!material) validationErrors.push('請輸入材質');

        // 量測欄位數字格式驗證
        const newFieldErrors: Record<string, string> = {};
        const numPattern = /^[+-]?\d+(\.\d+)?$/;
        Object.entries(groups).forEach(([gKey, groupData]) => {
            ITEMS.forEach(item => {
                const measItem = groupData[item.key] ?? {};
                if (item.type === 'minmax') {
                    const minVal = measItem.value_min;
                    const maxVal = measItem.value_max;
                    if (minVal != null && !numPattern.test(String(minVal))) {
                        newFieldErrors[`${gKey}:${item.key}:value_min`] = `「${item.label}第${gKey}組最小值」需為有效數字`;
                    }
                    if (maxVal != null && !numPattern.test(String(maxVal))) {
                        newFieldErrors[`${gKey}:${item.key}:value_max`] = `「${item.label}第${gKey}組最大值」需為有效數字`;
                    }
                } else {
                    const val = measItem.value_single;
                    if (val != null && !numPattern.test(String(val))) {
                        newFieldErrors[`${gKey}:${item.key}:value_single`] = `「${item.label}第${gKey}組」需為有效數字`;
                    }
                }
            });
        });

        setFieldErrors(newFieldErrors);

        if (validationErrors.length > 0) {
            toast.error(validationErrors.join('、'));
            return;
        }

        if (Object.keys(newFieldErrors).length > 0) {
            toast.error(Object.values(newFieldErrors)[0]);
            return;
        }

        // 建立要送出的 measurements 物件（轉為後端期望的新格式）
        const measurementsPayload: ShippingMeasurements = {};
        Object.entries(groups).forEach(([gKey, groupData]) => {
            const groupOut: Record<string, ShippingMeasurementItem> = {};
            ITEMS.forEach(item => {
                const m = groupData[item.key] ?? {};
                groupOut[item.key] = {
                    lower_limit: m.lower_limit ?? null,
                    upper_limit: m.upper_limit ?? null,
                    value_min: item.type === 'minmax' ? (m.value_min ?? null) : null,
                    value_max: item.type === 'minmax' ? (m.value_max ?? null) : null,
                    value_single: item.type === 'single' ? (m.value_single ?? null) : null,
                    is_ng: m.is_ng ?? false,
                };
            });
            measurementsPayload[gKey] = groupOut;
        });

        const basePayload: ShippingCreateInput = {
            "檢驗日期": date,
            "檢驗人員姓名": inspectorName,
            "廠商中文名稱": vendorName,
            "檢驗規格": spec,
            "材質": material,
            "訂單號碼": orderNo,
            "組數": Object.keys(groups).length,
            "measurements": measurementsPayload,
        };

        try {
            if (editId) {
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
                if (!err?._toasted) {
                    toast.error(err?.message || '發生未知錯誤');
                }
            }
            console.error(error);
        }
    };

    const isSaving = createMutation.isPending || updateMutation.isPending;

    // 量測表格的組鍵陣列（依 groups 鍵排序，確保渲染順序穩定）
    const sortedGroupKeys = Object.keys(groups).sort((a, b) => Number(a) - Number(b));

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
                        {/* 基本資料 */}
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

                        {/* 公差資訊 */}
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

                        {/* 量測資料表格（橫軸為量測項目，縱軸為組別） */}
                        <div className="table-responsive">
                            <Table bordered className="text-center align-middle shipping-table">
                                <thead className="table-primary">
                                    <tr>
                                        <th className="text-nowrap">項目 \ 組別</th>
                                        {sortedGroupKeys.map(gKey => (
                                            <th key={gKey}>
                                                <div className="d-flex align-items-center justify-content-center gap-1">
                                                    <span>{gKey}</span>
                                                    {sortedGroupKeys.length > 1 && (
                                                        <button
                                                            type="button"
                                                            className="btn btn-outline-danger btn-sm p-0 lh-1"
                                                            style={{ width: '18px', height: '18px', fontSize: '10px' }}
                                                            onClick={() => removeGroup(gKey)}
                                                            title={`移除第 ${gKey} 組`}
                                                        >
                                                            ✕
                                                        </button>
                                                    )}
                                                </div>
                                            </th>
                                        ))}
                                        <th>
                                            <button
                                                type="button"
                                                className="btn btn-outline-primary btn-sm"
                                                onClick={addGroup}
                                                title="新增量測組"
                                            >
                                                ＋
                                            </button>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {ITEMS.map((item, idx) => (
                                        <tr key={item.key}>
                                            <th className="bg-light text-nowrap">{item.label}</th>
                                            {sortedGroupKeys.map((gKey, gIdx) => (
                                                <td key={gKey} className={item.type === 'minmax' ? 'shipping-cell-double' : 'shipping-cell-single'}>
                                                    {item.type === 'minmax' ? (
                                                        <div className="d-flex gap-2 justify-content-center flex-nowrap">
                                                            <Form.Control
                                                                size="sm"
                                                                placeholder="Min"
                                                                style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                                className={`text-center shipping-input ${fieldErrors[`${gKey}:${item.key}:value_min`] ? 'is-invalid-format' : ''} ${violations[`${gKey}:${item.key}:value_min`] ? 'is-invalid-breathing' : ''}`}
                                                                value={groups[gKey]?.[item.key]?.value_min ?? ''}
                                                                onChange={e => updateMeasValue(gKey, item.key, 'value_min', e.target.value)}
                                                                tabIndex={100 + gIdx * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx]}
                                                            />
                                                            <Form.Control
                                                                size="sm"
                                                                placeholder="Max"
                                                                style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                                className={`text-center shipping-input ${fieldErrors[`${gKey}:${item.key}:value_max`] ? 'is-invalid-format' : ''} ${violations[`${gKey}:${item.key}:value_max`] ? 'is-invalid-breathing' : ''}`}
                                                                value={groups[gKey]?.[item.key]?.value_max ?? ''}
                                                                onChange={e => updateMeasValue(gKey, item.key, 'value_max', e.target.value)}
                                                                tabIndex={100 + gIdx * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx] + 1}
                                                            />
                                                        </div>
                                                    ) : (
                                                        <Form.Control
                                                            size="sm"
                                                            style={{ fontSize: '0.75rem', padding: '2px 4px', width: '60px' }}
                                                            className={`text-center mx-auto shipping-input ${fieldErrors[`${gKey}:${item.key}:value_single`] ? 'is-invalid-format' : ''} ${violations[`${gKey}:${item.key}:value_single`] ? 'is-invalid-breathing' : ''}`}
                                                            value={groups[gKey]?.[item.key]?.value_single ?? ''}
                                                            onChange={e => updateMeasValue(gKey, item.key, 'value_single', e.target.value)}
                                                            tabIndex={100 + gIdx * TOTAL_INPUTS_PER_GROUP + ITEM_OFFSETS[idx]}
                                                        />
                                                    )}
                                                </td>
                                            ))}
                                            {/* 新增組按鈕欄位佔位 */}
                                            <td className="text-muted" style={{ fontSize: '0.7rem', color: '#ccc' }}>—</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </Table>
                        </div>
                        <div className="text-muted small mb-2">
                            共 {sortedGroupKeys.length} 組量測資料 · 點擊表頭「＋」新增組，「✕」移除組
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
