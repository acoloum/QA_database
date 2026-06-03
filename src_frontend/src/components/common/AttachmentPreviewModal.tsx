import { useEffect, useState } from 'react';
import { Modal, Spinner, Button } from 'react-bootstrap';
import { getAttachmentDownloadUrl } from '../../hooks/useAttachment';
import type { Attachment } from '../../types';

interface AttachmentPreviewModalProps {
    attachment: Attachment | null;   // 為 null 時不顯示
    onClose: () => void;
}

// 抓取結果以附件 id 標記，供畫面判斷是否仍對應目前選取的附件
interface PreviewResult {
    id: number;
    url: string | null;
    error: string | null;
}

/**
 * 附件頁面內預覽 Modal。
 * 透過既有的下載 API（需帶 JWT）將檔案抓成 blob，再以 object URL 呈現，
 * 圖片用 <img>、PDF 用 <iframe>，不需後端額外支援 inline。
 */
const AttachmentPreviewModal = ({ attachment, onClose }: AttachmentPreviewModalProps) => {
    const [result, setResult] = useState<PreviewResult | null>(null);

    useEffect(() => {
        if (!attachment) return;

        let active = true;
        let createdUrl: string | null = null;
        const token = localStorage.getItem('authToken');

        fetch(getAttachmentDownloadUrl(attachment.id), {
            headers: { Authorization: `Bearer ${token ?? ''}` },
        })
            .then(r => {
                if (!r.ok) throw new Error(`載入失敗（${r.status}）`);
                return r.blob();
            })
            .then(blob => {
                // 以原始 MIME 類型重新包裝，確保瀏覽器正確判讀
                const typed = blob.type ? blob : new Blob([blob], { type: attachment.mime_type });
                createdUrl = URL.createObjectURL(typed);
                if (active) setResult({ id: attachment.id, url: createdUrl, error: null });
                else URL.revokeObjectURL(createdUrl);
            })
            .catch((e: Error) => {
                if (active) setResult({ id: attachment.id, url: null, error: e.message });
            });

        // 卸載或切換附件時釋放 object URL
        return () => {
            active = false;
            if (createdUrl) URL.revokeObjectURL(createdUrl);
        };
    }, [attachment]);

    // 由抓取結果是否對應目前附件，推導載入/錯誤/可顯示狀態（避免在 effect 內同步 setState）
    const ready   = !!attachment && result?.id === attachment.id;
    const loading = !!attachment && !ready;
    const blobUrl = ready ? result?.url ?? null : null;
    const error   = ready ? result?.error ?? null : null;
    const isImage = attachment?.mime_type.startsWith('image/');

    return (
        <Modal show={!!attachment} onHide={onClose} size="lg" centered>
            <Modal.Header closeButton>
                <Modal.Title className="fs-6 text-truncate">
                    <i className="bi bi-eye me-2" />
                    {attachment?.file_name}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body
                className="text-center p-0"
                style={{ minHeight: '60vh', maxHeight: '80vh', overflow: 'auto', backgroundColor: '#f8f9fa' }}
            >
                {loading && (
                    <div className="d-flex align-items-center justify-content-center" style={{ minHeight: '60vh' }}>
                        <Spinner animation="border" className="me-2" />
                        <span className="text-muted">載入預覽中…</span>
                    </div>
                )}

                {error && (
                    <div className="d-flex flex-column align-items-center justify-content-center text-danger" style={{ minHeight: '60vh' }}>
                        <i className="bi bi-exclamation-triangle fs-1 mb-2" />
                        <span>{error}</span>
                    </div>
                )}

                {blobUrl && !error && (
                    isImage ? (
                        <img
                            src={blobUrl}
                            alt={attachment?.file_name}
                            style={{ maxWidth: '100%', maxHeight: '80vh', objectFit: 'contain' }}
                        />
                    ) : (
                        <iframe
                            src={blobUrl}
                            title={attachment?.file_name}
                            style={{ width: '100%', height: '80vh', border: 'none' }}
                        />
                    )
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" size="sm" onClick={onClose}>關閉</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default AttachmentPreviewModal;
