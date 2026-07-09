import { Form, Table } from 'react-bootstrap';
import type { ShippingMeasurementItem } from '../../types';
import type { ShippingGroupMeasurements, ShippingItemConfig } from './shippingMeasurementUtils';

interface ShippingMeasurementTableProps {
    items: ShippingItemConfig[];
    groupKeys: string[];
    groups: Record<string, ShippingGroupMeasurements>;
    itemOffsets: number[];
    totalInputsPerGroup: number;
    fieldErrors: Record<string, string>;
    violations: Record<string, boolean>;
    onMeasurementChange: (
        groupKey: string,
        itemKey: string,
        field: keyof ShippingMeasurementItem,
        value: string,
    ) => void;
    onAddGroup: () => void;
    onRemoveGroup: (groupKey: string) => void;
    onToggleSegment: (baseKey: string) => void;
}

const inputStyle = { fontSize: '0.75rem', padding: '2px 4px', width: '60px' };

const ShippingMeasurementTable = ({
    items,
    groupKeys,
    groups,
    itemOffsets,
    totalInputsPerGroup,
    fieldErrors,
    violations,
    onMeasurementChange,
    onAddGroup,
    onRemoveGroup,
    onToggleSegment,
}: ShippingMeasurementTableProps) => (
    <>
        <div className="table-responsive">
            <Table bordered className="text-center align-middle shipping-table">
                <thead className="table-primary">
                    <tr>
                        <th className="text-nowrap">項目 \ 組別</th>
                        {groupKeys.map(groupKey => (
                            <th key={groupKey}>
                                <div className="d-flex align-items-center justify-content-center gap-1">
                                    <span>{groupKey}</span>
                                    {groupKeys.length > 1 && (
                                        <button
                                            type="button"
                                            className="btn btn-outline-danger btn-sm p-0 lh-1"
                                            style={{ width: '18px', height: '18px', fontSize: '10px' }}
                                            onClick={() => onRemoveGroup(groupKey)}
                                            title={`移除第 ${groupKey} 組`}
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
                                onClick={onAddGroup}
                                title="新增量測組"
                            >
                                ＋
                            </button>
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {items.map((item, itemIndex) => (
                        <tr key={item.key}>
                            <th className="bg-light text-nowrap">
                                <div className="d-flex align-items-center justify-content-between gap-1">
                                    <span>{item.label}</span>
                                    {item.segmentable && (!item.position || item.position === '前段') && (
                                        <div className="form-check form-switch mb-0">
                                            <Form.Check.Input
                                                type="checkbox"
                                                id={`segment-switch-${item.baseKey ?? item.key}`}
                                                title="分段量測(前/中/後)"
                                                checked={Boolean(item.position)}
                                                onChange={() => onToggleSegment(item.baseKey ?? item.key)}
                                            />
                                        </div>
                                    )}
                                </div>
                            </th>
                            {groupKeys.map((groupKey, groupIndex) => (
                                <td key={groupKey} className={item.type === 'minmax' ? 'shipping-cell-double' : 'shipping-cell-single'}>
                                    {item.type === 'minmax' ? (
                                        <div className="d-flex gap-2 justify-content-center flex-nowrap">
                                            <Form.Control
                                                size="sm"
                                                placeholder="Min"
                                                style={inputStyle}
                                                className={`text-center shipping-input ${fieldErrors[`${groupKey}:${item.key}:value_min`] ? 'is-invalid-format' : ''} ${violations[`${groupKey}:${item.key}:value_min`] ? 'is-invalid-breathing' : ''}`}
                                                value={groups[groupKey]?.[item.key]?.value_min ?? ''}
                                                onChange={e => onMeasurementChange(groupKey, item.key, 'value_min', e.target.value)}
                                                tabIndex={100 + groupIndex * totalInputsPerGroup + itemOffsets[itemIndex]}
                                            />
                                            <Form.Control
                                                size="sm"
                                                placeholder="Max"
                                                style={inputStyle}
                                                className={`text-center shipping-input ${fieldErrors[`${groupKey}:${item.key}:value_max`] ? 'is-invalid-format' : ''} ${violations[`${groupKey}:${item.key}:value_max`] ? 'is-invalid-breathing' : ''}`}
                                                value={groups[groupKey]?.[item.key]?.value_max ?? ''}
                                                onChange={e => onMeasurementChange(groupKey, item.key, 'value_max', e.target.value)}
                                                tabIndex={100 + groupIndex * totalInputsPerGroup + itemOffsets[itemIndex] + 1}
                                            />
                                        </div>
                                    ) : (
                                        <Form.Control
                                            size="sm"
                                            style={inputStyle}
                                            className={`text-center mx-auto shipping-input ${fieldErrors[`${groupKey}:${item.key}:value_single`] ? 'is-invalid-format' : ''} ${violations[`${groupKey}:${item.key}:value_single`] ? 'is-invalid-breathing' : ''}`}
                                            value={groups[groupKey]?.[item.key]?.value_single ?? ''}
                                            onChange={e => onMeasurementChange(groupKey, item.key, 'value_single', e.target.value)}
                                            tabIndex={100 + groupIndex * totalInputsPerGroup + itemOffsets[itemIndex]}
                                        />
                                    )}
                                </td>
                            ))}
                            <td className="text-muted" style={{ fontSize: '0.7rem', color: '#ccc' }}>—</td>
                        </tr>
                    ))}
                </tbody>
            </Table>
        </div>
        <div className="text-muted small mb-2">
            共 {groupKeys.length} 組量測資料 · 點擊表頭「＋」新增組，「✕」移除組
        </div>
    </>
);

export default ShippingMeasurementTable;
