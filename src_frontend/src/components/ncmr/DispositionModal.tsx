
import { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';
import type { NCMR } from '../../types';
import { useUpdateNCMR, useCreateCAPA } from '../../hooks/useNCMR';

interface DispositionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    item: NCMR | null;
}

const DispositionModal = ({ show, handleClose, onSuccess, item }: DispositionModalProps) => {
    const updateMutation = useUpdateNCMR();
    const createCAPAMutation = useCreateCAPA();

    const [result, setResult] = useState('');
    const [status, setStatus] = useState('');

    useEffect(() => {
        if (show && item) {
            setResult(item.result || '特採');
            setStatus(item.status || '待處理');
        }
    }, [show, item]);

    const handleSave = async () => {
        if (!item) return;
        try {
            await updateMutation.mutateAsync({
                "識別碼": item.id,
                "判定結果": result,
                "狀態": status
            });
            onSuccess();
            handleClose();
        } catch (error: any) {
            // Global error handler handles toast
            console.error(error);
        }
    };

    const convertToRework = () => {
        if (!item) return;
        if (window.confirm('確定要針對此異常單開立重工申請嗎？')) {
            window.open(`/rework?ncmr_id=${item.id}&ncmr_no=${item.no || item.id}`, '_blank');
        }
    };

    const createCAPA = async () => {
        if (!item) return;
        if (!window.confirm('確定要針對此異常單開立 8D 矯正措施嗎？')) return;

        try {
            const res = await createCAPAMutation.mutateAsync(item.id);
            // res is { success: true, id: ... } (from backend/routes/ncmr.py)
            // Backend returns: jsonify({"success": True, **result})
            // result is dictionary from Service.

            if (res.success || res.id) { // Defensive check
                const capaId = res.id;
                alert('已成功建立 CAPA 單，即將前往矯正措施頁面。');
                handleClose();
                window.location.href = `/capa?editId=${capaId}`;
            } else {
                // Should be caught by catch block if status code is error, 
                // but if 200 OK with success: false (unlikely for this backend), we handle it.
                alert('建立失敗');
            }
        } catch (error: any) {
            console.error(error);
        }
    };

    const isSaving = updateMutation.isPending || createCAPAMutation.isPending;

    return (
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>異常處置 (單號: {item?.no || item?.id})</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <div className="mb-3">
                        <Form.Label>判定結果</Form.Label>
                        <Form.Select value={result} onChange={e => setResult(e.target.value)}>
                            <option value="特採">特採 (允收但需紀錄)</option>
                            <option value="重工">重工 (修正後重驗)</option>
                            <option value="報廢">報廢 (無法使用)</option>
                            <option value="退貨">退貨 (退回廠商)</option>
                            <option value="選別及補數">選別及補數</option>
                        </Form.Select>
                    </div>
                    <div className="mb-3">
                        <Form.Label>狀態更新</Form.Label>
                        <Form.Select value={status} onChange={e => setStatus(e.target.value)}>
                            <option value="待處理">待處理</option>
                            <option value="已結案">已結案</option>
                        </Form.Select>
                    </div>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <div className="d-flex w-100 justify-content-between">
                    <div>
                        <Button variant="warning" size="sm" className="me-1" onClick={createCAPA} disabled={isSaving}>轉開 CAPA</Button>
                        <Button variant="info" size="sm" onClick={convertToRework} disabled={isSaving}>轉重工</Button>
                    </div>
                    <Button variant="primary" onClick={handleSave} disabled={isSaving}>
                        {updateMutation.isPending ? '更新中...' : '更新處置'}
                    </Button>
                </div>
            </Modal.Footer>
        </Modal>
    );
};

export default DispositionModal;
