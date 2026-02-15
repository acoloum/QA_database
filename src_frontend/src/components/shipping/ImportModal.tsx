import { useState, useRef } from 'react';
import { Modal, Button, Form, Alert } from 'react-bootstrap';
import api from '../../services/api';

interface ImportModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
}

const ImportModal = ({ show, handleClose, onSuccess }: ImportModalProps) => {
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
            setError(null);
        }
    };

    const handleUpload = async () => {
        if (!file) {
            setError('請選擇檔案');
            return;
        }

        setUploading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', file);

        try {
            await api.post('/import', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            alert('匯入成功');
            onSuccess();
            handleClose();
            setFile(null);
        } catch (err: any) {
            console.error('Import failed:', err);
            setError(err.response?.data?.error || '匯入失敗，請檢查檔案格式');
        } finally {
            setUploading(false);
        }
    };

    return (
        <Modal show={show} onHide={handleClose}>
            <Modal.Header closeButton>
                <Modal.Title>匯入 Excel 數據</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Alert variant="info">
                    請上傳符合格式的 Excel 檔案 (.xlsx, .xls)。
                </Alert>
                <Form.Group controlId="formFile" className="mb-3">
                    <Form.Label>選擇檔案</Form.Label>
                    <Form.Control
                        type="file"
                        accept=".xlsx, .xls"
                        onChange={handleFileChange}
                        ref={fileInputRef}
                    />
                </Form.Group>
                {error && <Alert variant="danger">{error}</Alert>}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose} disabled={uploading}>
                    取消
                </Button>
                <Button variant="success" onClick={handleUpload} disabled={!file || uploading}>
                    {uploading ? '匯入中...' : '開始匯入'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ImportModal;
