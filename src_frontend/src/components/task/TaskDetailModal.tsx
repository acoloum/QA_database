import { useState } from 'react';
import { Modal, Button, Form, Badge, Alert } from 'react-bootstrap';
import {
    useUpdateTaskStatus,
    TASK_CATEGORY_LABELS,
    TASK_STATUS_LABELS,
    TASK_STATUS_VARIANT,
} from '../../hooks/useTask';
import type { ActionTask, TaskStatus } from '../../types';
import PermissionAction from '../PermissionAction';

interface TaskDetailModalProps {
    task: ActionTask | null;
    show: boolean;
    onHide: () => void;
}

const STATUS_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
    pending:     ['in_progress', 'waived'],
    in_progress: ['completed', 'waived'],
    completed:   [],
    waived:      [],
};

const TaskDetailModal = ({ task, show, onHide }: TaskDetailModalProps) => {
    const updateStatus = useUpdateTaskStatus();

    const [nextStatus,       setNextStatus]       = useState<TaskStatus | ''>('');
    const [completionProof,  setCompletionProof]  = useState('');
    const [waiverReason,     setWaiverReason]     = useState('');

    if (!task) return null;

    const transitions = STATUS_TRANSITIONS[task.status] ?? [];

    const handleSubmit = async () => {
        if (!nextStatus) return;

        await updateStatus.mutateAsync({
            taskId:           task.id,
            status:           nextStatus as TaskStatus,
            completion_proof: nextStatus === 'completed' ? completionProof : undefined,
            waiver_reason:    nextStatus === 'waived'    ? waiverReason    : undefined,
        });
        onHide();
    };

    return (
        <Modal show={show} onHide={onHide} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>
                    任務明細
                    <Badge
                        bg={TASK_STATUS_VARIANT[task.status]}
                        className="ms-2"
                    >
                        {TASK_STATUS_LABELS[task.status]}
                    </Badge>
                </Modal.Title>
            </Modal.Header>

            <Modal.Body>
                {/* 基本資訊 */}
                <div className="row g-3 mb-4">
                    <div className="col-md-6">
                        <label className="form-label text-muted small">任務編號</label>
                        <div className="fw-semibold">{task.task_no}</div>
                    </div>
                    <div className="col-md-6">
                        <label className="form-label text-muted small">類別</label>
                        <div>{TASK_CATEGORY_LABELS[task.category] ?? task.category}</div>
                    </div>
                    <div className="col-md-6">
                        <label className="form-label text-muted small">負責人</label>
                        <div>{task.assignee_name ?? '—'}</div>
                    </div>
                    <div className="col-md-6">
                        <label className="form-label text-muted small">期限</label>
                        <div className={task.is_overdue ? 'text-danger fw-semibold' : ''}>
                            {task.due_date
                                ? `${task.due_date}${task.is_overdue ? ` （逾期 ${task.overdue_days} 天）` : ''}`
                                : '—'}
                        </div>
                    </div>
                    {task.description && (
                        <div className="col-12">
                            <label className="form-label text-muted small">說明</label>
                            <div>{task.description}</div>
                        </div>
                    )}
                    {task.completion_proof && (
                        <div className="col-12">
                            <label className="form-label text-muted small">完成憑證</label>
                            <div>{task.completion_proof}</div>
                        </div>
                    )}
                    {task.waiver_reason && (
                        <div className="col-12">
                            <label className="form-label text-muted small">豁免原因</label>
                            <div>{task.waiver_reason}</div>
                        </div>
                    )}
                </div>

                {/* 狀態切換 */}
                {transitions.length > 0 && (
                    <>
                        <hr />
                        <h6 className="mb-3">更新狀態</h6>
                        <Form.Group className="mb-3">
                            <Form.Label>切換至</Form.Label>
                            <Form.Select
                                value={nextStatus}
                                onChange={e => setNextStatus(e.target.value as TaskStatus | '')}
                            >
                                <option value="">— 請選擇 —</option>
                                {transitions.map(s => (
                                    <option key={s} value={s}>{TASK_STATUS_LABELS[s]}</option>
                                ))}
                            </Form.Select>
                        </Form.Group>

                        {nextStatus === 'completed' && (
                            <Form.Group className="mb-3">
                                <Form.Label>完成憑證 <span className="text-danger">*</span></Form.Label>
                                <Form.Control
                                    as="textarea"
                                    rows={2}
                                    placeholder="描述完成方式或附上憑證說明"
                                    value={completionProof}
                                    onChange={e => setCompletionProof(e.target.value)}
                                />
                            </Form.Group>
                        )}

                        {nextStatus === 'waived' && (
                            <Form.Group className="mb-3">
                                <Form.Label>豁免原因 <span className="text-danger">*</span></Form.Label>
                                <Form.Control
                                    as="textarea"
                                    rows={2}
                                    placeholder="說明豁免理由"
                                    value={waiverReason}
                                    onChange={e => setWaiverReason(e.target.value)}
                                />
                            </Form.Group>
                        )}

                        {updateStatus.isError && (
                            <Alert variant="danger" className="py-2">
                                {(updateStatus.error as Error)?.message ?? '更新失敗'}
                            </Alert>
                        )}
                    </>
                )}

                {transitions.length === 0 && (
                    <Alert variant="info" className="py-2 mb-0">
                        此任務已進入終態（{TASK_STATUS_LABELS[task.status]}），無法再切換狀態。
                    </Alert>
                )}
            </Modal.Body>

            <Modal.Footer>
                <Button variant="secondary" onClick={onHide}>關閉</Button>
                {nextStatus && (
                    <PermissionAction permission="task.edit"><Button
                        variant="primary"
                        onClick={handleSubmit}
                        disabled={
                            updateStatus.isPending ||
                            (nextStatus === 'completed' && !completionProof.trim()) ||
                            (nextStatus === 'waived'    && !waiverReason.trim())
                        }
                    >
                        {updateStatus.isPending ? '更新中…' : '確認更新'}
                    </Button></PermissionAction>
                )}
            </Modal.Footer>
        </Modal>
    );
};

export default TaskDetailModal;
