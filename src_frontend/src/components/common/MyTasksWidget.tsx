import { useState } from 'react';
import { Card, Badge, Button, Spinner, Table } from 'react-bootstrap';
import { useMyTasks, TASK_CATEGORY_LABELS, TASK_STATUS_LABELS, TASK_STATUS_VARIANT } from '../../hooks/useTask';
import TaskDetailModal from '../task/TaskDetailModal';
import type { ActionTask } from '../../types';

const MyTasksWidget = () => {
    const { data: tasks = [], isLoading } = useMyTasks();
    const [selected, setSelected] = useState<ActionTask | null>(null);

    const overdue    = tasks.filter(t => t.is_overdue);
    const notOverdue = tasks.filter(t => !t.is_overdue);
    const sorted     = [...overdue, ...notOverdue]; // 逾期排前面

    return (
        <>
            <Card className="h-100 shadow-sm">
                <Card.Header className="d-flex justify-content-between align-items-center py-2">
                    <span className="fw-semibold">
                        <i className="bi bi-list-check me-2 text-primary" />
                        我的待辦任務
                    </span>
                    <div className="d-flex gap-2 align-items-center">
                        {overdue.length > 0 && (
                            <Badge bg="danger">{overdue.length} 逾期</Badge>
                        )}
                        <Badge bg="primary">{tasks.length} 筆</Badge>
                    </div>
                </Card.Header>

                <Card.Body className="p-0" style={{ maxHeight: '320px', overflowY: 'auto' }}>
                    {isLoading ? (
                        <div className="text-center py-4">
                            <Spinner animation="border" size="sm" className="me-2" />
                            <span className="text-muted small">載入中…</span>
                        </div>
                    ) : sorted.length === 0 ? (
                        <div className="text-center py-4 text-muted small">
                            <i className="bi bi-check2-all fs-3 d-block mb-2 text-success" />
                            沒有待辦任務，繼續保持！
                        </div>
                    ) : (
                        <Table size="sm" hover className="mb-0">
                            <thead className="table-light sticky-top">
                                <tr>
                                    <th>類別</th>
                                    <th>來源</th>
                                    <th>期限</th>
                                    <th>狀態</th>
                                    <th style={{ width: '60px' }}></th>
                                </tr>
                            </thead>
                            <tbody>
                                {sorted.map(task => (
                                    <tr
                                        key={task.id}
                                        className={task.is_overdue ? 'table-danger' : ''}
                                    >
                                        <td className="small">
                                            {TASK_CATEGORY_LABELS[task.category] ?? task.category}
                                        </td>
                                        <td className="small text-muted">
                                            {task.source_type.toUpperCase()}-{task.source_id}
                                        </td>
                                        <td className="small">
                                            {task.due_date ? (
                                                <span className={task.is_overdue ? 'text-danger fw-semibold' : ''}>
                                                    {task.due_date}
                                                    {task.is_overdue && (
                                                        <span className="ms-1 badge bg-danger" style={{ fontSize: '0.65rem' }}>
                                                            +{task.overdue_days}天
                                                        </span>
                                                    )}
                                                </span>
                                            ) : '—'}
                                        </td>
                                        <td>
                                            <Badge bg={TASK_STATUS_VARIANT[task.status]} className="small">
                                                {TASK_STATUS_LABELS[task.status]}
                                            </Badge>
                                        </td>
                                        <td>
                                            <Button
                                                variant="link"
                                                size="sm"
                                                className="p-0"
                                                onClick={() => setSelected(task)}
                                            >
                                                詳情
                                            </Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    )}
                </Card.Body>

                <Card.Footer className="py-2 text-end">
                    <Button
                        variant="link"
                        size="sm"
                        href="/tasks"
                        className="p-0 text-muted"
                    >
                        查看全部任務 →
                    </Button>
                </Card.Footer>
            </Card>

            <TaskDetailModal
                task={selected}
                show={!!selected}
                onHide={() => setSelected(null)}
            />
        </>
    );
};

export default MyTasksWidget;
