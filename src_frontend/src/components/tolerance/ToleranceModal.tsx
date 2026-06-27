import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import toast from 'react-hot-toast';
import { useToleranceDetail, useCreateTolerance, useUpdateTolerance } from '../../hooks/useTolerance';
import type { Vendor } from '../../types';
import type { DragEndEvent } from '@dnd-kit/core';
import { arrayMove } from '@dnd-kit/sortable';
import {
    buildTolerancePayload,
    createToleranceDetailRow,
    mapToleranceDetailToRow,
    validateToleranceRows,
    type ToleranceDetailRow,
} from './toleranceFormUtils';
import ToleranceDetailTable from './ToleranceDetailTable';
import { formatLocalDate } from '../../utils/dateUtils';

interface ToleranceModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
    vendors: Vendor[];
}

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

                        <ToleranceDetailTable
                            details={details}
                            fieldErrors={fieldErrors}
                            onDragEnd={handleDragEnd}
                            onChange={handleDetailChange}
                            onRemove={removeRow}
                            onAddRow={addRow}
                        />
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
