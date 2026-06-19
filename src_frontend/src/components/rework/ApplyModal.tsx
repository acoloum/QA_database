import { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap'; // We use react-bootstrap components
import api from '../../services/api';

interface ApplyModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    initialNcmrId?: string;
    initialNcmrNo?: string;
}

interface Inspector {
    name: string;
}

const ApplyModal = ({ show, handleClose, onSuccess, initialNcmrId, initialNcmrNo }: ApplyModalProps) => {
    const [inspectors, setInspectors] = useState<Inspector[]>([]);

    // Form States
    const [ncmrId, setNcmrId] = useState('');
    const [ncmrInfo, setNcmrInfo] = useState('');
    const [applicant, setApplicant] = useState('');
    const [department, setDepartment] = useState('');
    const [urgency, setUrgency] = useState('普通');
    const [productInfo, setProductInfo] = useState('');
    const [batchNo, setBatchNo] = useState('');
    const [quantity, setQuantity] = useState('');
    const [reason, setReason] = useState('');
    const [expectedDate, setExpectedDate] = useState('');

    const loadInspectors = async () => {
        try {
            const res = await api.get<Inspector[]>('/inspectors');
            setInspectors(res.data);
        } catch (error) {
            console.error('Failed to load inspectors', error);
        }
    };

    useEffect(() => {
        let cancelled = false;

        if (show) {
            queueMicrotask(() => {
                if (cancelled) return;
                loadInspectors();
                if (initialNcmrId) {
                    setNcmrId(initialNcmrId);
                    setNcmrInfo(`從 NCMR #${initialNcmrNo || initialNcmrId} 開立重工`);
                } else {
                    setNcmrId('');
                    setNcmrInfo('');
                }
            });
        }
        return () => {
            cancelled = true;
        };
    }, [show, initialNcmrId, initialNcmrNo]);

    const handleNcmrChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value;
        setNcmrId(val);
        // Basic simulation of NCMR lookup logic from rework.html
        if (val) {
            setNcmrInfo(`從 NCMR #${val} 自動帶入 (模擬)`);
        } else {
            setNcmrInfo('');
        }
    };

    const handleSubmit = async () => {
        try {
            const payload = {
                "NCMR_ID": parseInt(ncmrId),
                "申請人員姓名": applicant,
                "部門": department,
                "緊急程度": urgency,
                "產品資訊": productInfo,
                "批號": batchNo,
                "重工數量": parseFloat(quantity) || 0,
                "申請原因": reason,
                "預計完成日期": expectedDate
            };

            await api.post('/rework/apply', payload);
            alert('申請提交成功！');
            onSuccess();
            handleClose();
            // Reset form
            setNcmrId('');
            setApplicant('');
            setDepartment('');
            setUrgency('普通');
            setProductInfo('');
            setBatchNo('');
            setQuantity('');
            setReason('');
            setExpectedDate('');
        } catch (error: unknown) {
            const err = error as { response?: { data?: { error?: string } } };
            console.error(error);
            alert(err.response?.data?.error || '申請失敗');
        }
    };

    return (
        <Modal show={show} onHide={handleClose} backdrop="static">
            <Modal.Header closeButton>
                <Modal.Title>新增重工申請</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Form.Group className="mb-3">
                        <Form.Label>NCMR單號 (請輸入數字)</Form.Label>
                        <Form.Control
                            type="number"
                            value={ncmrId}
                            onChange={handleNcmrChange}
                            placeholder="例如: 123"
                        />
                        {ncmrInfo && <Form.Text className="text-success fw-bold">{ncmrInfo}</Form.Text>}
                    </Form.Group>

                    <div className="row">
                        <div className="col-md-6 mb-3">
                            <Form.Label>申請人員</Form.Label>
                            <Form.Select
                                value={applicant}
                                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setApplicant(e.target.value)}
                            >
                                <option value="">請選擇</option>
                                {inspectors.map((i, idx) => (
                                    <option key={idx} value={i.name}>{i.name}</option>
                                ))}
                            </Form.Select>
                        </div>
                        <div className="col-md-6 mb-3">
                            <Form.Label>部門</Form.Label>
                            <Form.Select
                                value={department}
                                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setDepartment(e.target.value)}
                            >
                                <option value="">請選擇</option>
                                <option value="製造部">製造部</option>
                                <option value="品保部">品保部</option>
                                <option value="工程部">工程部</option>
                                <option value="業務部">業務部</option>
                            </Form.Select>
                        </div>
                    </div>

                    <div className="row">
                        <div className="col-md-6 mb-3">
                            <Form.Label>緊急程度</Form.Label>
                            <Form.Select value={urgency} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setUrgency(e.target.value)}>
                                <option value="普通">普通</option>
                                <option value="重要">重要</option>
                                <option value="緊急">緊急</option>
                            </Form.Select>
                        </div>
                        <div className="col-md-6 mb-3">
                            <Form.Label>預計完成日期</Form.Label>
                            <Form.Control
                                type="date"
                                value={expectedDate}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setExpectedDate(e.target.value)}
                            />
                        </div>
                    </div>

                    <Form.Group className="mb-3">
                        <Form.Label>產品資訊</Form.Label>
                        <Form.Control
                            type="text"
                            value={productInfo}
                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProductInfo(e.target.value)}
                        />
                    </Form.Group>

                    <div className="row">
                        <div className="col-md-6 mb-3">
                            <Form.Label>批號</Form.Label>
                            <Form.Control
                                type="text"
                                value={batchNo}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setBatchNo(e.target.value)}
                            />
                        </div>
                        <div className="col-md-6 mb-3">
                            <Form.Label>重工數量</Form.Label>
                            <Form.Control
                                type="number"
                                value={quantity}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuantity(e.target.value)}
                            />
                        </div>
                    </div>

                    <Form.Group className="mb-3">
                        <Form.Label>申請原因</Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={3}
                            value={reason}
                            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setReason(e.target.value)}
                        />
                    </Form.Group>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>
                    取消
                </Button>
                <Button variant="primary" onClick={handleSubmit}>
                    提交申請
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ApplyModal;
