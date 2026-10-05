import { useState } from 'react';
import { Button, Form, Modal, Spinner } from 'react-bootstrap';

import { useAuth } from '../../context/useAuth';
import { useCapaList } from '../../hooks/useCapa';
import type { CustomerComplaint } from '../../types';

type CapaMode = 'create' | 'link';

interface ComplaintCapaModalProps {
    complaint: CustomerComplaint | null;
    onHide: () => void;
    onCreate: (complaintId: number) => Promise<unknown>;
    onLink: (complaintId: number, capaId: number) => Promise<unknown>;
}

const LINK_LABEL = '關聯既有 CAPA（共用同一份 8D）';

/** 進行中 CAPA 下拉選單；僅在選擇「關聯」時掛載，避免無謂查詢 */
const OpenCapaSelect = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => {
    const { data, isLoading } = useCapaList({ status: '進行中', per_page: 100 });
    const capas = data?.data ?? [];
    if (isLoading) return <Spinner animation="border" size="sm" />;
    if (capas.length === 0) return <div className="text-muted small">目前沒有進行中的 CAPA</div>;
    return (
        <Form.Select value={value} onChange={e => onChange(e.target.value)}>
            <option value="">請選擇 CAPA…</option>
            {capas.map(ca => {
                const desc = ca.ncmr_description ?? '';
                return (
                    <option key={ca.id} value={ca.id}>
                        {[ca.no, ca.vendor, desc.length > 30 ? `${desc.slice(0, 30)}…` : desc]
                            .filter(Boolean)
                            .join('｜')}
                    </option>
                );
            })}
        </Form.Select>
    );
};

const ComplaintCapaModal = ({ complaint, onHide, onCreate, onLink }: ComplaintCapaModalProps) => {
    const { hasPermission } = useAuth();
    const canLink = hasPermission('capa.edit');
    const [mode, setMode] = useState<CapaMode>('create');
    const [capaId, setCapaId] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const handleHide = () => {
        setMode('create');
        setCapaId('');
        onHide();
    };

    const handleConfirm = async () => {
        if (!complaint) return;
        setSubmitting(true);
        try {
            if (mode === 'create') {
                await onCreate(complaint.id);
            } else {
                await onLink(complaint.id, Number(capaId));
            }
            handleHide();
        } catch {
            // 錯誤訊息由 mutation 的 onError 以 toast 顯示，保留視窗讓使用者重試
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Modal show={!!complaint} onHide={handleHide} centered>
            <Modal.Header closeButton>
                <Modal.Title>客訴「{complaint?.complaint_no}」的 CAPA</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form.Check
                    type="radio"
                    id="complaint-capa-create"
                    name="complaint-capa-mode"
                    label="開立新 CAPA"
                    checked={mode === 'create'}
                    onChange={() => setMode('create')}
                />
                <Form.Check
                    type="radio"
                    id="complaint-capa-link"
                    name="complaint-capa-mode"
                    label={LINK_LABEL}
                    checked={mode === 'link'}
                    disabled={!canLink}
                    onChange={() => setMode('link')}
                />
                {!canLink && <div className="text-muted small ms-4">需要 capa.edit 權限</div>}
                {mode === 'link' && (
                    <div className="mt-2 ms-4">
                        <OpenCapaSelect value={capaId} onChange={setCapaId} />
                        <div className="text-muted small mt-1">
                            同一真因的多張客訴共用一份 8D；CAPA 結案時，所有關聯客訴一併結案。
                        </div>
                    </div>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleHide}>取消</Button>
                <Button
                    variant="primary"
                    onClick={handleConfirm}
                    disabled={submitting || (mode === 'link' && !capaId)}
                >
                    {mode === 'create' ? '開立' : '關聯'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ComplaintCapaModal;
