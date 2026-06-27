import { Button, Form, Table } from 'react-bootstrap';
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
    SortableContext,
    sortableKeyboardCoordinates,
    useSortable,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { CSSProperties } from 'react';
import type { ToleranceDetailRow } from './toleranceFormUtils';

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

interface ToleranceDetailTableProps {
    details: ToleranceDetailRow[];
    fieldErrors: Record<string, string>;
    onDragEnd: (event: DragEndEvent) => void;
    onChange: (index: number, field: keyof ToleranceDetailRow, value: string) => void;
    onRemove: (index: number) => void;
    onAddRow: () => void;
}

const ToleranceDetailTable = ({
    details,
    fieldErrors,
    onDragEnd,
    onChange,
    onRemove,
    onAddRow,
}: ToleranceDetailTableProps) => {
    const sensors = useSensors(
        useSensor(PointerSensor, {
            activationConstraint: {
                distance: 8,
            },
        }),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        }),
    );

    return (
        <>
            <div className="d-flex justify-content-between align-items-center mb-2">
                <h5 className="mb-0"><i className="bi bi-list"></i> 公差明細 <small className="text-muted fs-6">(可拖曳排序)</small></h5>
                <Button variant="outline-primary" size="sm" onClick={onAddRow}><i className="bi bi-plus"></i> 新增明細</Button>
            </div>

            <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={onDragEnd}
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
                                        onChange={onChange}
                                        onRemove={onRemove}
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
    );
};

export default ToleranceDetailTable;
