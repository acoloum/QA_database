import { useState } from 'react';
import { Alert, Badge, Button, Form, Modal, Table } from 'react-bootstrap';
import { useSetMeasurementExclusion, useShippingMeasurements } from '../../hooks/useShipping';

interface OutlierManagerModalProps {
    shippingId: number | null;
    show: boolean;
    onHide: () => void;
}

/** 離群值管理（AIAG-VDA 2026 §6.6）：標示無效、保留追溯、排除統計，不得刪除 */
const OutlierManagerModal = ({ shippingId, show, onHide }: OutlierManagerModalProps) => {
    const { data: measurements = [], isLoading } = useShippingMeasurements(show ? shippingId : null);
    const setExclusion = useSetMeasurementExclusion();
    const [reasons, setReasons] = useState<Record<number, string>>({});

    const toggle = (id: number, currentlyExcluded: boolean) => {
        const reason = reasons[id] ?? '';
        if (!currentlyExcluded && !reason.trim()) return; // 標示離群必填原因
        setExclusion.mutate({ id, excluded: !currentlyExcluded, reason });
    };

    return (
        <Modal show={show} onHide={onHide} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>離群值管理（記錄 #{shippingId}）</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Alert variant="info" className="small py-2">
                    依 AIAG-VDA SPC 手冊 §6.6：離群值不得刪除，標示後保留於資料庫供追溯，
                    但排除於管制圖與能力指數計算之外。標示時必須填寫原因。
                </Alert>
                {isLoading ? <div className="text-center py-3">載入中…</div> : (
                    <Table size="sm" bordered hover>
                        <thead className="table-light text-center">
                            <tr><th>項目</th><th>組別</th><th>位置</th><th>量測值</th><th>狀態</th><th>原因</th><th></th></tr>
                        </thead>
                        <tbody>
                            {measurements.map(m => (
                                <tr key={m.識別碼} className={m.排除統計 ? 'table-secondary' : ''}>
                                    <td>{m.量測項目}</td>
                                    <td className="text-center">{m.組別}</td>
                                    <td className="text-center">{m.測量位置 || '—'}</td>
                                    <td className="text-center">
                                        {m.量測值 ?? (m.量測最小值 != null ? `${m.量測最小值} / ${m.量測最大值}` : '—')}
                                    </td>
                                    <td className="text-center">
                                        {m.排除統計
                                            ? <Badge bg="secondary">已排除</Badge>
                                            : <Badge bg="success">計入統計</Badge>}
                                    </td>
                                    <td>
                                        {m.排除統計 ? (m.排除原因 || '') : (
                                            <Form.Control size="sm" placeholder="離群原因（必填）"
                                                value={reasons[m.識別碼] ?? ''}
                                                onChange={e => setReasons(prev => ({ ...prev, [m.識別碼]: e.target.value }))} />
                                        )}
                                    </td>
                                    <td className="text-center">
                                        <Button size="sm"
                                            variant={m.排除統計 ? 'outline-success' : 'outline-danger'}
                                            disabled={setExclusion.isPending || (!m.排除統計 && !(reasons[m.識別碼] ?? '').trim())}
                                            onClick={() => toggle(m.識別碼, m.排除統計)}>
                                            {m.排除統計 ? '恢復計入' : '標示離群'}
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

export default OutlierManagerModal;
