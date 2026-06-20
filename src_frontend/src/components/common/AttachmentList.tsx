import { useState } from 'react';
import { Table, Button, Badge, Spinner } from 'react-bootstrap';
import {
    useAttachments,
    useDeleteAttachment,
    getAttachmentDownloadUrl,
} from '../../hooks/useAttachment';
import ConfirmActionModal, { type ConfirmActionState } from './ConfirmActionModal';
import AttachmentPreviewModal from './AttachmentPreviewModal';
import type { Attachment } from '../../types';

/** 判斷該 MIME 類型是否可在頁面內預覽（圖片與 PDF） */
const isPreviewable = (mimeType: string): boolean =>
    mimeType.startsWith('image/') || mimeType === 'application/pdf';

const ICON_MAP: Record<string, string> = {
    'application/pdf':  'bi-file-pdf text-danger',
    'image/jpeg':       'bi-file-image text-info',
    'image/png':        'bi-file-image text-info',
    'image/gif':        'bi-file-image text-info',
    'text/plain':       'bi-file-text text-secondary',
    'text/csv':         'bi-file-spreadsheet text-success',
    'application/vnd.ms-excel':                                                            'bi-file-spreadsheet text-success',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':                   'bi-file-spreadsheet text-success',
    'application/msword':                                                                  'bi-file-word text-primary',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document':             'bi-file-word text-primary',
    'application/vnd.ms-powerpoint':                                                       'bi-file-ppt text-warning',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation':           'bi-file-ppt text-warning',
};

const formatSize = (bytes: number) => {
    if (bytes < 1024)        return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

interface AttachmentListProps {
    entityType: string;
    entityId: number;
    dStep?: string;
    canDelete?: boolean;
    currentUserId?: number;
}

const AttachmentList = ({
    entityType,
    entityId,
    dStep,
    canDelete = false,
}: AttachmentListProps) => {
    const { data: attachments = [], isLoading } = useAttachments(entityType, entityId, dStep);
    const deleteMutation = useDeleteAttachment(entityType, entityId);
    const [previewAtt, setPreviewAtt] = useState<Attachment | null>(null);
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    if (isLoading) {
        return (
            <div className="text-center py-2">
                <Spinner animation="border" size="sm" className="me-2" />
                <span className="small text-muted">載入附件中…</span>
            </div>
        );
    }

    if (attachments.length === 0) {
        return <p className="small text-muted mb-0">尚無附件</p>;
    }

    const handleDownload = (att: Attachment) => {
        const url = getAttachmentDownloadUrl(att.id);
        const a   = document.createElement('a');
        a.href     = url;
        a.download = att.file_name;
        // 帶入 JWT，讓 axios interceptor 處理（改用 fetch 方式）
        const token = localStorage.getItem('authToken');
        fetch(url, { headers: { Authorization: `Bearer ${token ?? ''}` } })
            .then(r => r.blob())
            .then(blob => {
                const blobUrl = URL.createObjectURL(blob);
                a.href = blobUrl;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(blobUrl);
            });
    };

    const handleDelete = (att: Attachment) => {
        setConfirmAction({
            title: '刪除附件',
            message: `確定要刪除「${att.file_name}」嗎？`,
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: () => deleteMutation.mutateAsync(att.id),
        });
    };

    return (
      <>
        <Table size="sm" hover className="mb-0">
            <thead className="table-light">
                <tr>
                    <th>檔案名稱</th>
                    <th>大小</th>
                    {dStep && <th>步驟</th>}
                    <th style={{ width: '100px' }}>操作</th>
                </tr>
            </thead>
            <tbody>
                {attachments.map(att => (
                    <tr key={att.id}>
                        <td>
                            <i className={`bi ${ICON_MAP[att.mime_type] ?? 'bi-file'} me-2`} />
                            {att.file_name}
                        </td>
                        <td className="text-muted small">{formatSize(att.file_size)}</td>
                        {dStep && (
                            <td>
                                <Badge bg="light" text="secondary">{att.d_step ?? '—'}</Badge>
                            </td>
                        )}
                        <td>
                            {isPreviewable(att.mime_type) && (
                                <Button
                                    variant="link"
                                    size="sm"
                                    className="p-0 me-2"
                                    title="預覽"
                                    onClick={() => setPreviewAtt(att)}
                                >
                                    <i className="bi bi-eye" />
                                </Button>
                            )}
                            <Button
                                variant="link"
                                size="sm"
                                className="p-0 me-2"
                                title="下載"
                                onClick={() => handleDownload(att)}
                            >
                                <i className="bi bi-download" />
                            </Button>
                            {canDelete && (
                                <Button
                                    variant="link"
                                    size="sm"
                                    className="p-0 text-danger"
                                    title="刪除"
                                    onClick={() => handleDelete(att)}
                                    disabled={deleteMutation.isPending}
                                >
                                    <i className="bi bi-trash" />
                                </Button>
                            )}
                        </td>
                    </tr>
                ))}
            </tbody>
        </Table>

        <AttachmentPreviewModal
            attachment={previewAtt}
            onClose={() => setPreviewAtt(null)}
        />
        <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
      </>
    );
};

export default AttachmentList;
