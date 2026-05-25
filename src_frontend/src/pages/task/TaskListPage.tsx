import { useState } from 'react';
import { Container, Row, Col, Card, Table, Badge, Button, Form } from 'react-bootstrap';
import {
    useTaskList,
    TASK_CATEGORY_LABELS,
    TASK_STATUS_LABELS,
    TASK_STATUS_VARIANT,
} from '../../hooks/useTask';
import TaskDetailModal from '../../components/task/TaskDetailModal';
import type { ActionTask, TaskStatus } from '../../types';

const PAGE_SIZE = 20;

const TaskListPage = () => {
    // 篩選條件
    const [statusFilter,    setStatusFilter]    = useState<TaskStatus | ''>('');
    const [categoryFilter,  setCategoryFilter]  = useState('');
    const [assigneeFilter,  setAssigneeFilter]  = useState('');
    const [dueFromFilter,   setDueFromFilter]   = useState('');
    const [dueToFilter,     setDueToFilter]     = useState('');
    const [page,            setPage]            = useState(1);

    const [selected, setSelected] = useState<ActionTask | null>(null);

    const params = {
        status:      statusFilter    || undefined,
        category:    categoryFilter  || undefined,
        due_from:    dueFromFilter   || undefined,
        due_to:      dueToFilter     || undefined,
        page,
        per_page:    PAGE_SIZE,
    };

    const { data, isLoading } = useTaskList(params);
    const tasks     = data?.data ?? [];
    const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE);

    const handleReset = () => {
        setStatusFilter('');
        setCategoryFilter('');
        setAssigneeFilter('');
        setDueFromFilter('');
        setDueToFilter('');
        setPage(1);
    };

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="bi bi-list-check me-2 text-primary" />
                    任務管理
                </h4>
            </div>

            {/* 篩選列 */}
            <Card className="mb-3 shadow-sm">
                <Card.Body className="py-2">
                    <Row className="g-2 align-items-end">
                        <Col xs={12} md={2}>
                            <Form.Label className="small mb-1">狀態</Form.Label>
                            <Form.Select
                                size="sm"
                                value={statusFilter}
                                onChange={e => { setStatusFilter(e.target.value as TaskStatus | ''); setPage(1); }}
                            >
                                <option value="">全部</option>
                                {(['pending', 'in_progress', 'completed', 'waived'] as TaskStatus[]).map(s => (
                                    <option key={s} value={s}>{TASK_STATUS_LABELS[s]}</option>
                                ))}
                            </Form.Select>
                        </Col>
                        <Col xs={12} md={2}>
                            <Form.Label className="small mb-1">類別</Form.Label>
                            <Form.Select
                                size="sm"
                                value={categoryFilter}
                                onChange={e => { setCategoryFilter(e.target.value); setPage(1); }}
                            >
                                <option value="">全部</option>
                                {Object.entries(TASK_CATEGORY_LABELS).map(([k, v]) => (
                                    <option key={k} value={k}>{v}</option>
                                ))}
                            </Form.Select>
                        </Col>
                        <Col xs={12} md={2}>
                            <Form.Label className="small mb-1">負責人</Form.Label>
                            <Form.Control
                                size="sm"
                                placeholder="輸入姓名…"
                                value={assigneeFilter}
                                onChange={e => setAssigneeFilter(e.target.value)}
                            />
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">期限（起）</Form.Label>
                            <Form.Control
                                type="date"
                                size="sm"
                                value={dueFromFilter}
                                onChange={e => { setDueFromFilter(e.target.value); setPage(1); }}
                            />
                        </Col>
                        <Col xs={6} md={2}>
                            <Form.Label className="small mb-1">期限（迄）</Form.Label>
                            <Form.Control
                                type="date"
                                size="sm"
                                value={dueToFilter}
                                onChange={e => { setDueToFilter(e.target.value); setPage(1); }}
                            />
                        </Col>
                        <Col xs={12} md={2}>
                            <Button variant="outline-secondary" size="sm" onClick={handleReset} className="w-100">
                                清除篩選
                            </Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            {/* 任務表格 */}
            <Card className="shadow-sm">
                <Card.Body className="p-0">
                    <div className="table-responsive">
                        <Table hover className="mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th>任務編號</th>
                                    <th>類別</th>
                                    <th>來源</th>
                                    <th>負責人</th>
                                    <th>期限</th>
                                    <th>狀態</th>
                                    <th style={{ width: '80px' }}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isLoading ? (
                                    <tr>
                                        <td colSpan={7} className="text-center py-4 text-muted">載入中…</td>
                                    </tr>
                                ) : tasks.length === 0 ? (
                                    <tr>
                                        <td colSpan={7} className="text-center py-4 text-muted">
                                            <i className="bi bi-inbox fs-3 d-block mb-2" />
                                            查無符合條件的任務
                                        </td>
                                    </tr>
                                ) : (
                                    tasks.map(task => (
                                        <tr key={task.id} className={task.is_overdue ? 'table-warning' : ''}>
                                            <td className="small fw-semibold">{task.task_no}</td>
                                            <td className="small">{TASK_CATEGORY_LABELS[task.category] ?? task.category}</td>
                                            <td className="small text-muted">
                                                {task.source_type.toUpperCase()}-{task.source_id}
                                            </td>
                                            <td className="small">{task.assignee_name ?? '—'}</td>
                                            <td className="small">
                                                {task.due_date ? (
                                                    <span className={task.is_overdue ? 'text-danger fw-semibold' : ''}>
                                                        {task.due_date}
                                                        {task.is_overdue && (
                                                            <Badge bg="danger" className="ms-1" style={{ fontSize: '0.65rem' }}>
                                                                逾期 {task.overdue_days} 天
                                                            </Badge>
                                                        )}
                                                    </span>
                                                ) : '—'}
                                            </td>
                                            <td>
                                                <Badge bg={TASK_STATUS_VARIANT[task.status]}>
                                                    {TASK_STATUS_LABELS[task.status]}
                                                </Badge>
                                            </td>
                                            <td>
                                                <Button
                                                    variant="outline-primary"
                                                    size="sm"
                                                    onClick={() => setSelected(task)}
                                                >
                                                    明細
                                                </Button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </Table>
                    </div>

                    {/* 分頁 */}
                    {totalPages > 1 && (
                        <div className="d-flex justify-content-between align-items-center px-3 py-2 border-top">
                            <span className="small text-muted">
                                共 {data?.total ?? 0} 筆，第 {page}/{totalPages} 頁
                            </span>
                            <div>
                                <Button
                                    variant="outline-secondary"
                                    size="sm"
                                    className="me-1"
                                    disabled={page <= 1}
                                    onClick={() => setPage(p => p - 1)}
                                >
                                    上一頁
                                </Button>
                                <Button
                                    variant="outline-secondary"
                                    size="sm"
                                    disabled={page >= totalPages}
                                    onClick={() => setPage(p => p + 1)}
                                >
                                    下一頁
                                </Button>
                            </div>
                        </div>
                    )}
                </Card.Body>
            </Card>

            <TaskDetailModal
                task={selected}
                show={!!selected}
                onHide={() => setSelected(null)}
            />
        </Container>
    );
};

export default TaskListPage;
