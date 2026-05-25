import { useRef, useState, useCallback } from 'react';
import { Button, ProgressBar, Badge } from 'react-bootstrap';
import { useUploadAttachment } from '../../hooks/useAttachment';

const ALLOWED_TYPES = [
    'image/jpeg', 'image/png', 'image/gif',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain', 'text/csv',
];
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

interface AttachmentUploaderProps {
    entityType: string;
    entityId: number;
    dStep?: string;
    disabled?: boolean;
}

const AttachmentUploader = ({
    entityType,
    entityId,
    dStep,
    disabled = false,
}: AttachmentUploaderProps) => {
    const inputRef  = useRef<HTMLInputElement>(null);
    const [dragging, setDragging]   = useState(false);
    const [progress, setProgress]   = useState<number | null>(null);
    const [fileError, setFileError] = useState<string | null>(null);

    const uploadMutation = useUploadAttachment();

    const validate = (file: File): string | null => {
        if (!ALLOWED_TYPES.includes(file.type)) {
            return `不支援的檔案類型：${file.name}（僅接受 JPG/PNG/PDF/Word/Excel/PPT/TXT/CSV）`;
        }
        if (file.size > MAX_SIZE) {
            return `檔案過大：${file.name}（上限 10 MB）`;
        }
        return null;
    };

    const handleUpload = useCallback(
        async (file: File) => {
            const err = validate(file);
            if (err) {
                setFileError(err);
                return;
            }
            setFileError(null);
            setProgress(0);

            // 模擬上傳進度（axios 實際進度需更多設定，此處簡化）
            const interval = setInterval(() => {
                setProgress(prev => (prev !== null && prev < 85 ? prev + 15 : prev));
            }, 200);

            try {
                await uploadMutation.mutateAsync({ file, entity_type: entityType, entity_id: entityId, d_step: dStep });
                setProgress(100);
            } finally {
                clearInterval(interval);
                setTimeout(() => setProgress(null), 800);
            }
        },
        [entityType, entityId, dStep, uploadMutation],
    );

    const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            void handleUpload(files[0]);
        }
        e.target.value = ''; // 允許重複上傳同名檔案
    };

    const onDrop = useCallback(
        (e: React.DragEvent<HTMLDivElement>) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files[0];
            if (file) void handleUpload(file);
        },
        [handleUpload],
    );

    return (
        <div
            className={`border rounded p-3 text-center ${dragging ? 'border-primary bg-light' : 'border-dashed'}`}
            style={{ cursor: disabled ? 'not-allowed' : 'pointer', borderStyle: 'dashed' }}
            onDragOver={e => { e.preventDefault(); if (!disabled) setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={disabled ? undefined : onDrop}
            onClick={() => !disabled && inputRef.current?.click()}
        >
            <input
                ref={inputRef}
                type="file"
                className="d-none"
                onChange={onFileChange}
                disabled={disabled}
            />
            <div className="mb-1">
                <i className="bi bi-cloud-upload fs-3 text-secondary" />
            </div>
            <div className="small text-muted">
                拖曳檔案至此，或{' '}
                <span className="text-primary text-decoration-underline">點此選擇</span>
            </div>
            <div className="mt-1">
                {(['JPG', 'PNG', 'PDF', 'Word', 'Excel', 'PPT', 'TXT', 'CSV'] as string[]).map(t => (
                    <Badge bg="light" text="secondary" className="me-1" key={t}>{t}</Badge>
                ))}
                <Badge bg="light" text="secondary">≤ 10 MB</Badge>
            </div>

            {progress !== null && (
                <ProgressBar
                    now={progress}
                    label={`${progress}%`}
                    className="mt-2"
                    style={{ height: '6px' }}
                />
            )}

            {fileError && (
                <div className="mt-2 text-danger small">{fileError}</div>
            )}

            {!disabled && (
                <Button
                    variant="outline-primary"
                    size="sm"
                    className="mt-2"
                    onClick={e => { e.stopPropagation(); inputRef.current?.click(); }}
                >
                    選擇檔案
                </Button>
            )}
        </div>
    );
};

export default AttachmentUploader;
