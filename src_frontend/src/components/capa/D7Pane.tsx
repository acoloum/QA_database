import { Alert, Badge, Button, Form, Spinner, Table } from 'react-bootstrap';

import type { ActionTask, D7Action } from '../../types';
import { D7_TYPES } from './capaD7Types';
import { groupInspectors, inspectorLabel, type InspectorItem } from './capaInspectors';

const TASK_STATUS_BADGE: Record<string, string> = {
    pending: 'secondary',
    in_progress: 'primary',
    completed: 'success',
    waived: 'warning',
};

const TASK_STATUS_LABEL: Record<string, string> = {
    pending: '待處理',
    in_progress: '進行中',
    completed: '已完成',
    waived: '豁免',
};

export interface D7PaneProps {
    actions: D7Action[];
    tasks: ActionTask[];
    inspectors: InspectorItem[];
    readonly?: boolean;
    onToggle: (idx: number, checked: boolean) => void;
    onUpdateField: (idx: number, field: keyof D7Action, val: unknown) => void;
    onSave: () => void;
    saving: boolean;
}

const SaveBar = ({ onSave, saving, readonly }: { onSave: () => void; saving: boolean; readonly?: boolean }) => {
    if (readonly) return null;
    return (
        <div className="d-flex justify-content-end mt-3">
            <Button variant="primary" size="sm" onClick={onSave} disabled={saving}>
                {saving ? <Spinner size="sm" animation="border" className="me-1" /> : <i className="bi bi-save me-1" />}
                儲存此步驟
            </Button>
        </div>
    );
};

const D7Pane = ({
    actions,
    tasks,
    inspectors,
    readonly,
    onToggle,
    onUpdateField,
    onSave,
    saving,
}: D7PaneProps) => (
    <div>
        <Alert variant="info" className="py-2 small">
            <i className="bi bi-info-circle me-1" />
            勾選需要橫展的項目，儲存後系統將自動產生對應任務（ActionTask）。
        </Alert>

        <Table size="sm" bordered>
            <thead className="table-light">
                <tr>
                    <th style={{ width: '30px' }}></th>
                    <th>橫展類型</th>
                    <th>指派人</th>
                    <th>期限</th>
                    <th>說明</th>
                    <th>任務狀態</th>
                </tr>
            </thead>
            <tbody>
                {actions.map((action, idx) => {
                    const typeLabel = D7_TYPES.find(type => type.key === action.type)?.label ?? action.type;
                    const relTask = tasks.find(task => task.category === action.type);

                    return (
                        <tr key={action.type} className={action.checked ? '' : 'text-muted'}>
                            <td className="text-center">
                                <Form.Check
                                    type="checkbox"
                                    aria-label={typeLabel}
                                    checked={action.checked}
                                    onChange={e => onToggle(idx, e.target.checked)}
                                    disabled={readonly}
                                />
                            </td>
                            <td className="small fw-semibold">{typeLabel}</td>
                            <td>
                                {action.checked && (
                                    <Form.Select
                                        size="sm"
                                        value={action.assignee_id ?? ''}
                                        onChange={e => onUpdateField(idx, 'assignee_id', e.target.value ? Number(e.target.value) : null)}
                                        disabled={readonly}
                                    >
                                        <option value="">請選擇</option>
                                        {Object.entries(groupInspectors(inspectors)).map(([group, items]) => (
                                            <optgroup key={group} label={group}>
                                                {items.map(inspector => (
                                                    <option key={inspector.id} value={inspector.id}>
                                                        {inspectorLabel(inspector)}
                                                    </option>
                                                ))}
                                            </optgroup>
                                        ))}
                                    </Form.Select>
                                )}
                            </td>
                            <td>
                                {action.checked && (
                                    <Form.Control
                                        type="date"
                                        size="sm"
                                        value={action.due_date ?? ''}
                                        onChange={e => onUpdateField(idx, 'due_date', e.target.value || null)}
                                        disabled={readonly}
                                    />
                                )}
                            </td>
                            <td>
                                {action.checked && (
                                    <Form.Control
                                        size="sm"
                                        value={action.description ?? ''}
                                        onChange={e => onUpdateField(idx, 'description', e.target.value)}
                                        disabled={readonly}
                                        placeholder="備註..."
                                    />
                                )}
                            </td>
                            <td>
                                {relTask ? (
                                    <Badge bg={TASK_STATUS_BADGE[relTask.status] ?? 'secondary'}>
                                        {TASK_STATUS_LABEL[relTask.status] ?? relTask.status}
                                    </Badge>
                                ) : action.checked ? (
                                    <span className="small text-muted">儲存後建立</span>
                                ) : null}
                            </td>
                        </tr>
                    );
                })}
            </tbody>
        </Table>

        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

export default D7Pane;
