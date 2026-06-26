import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Row, Col, Table } from 'react-bootstrap';
import toast from 'react-hot-toast';
import { useToleranceDetail, useCreateTolerance, useUpdateTolerance } from '../../hooks/useTolerance';
import type { Vendor } from '../../types';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { CSSProperties } from 'react';
import {
    buildTolerancePayload,
    createToleranceDetailRow,
    mapToleranceDetailToRow,
    validateToleranceRows,
    type ToleranceDetailRow,
} from './toleranceFormUtils';
import { formatLocalDate } from '../../utils/dateUtils';

interface ToleranceModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
    vendors: Vendor[];
}

// 拖曳排序表格列元件
interface SortableRowProps {
    id: string;
    detail: ToleranceDetailRow;
    index: number;
    onChange: (index: number, field: keyof ToleranceDetailRow, value: string) => void;
    onRemove: (index: number) => void;
    canDelete: boolean;
    fieldErrors: Record<string, string>;
}

const SortableRow = ({ id, detail, index, onChange, onRemove, canDelete, fieldErrors }: SortableRowProps) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id });

    const style: CSSProperties = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        backgroundColor: isDragging ? '#f8f9fa' : 'transparent',
    };

    return (
        <tr ref={setNodeRef} style={style}>
            <td className="text-center" style={{ cursor: 'grab', width: '40px' }} {...attributes} {...listeners}>
                <i className="bi bi-grip-vertical text-muted"></i>
            </td>
            <td><Form.Control size="sm" value={detail.item} onChange={e => onChange(index, 'item', e.target.value)} placeholder="項目" /></td>
            <td><Form.Control size="sm" value={detail.position} onChange={e => onChange(index, 'position', e.target.value)} placeholder="Pos" /></td>
            <td><Form.Control size="sm" type="text" inputMode="decimal" value={detail.size_min} isInvalid={!!fieldErrors[`${id}:size_min`]} onChange={e => onChange(index, 'size_min', e.target.value)} /></td>
            <td><Form.Control size="sm" type="text" inputMode="decimal" value={detail.size_max} isInvalid={!!fieldErrors[`${id}:size_max`]} onChange={e => onChange(index, 'size_max', e.target.value)} /></td>
            <td><Form.Control size="sm" type="text" inputMode="decimal" value={detail.tol_min} isInvalid={!!fieldErrors[`${id}:tol_min`]} onChange={e => onChange(index, 'tol_min', e.target.value)} /></td>
            <td><Form.Control size="sm" type="text" inputMode="decimal" value={detail.tol_max} isInvalid={!!fieldErrors[`${id}:tol_max`]} onChange={e => onChange(index, 'tol_max', e.target.value)} /></td>
            <td><Form.Control size="sm" type="text" inputMode="decimal" value={detail.std} isInvalid={!!fieldErrors[`${id}:std`]} onChange={e => onChange(index, 'std', e.target.value)} /></td>
            <td><Form.Control size="sm" value={detail.unit} onChange={e => onChange(index, 'unit', e.target.value)} /></td>
            <td><Form.Control size="sm" value={detail.remark} onChange={e => onChange(index, 'remark', e.target.value)} /></td>
            <td className="text-center">
                <Button variant="outline-danger" size="sm" onClick={() => onRemove(index)} tabIndex={-1} disabled={!canDelete}><i className="bi bi-trash"></i></Button>
            </td>
        </tr>
    );
};

const ToleranceModal = ({ show, handleClose, onSuccess, editId, vendors }: ToleranceModalProps) => {
    const [date, setDate] = useState('');
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [vendorId, setVendorId] = useState('');
    const [remark, setRemark] = useState('');
    const [details, setDetails] = useState<ToleranceDetailRow[]>([]);
    const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

    // 產生唯一 ID 用於拖曳排序
    const generateId = () => Math.random().toString(36).substring(2, 11);

    const createEmptyRow = useCallback((): ToleranceDetailRow => createToleranceDetailRow(generateId()), []);

    const resetForm = useCallback(() => {
        setDate(formatLocalDate());
        setMaterial('');
        setSpec('');
        setVendorId('');
        setRemark('');
        setDetails([createEmptyRow()]);
        setFieldErrors({});
    }, [createEmptyRow]);

    // 設定拖曳感測器
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8, // 必須拖曳 8px 才會觸發
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    // 處理拖曳結束
    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;

        if (over && active.id !== over.id) {
            setDetails((items) => {
                const oldIndex = items.findIndex((item) => item.id === active.id);
                const newIndex = items.findIndex((item) => item.id === over.id);
                return arrayMove(items, oldIndex, newIndex);
            });
        }
    };

    // Hooks
    const { data: detailData, isLoading: detailLoading } = useToleranceDetail(show && editId ? editId : null);
    const createMutation = useCreateTolerance();
    const updateMutation = useUpdateTolerance();

    useEffect(() => {
        let cancelled = false;

        if (show) {
            if (editId) {
                // Wait for data to load
                if (detailData) {
                    const { main, details: dList } = detailData;
                    queueMicrotask(() => {
                        if (cancelled) return;
                        setDate(main.建立日期 ? main.建立日期.split('T')[0] : '');
                        setMaterial(main.材質 || '');
                        setSpec(main.規格 || '');
                        setVendorId(main.廠商ID?.toString() || '');
                        setRemark(main.備註 || '');
                        setFieldErrors({});

                        if (dList && dList.length > 0) {
                            setDetails(dList.map((d, idx: number) => mapToleranceDetailToRow(d, String(idx))));
                        } else {
                            setDetails([createEmptyRow()]);
                        }
                    });
                }
            } else {
                queueMicrotask(() => {
                    if (!cancelled) resetForm();
                });
            }
        }
        return () => {
            cancelled = true;
        };
    }, [show, editId, detailData, createEmptyRow, resetForm]);

    const handleDetailChange = (index: number, field: keyof ToleranceDetailRow, value: string) => {
        const newDetails = [...details];
        newDetails[index][field] = value;
        setDetails(newDetails);
        setFieldErrors(prev => {
            const errorKey = `${newDetails[index].id}:${field}`;
            if (!prev[errorKey]) return prev;
            const next = { ...prev };
            delete next[errorKey];
            return next;
        });
    };

    const addRow = () => {
        setDetails([...details, createEmptyRow()]);
    };

    const removeRow = (index: number) => {
        if (details.length > 1) {
            setDetails(details.filter((_, i) => i !== index));
        }
    };

    const handleSave = async () => {
        if (!material) {
            toast.error('請輸入材質');
            return;
        }

        const nextFieldErrors = validateToleranceRows(details);
        setFieldErrors(nextFieldErrors);
        if (Object.keys(nextFieldErrors).length > 0) {
            toast.error(Object.values(nextFieldErrors)[0]);
            return;
        }

        const payload = buildTolerancePayload({ date, material, spec, vendorId, remark, details });

        if (editId) {
            // ToleranceUpdateInput 需要 識別碼 欄位，這裡加入以符合型別要求
            updateMutation.mutate({ id: editId, data: { ...payload, 識別碼: editId } }, {
                onSuccess: () => {
                    onSuccess();
                    handleClose();
                }
            });
        } else {
            createMutation.mutate(payload, {
                onSuccess: () => {
                    onSuccess();
                    handleClose();
                }
            });
        }
    };

    return (
        <Modal show={show} onHide={handleClose} size="xl" backdrop="static" dialogClassName="modal-90w">
            <Modal.Header closeButton>
                <Modal.Title>{editId ? '編輯公差資料' : '新增公差資料'}</Modal.Title>
            </Modal.Header>
            <Modal.Body style={{ maxHeight: '80vh', overflowY: 'auto' }}>
                <style type="text/css">
                    {`
                        .modal-90w {
                            max-width: 90% !important;
                        }
                        .sticky-header th {
                            position: sticky;
                            top: 0;
                            z-index: 2;
                            background-color: var(--bs-light);
                            box-shadow: inset 0 -1px 0 var(--bs-border-color, #dee2e6);
                        }
                    `}
                </style>
                {detailLoading && editId ? <div className="text-center">載入中...</div> : (
                    <>
                        <div className="bg-light p-3 rounded mb-3">
                            <Row className="g-3">
                                <Col md={3}><Form.Label>日期</Form.Label><Form.Control type="date" value={date} onChange={e => setDate(e.target.value)} /></Col>
                                <Col md={3}><Form.Label>材質 <span className="text-danger">*</span></Form.Label><Form.Control value={material} onChange={e => setMaterial(e.target.value)} required /></Col>
                                <Col md={3}><Form.Label>規格</Form.Label><Form.Control value={spec} onChange={e => setSpec(e.target.value)} /></Col>
                                <Col md={3}>
                                    <Form.Label>廠商</Form.Label>
                                    <Form.Select value={vendorId} onChange={e => setVendorId(e.target.value)}>
                                        <option value="">-- 請選擇 --</option>
                                        {vendors.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}
                                    </Form.Select>
                                </Col>
                                <Col md={12}><Form.Label>備註</Form.Label><Form.Control value={remark} onChange={e => setRemark(e.target.value)} /></Col>
                            </Row>
                        </div>

                        <div className="d-flex justify-content-between align-items-center mb-2">
                            <h5 className="mb-0"><i className="bi bi-list"></i> 公差明細 <small className="text-muted fs-6">(可拖曳排序)</small></h5>
                            <Button variant="outline-primary" size="sm" onClick={addRow}><i className="bi bi-plus"></i> 新增明細</Button>
                        </div>

                        <DndContext
                            sensors={sensors}
                            collisionDetection={closestCenter}
                            onDragEnd={handleDragEnd}
                        >
                        {/* overflowX + overflowY 合一，讓 sticky header 相對此容器定位 */}
                        <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 'calc(80vh - 230px)' }}>
                            <Table bordered hover size="sm" style={{ minWidth: '760px' }}>
                                <thead className="table-light text-center sticky-header">
                                    <tr>
                                        <th style={{ width: '40px' }}></th>
                                        <th style={{ width: '15%' }}>測量項目</th>
                                        <th style={{ width: '8%' }}>位置</th>
                                        <th>尺寸下限</th>
                                        <th>尺寸上限</th>
                                        <th>公差下限</th>
                                        <th>公差上限</th>
                                        <th>標準值</th>
                                        <th style={{ width: '8%' }}>單位</th>
                                        <th>備註</th>
                                        <th style={{ width: '5%' }}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <SortableContext items={details.map(d => d.id)} strategy={verticalListSortingStrategy}>
                                        {details.map((d, index) => (
                                            <SortableRow
                                                key={d.id}
                                                id={d.id}
                                                detail={d}
                                                index={index}
                                                onChange={handleDetailChange}
                                                onRemove={removeRow}
                                                canDelete={details.length > 1}
                                                fieldErrors={fieldErrors}
                                            />
                                        ))}
                                    </SortableContext>
                                </tbody>
                            </Table>
                        </div>
                        </DndContext>
                    </>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSave} disabled={createMutation.isPending || updateMutation.isPending}>
                    {createMutation.isPending || updateMutation.isPending ? '儲存中...' : '儲存'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ToleranceModal;
