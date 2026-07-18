import { useState } from 'react';
import { Alert, Badge, Button, Form, Modal, Table } from 'react-bootstrap';
import { useSetPatrolDetailExclusion, usePatrolDetails } from '../../hooks/usePatrol';

interface PatrolOutlierManagerModalProps {
    mainId: number | null;
    show: boolean;
    onHide: () => void;
}

/** 巡檢離群值管理（AIAG-VDA SPC 2026 §6.6）：標示無效、保留追溯、排除統計，不得刪除 */
const PatrolOutlierManagerModal = ({ mainId, show, onHide }: PatrolOutlierManagerModalProps) => {
    const { data: details = [], isLoading } = usePatrolDetails(show ? mainId : null);
    const setExclusion = useSetPatrolDetailExclusion();
    const [reasons, setReasons] = useState<Record<number, string>>({});

    const toggle = (id: number, currentlyExcluded: boolean) => {
        const reason = reasons[id] ?? '';
        if (!reason.trim()) return; // 排除與恢復都必填原因，確保稽核軌跡可解釋
        setExclusion.mutate({ id, excluded: !currentlyExcluded, reason }, {
            // 成功後清除本地暫存原因，避免下次排除時誤用舊原因造成追溯紀錄錯誤
            onSuccess: () => setReasons(prev => {
                const next = { ...prev };
                delete next[id];
                return next;
            }),
        });
    };

    return (
        <Modal show={show} onHide={onHide} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>離群值管理（巡檢記錄 #{mainId}）</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Alert variant="info" className="small py-2">
                    依 AIAG-VDA SPC 手冊 §6.6：離群值不得刪除，標示後保留於資料庫供追溯，
                    但排除於管制圖與能力指數計算之外。排除與恢復都必須填寫原因。
                </Alert>
                {isLoading ? <div className="text-center py-3">載入中…</div> : (
                    <Table size="sm" bordered hover>
                        <thead className="table-light text-center">
                            <tr><th>項目</th><th>組別</th><th>位置</th><th>量測值</th><th>狀態</th><th>原因</th><th></th></tr>
                        </thead>
                        <tbody>
                            {details.map(d => (
                                <tr key={d.識別碼} className={d.排除統計 ? 'table-secondary' : ''}>
                                    <td>{d.測量項目}</td>
                                    <td className="text-center">{d.組別}</td>
                                    <td className="text-center">{d.測量位置 || '—'}</td>
                                    <td className="text-center">
                                        {d.最小值 != null ? `${d.最小值} / ${d.最大值}` : '—'}
                                    </td>
                                    <td className="text-center">
                                        {d.排除統計
                                            ? <Badge bg="secondary">已排除</Badge>
                                            : <Badge bg="success">計入統計</Badge>}
                                    </td>
                                    <td>
                                        {d.排除統計 && (
                                            <div className="small mb-1">
                                                <strong>目前排除：</strong>{d.排除原因 || '—'}
                                                <div className="text-muted">
                                                    操作者 #{d.排除者ID ?? '—'} · {d.排除時間 ? new Date(d.排除時間).toLocaleString('zh-TW') : '時間未記錄'}
                                                </div>
                                            </div>
                                        )}
                                        <Form.Control size="sm" placeholder={d.排除統計 ? '恢復理由（必填）' : '離群原因（必填）'}
                                            value={reasons[d.識別碼] ?? ''}
                                            onChange={e => setReasons(prev => ({ ...prev, [d.識別碼]: e.target.value }))} />
                                    </td>
                                    <td className="text-center">
                                        <Button size="sm"
                                            variant={d.排除統計 ? 'outline-success' : 'outline-danger'}
                                            disabled={setExclusion.isPending || !(reasons[d.識別碼] ?? '').trim()}
                                            onClick={() => toggle(d.識別碼, d.排除統計)}>
                                            {d.排除統計 ? '恢復計入' : '標示離群'}
                                        </Button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                )}
            </Modal.Body>
        </Modal>
    );
};

export default PatrolOutlierManagerModal;
