import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col, Table } from 'react-bootstrap';
import { useToleranceDetail, useCreateTolerance, useUpdateTolerance } from '../../hooks/useTolerance';
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

interface ToleranceModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
    vendors: any[];
}

interface DetailRow {
    id: string;
    item: string;
    position: string;
    size_min: string;
    size_max: string;
    tol_min: string;
    tol_max: string;
    std: string;
    unit: string;
    remark: string;
}

// 拖曳排序表格列元件
interface SortableRowProps {
    id: string;
    detail: DetailRow;
    index: number;
    onChange: (index: number, field: keyof DetailRow, value: string) => void;
    onRemove: (index: number) => void;
    canDelete: boolean;
}

const SortableRow = ({ id, detail, index, onChange, onRemove, canDelete }: SortableRowProps) => {
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
            <td><Form.Control size="sm" type="number" step="0.0001" value={detail.size_min} onChange={e => onChange(index, 'size_min', e.target.value)} /></td>
            <td><Form.Control size="sm" type="number" step="0.0001" value={detail.size_max} onChange={e => onChange(index, 'size_max', e.target.value)} /></td>
            <td><Form.Control size="sm" type="number" step="0.0001" value={detail.tol_min} onChange={e => onChange(index, 'tol_min', e.target.value)} /></td>
            <td><Form.Control size="sm" type="number" step="0.0001" value={detail.tol_max} onChange={e => onChange(index, 'tol_max', e.target.value)} /></td>
            <td><Form.Control size="sm" type="number" step="0.0001" value={detail.std} onChange={e => onChange(index, 'std', e.target.value)} /></td>
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
    const [details, setDetails] = useState<DetailRow[]>([]);

    // 產生唯一 ID 用於拖曳排序
    const generateId = () => Math.random().toString(36).substring(2, 11);

    const createEmptyRow = (): DetailRow => ({
        id: generateId(),
        item: '', position: '', size_min: '', size_max: '', tol_min: '', tol_max: '', std: '', unit: 'mm', remark: ''
    });

    const resetForm = () => {
        setDate(new Date().toISOString().split('T')[0]);
        setMaterial('');
        setSpec('');
        setVendorId('');
        setRemark('');
        setDetails([createEmptyRow()]);
    };

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
        if (show) {
            if (editId) {
                // Wait for data to load
                if (detailData) {
                    const { main, details: dList } = detailData;
                    setDate(main.建立日期 ? main.建立日期.split('T')[0] : '');
                    setMaterial(main.材質 || '');
                    setSpec(main.規格 || '');
                    setVendorId(main.廠商ID?.toString() || '');
                    setRemark(main.備註 || '');

                    if (dList && dList.length > 0) {
                        setDetails(dList.map((d: any, idx: number) => ({
                            id: d.id || `existing-${idx}`,
                            item: d.測量項目 || '',
                            position: d.測量位置 || '',
                            size_min: d.尺寸下限 ?? '',
                            size_max: d.尺寸上限 ?? '',
                            tol_min: d.公差下限 ?? '',
                            tol_max: d.公差上限 ?? '',
                            std: d.標準值 ?? '',
                            unit: d.單位 || 'mm',
                            remark: d.備註 || ''
                        })));
                    } else {
                        setDetails([createEmptyRow()]);
                    }
                }
            } else {
                resetForm();
            }
        }
    }, [show, editId, detailData]);

    const handleDetailChange = (index: number, field: keyof DetailRow, value: string) => {
        const newDetails = [...details];
        newDetails[index][field] = value;
        setDetails(newDetails);
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
            // Toast will be better but keeping alert for client-side validation just in case, 
            // though toast is preferred. 
            // Since we have global error handling, using toast.error would be consistent if we import it,
            // but the plan says "global error handling" used in interceptors. 
            // For form validation, we can throw error or use alert. Alert is fine for now or validtion lib.
            alert('請輸入材質');
            return;
        }

        const payloadDetails = details
            .filter(d => d.item) // Filter out empty rows
            .map(d => ({
                測量項目: d.item,
                測量位置: d.position,
                尺寸下限: d.size_min === '' ? null : parseFloat(d.size_min),
                尺寸上限: d.size_max === '' ? null : parseFloat(d.size_max),
                公差下限: d.tol_min === '' ? null : parseFloat(d.tol_min),
                公差上限: d.tol_max === '' ? null : parseFloat(d.tol_max),
                標準值: d.std === '' ? null : parseFloat(d.std),
                單位: d.unit,
                備註: d.remark
            }));

        const payload = {
            建立日期: date,
            材質: material,
            規格: spec,
            廠商ID: vendorId ? parseInt(vendorId) : null,
            備註: remark,
            details: payloadDetails
        };

        if (editId) {
            updateMutation.mutate({ id: editId, data: payload }, {
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
            <Modal.Body style={{ maxHeight: '80vh', overflowY: 'auto', overflowX: 'auto' }}>
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
                            <Table bordered hover size="sm">
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
                                            />
                                        ))}
                                    </SortableContext>
                                </tbody>
                            </Table>
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
