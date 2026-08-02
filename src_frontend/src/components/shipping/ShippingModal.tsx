import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Modal, Button, Form, Alert } from 'react-bootstrap';
import toast from 'react-hot-toast';
import type { ToleranceResult, ShippingMeasurementItem } from '../../types';
import { useInspectors } from '../../hooks/useInspectors';
import {
    useVendors,
    useShippingDetail,
    useCreateShipping,
    useUpdateShipping,
    useCheckTolerance
} from '../../hooks/useShipping';
import {
    calculateShippingViolations,
    type ShippingGroupMeasurements,
} from './shippingMeasurementUtils';
import { formatLocalDate } from '../../utils/dateUtils';
import {
    buildShippingPayload,
    emptyShippingGroup,
    getSortedShippingGroupKeys,
    initEmptyShippingGroups,
    validateShippingForm,
} from './shippingFormPayload';
import {
    BASE_SHIPPING_ITEMS,
    getShippingInspectionItems,
    getShippingItemInputOffsets,
} from './shippingInspectionItems';
import { ToleranceBadgeList } from '../common/toleranceDisplay';
import ConfirmActionModal, { type ConfirmActionState } from '../common/ConfirmActionModal';
import ShippingMeasurementTable from './ShippingMeasurementTable';
import {
    detectSegmentedKeys,
    expandSegmentedItems,
    hasMidRearSegmentValues,
    remapGroupsOnSegmentToggle,
} from './shippingSegmentUtils';

interface ShippingModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

const DEFAULT_GROUP_COUNT = 5;

/** 每組量測的資料結構 */
type GroupMeas = ShippingGroupMeasurements;

const ShippingModal = ({ show, handleClose, onSuccess, editId }: ShippingModalProps) => {
    // Hooks（品保組檢驗人員；走統一 useInspectors hook，避免與其他頁共用 cache key）
    const { data: inspectors = [] } = useInspectors({ group: '品保' });
    const { data: vendors = [] } = useVendors();
    const { data: detailData, isLoading: isLoadingDetail } = useShippingDetail(editId);

    const createMutation = useCreateShipping();
    const updateMutation = useUpdateShipping();
    const { mutateAsync: checkToleranceMutate } = useCheckTolerance();
    const toleranceRequestSeq = useRef(0);

    // 表單基本欄位
    const [date, setDate] = useState(formatLocalDate());
    const [inspectorName, setInspectorName] = useState('');
    const [vendorName, setVendorName] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [orderNo, setOrderNo] = useState('');

    // 新格式量測資料：Record<組號字串, Record<項目名稱, Partial<ShippingMeasurementItem>>>
    const [groups, setGroups] = useState<Record<string, GroupMeas>>({});

    // 已啟用分段量測的項目基鍵（如 '外徑'）
    const [segmentedKeys, setSegmentedKeys] = useState<Set<string>>(new Set());

    // 公差狀態
    const [tolerance, setTolerance] = useState<ToleranceResult | null>(null);
    const [violations, setViolations] = useState<Record<string, boolean>>({});

    // 欄位格式錯誤（key: 欄位名稱, value: 錯誤訊息）
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

    // 需二次確認的動作（如關閉分段量測會刪除中/後段數據）
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    // 依廠商決定量測項目清單（安泰：真圓度插入內徑後、新增韋伯氏硬度(HW)），
    // 主硬度的比對目標與標籤則依公差檔實際項目決定（洛氏硬度／未指明標度的硬度）。
    const toleranceItemNames = useMemo(
        () => tolerance?.found ? tolerance.tolerances.map(item => item.項目) : undefined,
        [tolerance],
    );
    // 已存檔即有量測值的項目：即使公差判定該欄不需顯示，也不得隱藏而讓既有值被孤立。
    // 必須取自載入的紀錄而非編輯中的 groups——ITEMS 變動會重建 groups，
    // 若反過來依賴 groups 會形成循環並清掉使用者剛輸入的值。
    const presentItemKeys = useMemo(() => {
        const keys = new Set<string>();
        const nested = (detailData?.measurements ?? {}) as Record<string, GroupMeas>;
        Object.values(nested).forEach(group => {
            Object.entries(group ?? {}).forEach(([key, value]) => {
                const hasValue = value != null && (
                    value.value_min != null || value.value_max != null || value.value_single != null
                );
                if (hasValue) keys.add(key);
            });
        });
        return keys;
    }, [detailData]);
    const ITEMS = useMemo(
        () => getShippingInspectionItems(vendorName, toleranceItemNames, presentItemKeys),
        [vendorName, toleranceItemNames, presentItemKeys],
    );

    // 依分段狀態展開後的實際渲染項目清單
    const ACTIVE_ITEMS = useMemo(() => expandSegmentedItems(ITEMS, segmentedKeys), [ITEMS, segmentedKeys]);

    // 預先計算 tab index 用的偏移量（垂直導覽）
    const { ITEM_OFFSETS, TOTAL_INPUTS_PER_GROUP } = useMemo(() => {
        const { itemOffsets, totalInputsPerGroup } = getShippingItemInputOffsets(ACTIVE_ITEMS);
        return { ITEM_OFFSETS: itemOffsets, TOTAL_INPUTS_PER_GROUP: totalInputsPerGroup };
    }, [ACTIVE_ITEMS]);

    const resetForm = useCallback(() => {
        setDate(formatLocalDate());
        setInspectorName('');
        setVendorName('');
        setMaterial('');
        setSpec('');
        setOrderNo('');
        setGroups(initEmptyShippingGroups(DEFAULT_GROUP_COUNT, BASE_SHIPPING_ITEMS));
        setSegmentedKeys(new Set());
        setTolerance(null);
        setViolations({});
        setFieldErrors({});
    }, []);

    // 載入編輯資料，或開新增時重置表單
    useEffect(() => {
        let cancelled = false;
        if (!show) {
            queueMicrotask(() => {
                if (!cancelled) resetForm();
            });
            return () => { cancelled = true; };
        }

        queueMicrotask(() => {
            if (cancelled) return;
            if (editId && detailData) {
                setDate(detailData.檢驗日期 ?? detailData.date ?? '');
                setInspectorName(String(detailData.檢驗人員 ?? '') || String(detailData.檢驗人員姓名 ?? '') || String(detailData.inspector_name ?? '') || '');
                setVendorName(String(detailData.廠商中文名稱 ?? detailData.vendor_name ?? ''));
                setMaterial(String(detailData.材質 ?? detailData.material ?? ''));
                setSpec(String(detailData.檢驗規格 ?? detailData.spec ?? ''));
                setOrderNo(detailData.訂單號碼 ?? detailData.order_num ?? '');

                // 讀取組數
                const savedGroupCount = detailData.組數 ?? detailData.group_count ?? DEFAULT_GROUP_COUNT;

                // 載入量測資料：一律使用 measurements 巢狀資料。
                // 先為 1..組數 建立空組以確保表格欄位顯示，再覆蓋實際量測值。
                const nested = (detailData.measurements ?? {}) as Record<string, GroupMeas>;
                const loaded: Record<string, GroupMeas> = {};
                for (let g = 1; g <= savedGroupCount; g++) {
                    loaded[String(g)] = {};
                }
                for (const [gKey, items] of Object.entries(nested)) {
                    loaded[gKey] = { ...(loaded[gKey] ?? {}), ...items };
                }
                setSegmentedKeys(detectSegmentedKeys(nested, BASE_SHIPPING_ITEMS));
                setGroups(loaded);
            }
        });
        return () => { cancelled = true; };
    }, [show, editId, detailData, resetForm]);

    // 廠商變更時（僅新增模式），重置量測組
    useEffect(() => {
        let cancelled = false;
        queueMicrotask(() => {
            if (cancelled || editId) return;
            setSegmentedKeys(new Set());
            setGroups(initEmptyShippingGroups(DEFAULT_GROUP_COUNT, ITEMS));
        });
        return () => { cancelled = true; };
    }, [vendorName, editId, ITEMS]);

    // 公差查詢
    useEffect(() => {
        const requestSeq = ++toleranceRequestSeq.current;
        const queryKey = `${vendorName}|${material}|${spec}`;

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

                if (requestSeq !== toleranceRequestSeq.current || queryKey !== `${vendorName}|${material}|${spec}`) {
                    return;
                }

                if (result.success && result.found) {
                    setTolerance(result);
                } else {
                    setTolerance(null);
                }
            } catch (e) {
                if (requestSeq !== toleranceRequestSeq.current) {
                    return;
                }
                console.error(e);
                setTolerance(null);
            }
        };

        const timeout = setTimeout(checkTolerance, 500);
        return () => clearTimeout(timeout);
    }, [material, spec, vendorName, vendors, checkToleranceMutate]);

    // 公差違規偵測（新格式：從 groups 讀取量測值）
    useEffect(() => {
        let cancelled = false;
        if (!tolerance) {
            queueMicrotask(() => {
                if (!cancelled) setViolations({});
            });
            return () => { cancelled = true; };
        }

        const newViolations = calculateShippingViolations({
            items: ACTIVE_ITEMS,
            groupKeys: getSortedShippingGroupKeys(groups),
            groups,
            tolerance,
            spec,
        });

        queueMicrotask(() => {
            if (!cancelled) setViolations(newViolations);
        });
        return () => { cancelled = true; };
    }, [groups, tolerance, spec, ACTIVE_ITEMS]);

    /** 更新特定組、特定項目的量測值 */
    const updateMeasValue = (gKey: string, itemKey: string, field: keyof ShippingMeasurementItem, value: string) => {
        setGroups(prev => ({
            ...prev,
            [gKey]: {
                ...prev[gKey],
                [itemKey]: {
                    ...prev[gKey]?.[itemKey],
                    [field]: value === '' ? null : value,
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
        setGroups(prev => ({ ...prev, [nextNum]: emptyShippingGroup(ACTIVE_ITEMS) }));
    };

    /** 移除指定量測組 */
    const removeGroup = (gKey: string) => {
        if (Object.keys(groups).length <= 1) return;
        setGroups(prev => {
            const next = { ...prev };
            delete next[gKey];
            return next;
        });
    };

    /** 實際套用分段切換：收合分段（只保留前段）或展開分段 */
    const applySegmentToggle = (baseKey: string, enabled: boolean) => {
        setGroups(prev => remapGroupsOnSegmentToggle(prev, baseKey, !enabled));
        setSegmentedKeys(prev => {
            const next = new Set(prev);
            if (enabled) next.delete(baseKey);
            else next.add(baseKey);
            return next;
        });
    };

    /** 切換項目的分段量測模式（開啟：單段值搬到前段；關閉：只保留前段） */
    const toggleSegment = (baseKey: string) => {
        const enabled = segmentedKeys.has(baseKey);
        // 關閉分段且中/後段仍有數據時，先跳出確認視窗避免誤刪；確認才收合
        if (enabled && hasMidRearSegmentValues(groups, baseKey)) {
            setConfirmAction({
                title: '關閉分段量測',
                message: '關閉分段後將只保留前段數據，確定要關閉嗎？',
                confirmLabel: '關閉',
                confirmVariant: 'danger',
                onConfirm: () => applySegmentToggle(baseKey, enabled),
            });
            return;
        }
        applySegmentToggle(baseKey, enabled);
    };

    const handleSubmit = async () => {
        const { validationErrors, fieldErrors: newFieldErrors } = validateShippingForm({
            date,
            inspectorName,
            vendorName,
            material,
            spec,
            items: ACTIVE_ITEMS,
            groups,
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

        const basePayload = buildShippingPayload({
            date,
            inspectorName,
            vendorName,
            material,
            spec,
            orderNo,
            items: ACTIVE_ITEMS,
            groups,
        });

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
    const sortedGroupKeys = getSortedShippingGroupKeys(groups);

    return (
        <>
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
                                    <ToleranceBadgeList tolerances={tolerance.tolerances} />
                                </div>
                            </Alert>
                        )}

                        <ShippingMeasurementTable
                            items={ACTIVE_ITEMS}
                            groupKeys={sortedGroupKeys}
                            groups={groups}
                            itemOffsets={ITEM_OFFSETS}
                            totalInputsPerGroup={TOTAL_INPUTS_PER_GROUP}
                            fieldErrors={fieldErrors}
                            violations={violations}
                            onMeasurementChange={updateMeasValue}
                            onAddGroup={addGroup}
                            onRemoveGroup={removeGroup}
                            onToggleSegment={toggleSegment}
                        />
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
        <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </>
    );
};

export default ShippingModal;
