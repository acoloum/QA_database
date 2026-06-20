import { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';
import api from '../../services/api';
import { useInspectors } from '../../hooks/useInspectors';

interface ApproveModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    reworkId: number | null;
}

const ApproveModal = ({ show, handleClose, onSuccess, reworkId }: ApproveModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show });
    const [reviewerName, setReviewerName] = useState('');
    const [action, setAction] = useState('核准');
    const [opinion, setOpinion] = useState('');

    useEffect(() => {
        let cancelled = false;

        if (show) {
            queueMicrotask(() => {
                if (cancelled) return;
                setAction('核准');
                setOpinion('');
                setReviewerName('');
            });
        }
        return () => {
            cancelled = true;
        };
    }, [show]);

    const handleSubmit = async () => {
        if (!reworkId) return;
        if (!reviewerName) {
            alert('請選擇審核人員');
            return;
        }

        try {
            const payload = {
                "rework_id": reworkId,
                "action": action,
                "opinion": opinion,
                "審核人員姓名": reviewerName
            };

            await api.post('/rework/approve', payload);
            alert('審核完成！');
            onSuccess();
            handleClose();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } } };
            console.error(error);
            alert(err.response?.data?.error || '審核失敗');
        }
    };

    return (
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>審核重工申請 #{reworkId}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Form.Group className="mb-3">
                        <Form.Label>審核人員</Form.Label>
                        <Form.Select
                            value={reviewerName}
                            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setReviewerName(e.target.value)}
                        >
                            <option value="">請選擇</option>
                            {inspectors.map(i => (
                                <option key={i.id} value={i.name}>{i.name}</option>
                            ))}
                        </Form.Select>
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>審核動作</Form.Label>
                        <Form.Select
                            value={action}
                            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setAction(e.target.value)}
                        >
                            <option value="核准">核准</option>
                            <option value="拒絕">拒絕</option>
                        </Form.Select>
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>審核意見</Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={3}
                            value={opinion}
                            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setOpinion(e.target.value)}
                        />
                    </Form.Group>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>
                    取消
                </Button>
                <Button variant={action === '核准' ? 'success' : 'danger'} onClick={handleSubmit}>
                    確認{action}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ApproveModal;
