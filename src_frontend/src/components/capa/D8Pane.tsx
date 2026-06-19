import { Alert, Button, Form, Spinner } from 'react-bootstrap';

export interface CloseGateData {
    can_close: boolean;
    d6_passed: boolean;
    blocking_tasks: unknown[];
    missing_steps?: string[];
}

export interface D8PaneProps {
    confirmation: string;
    setConfirmation: (v: string) => void;
    recognition: string;
    setRecognition: (v: string) => void;
    closeGateData?: CloseGateData | null;
    closeGateLoading: boolean;
    isClosed: boolean;
    closeDate?: string | null;
    onClose: () => void;
    closing: boolean;
}

const D8Pane = ({
    confirmation,
    setConfirmation,
    recognition,
    setRecognition,
    closeGateData,
    closeGateLoading,
    isClosed,
    closeDate,
    onClose,
    closing,
}: D8PaneProps) => {
    const canClose = closeGateData?.can_close === true;
    const blockCount = closeGateData?.blocking_tasks?.length ?? 0;
    const missingSteps = closeGateData?.missing_steps ?? [];

    if (isClosed) {
        return (
            <Alert variant="success" className="mt-2">
                <i className="bi bi-check-circle-fill me-2" />
                此 CAPA 已於 {closeDate ?? '-'} 結案。
            </Alert>
        );
    }

    return (
        <div>
            {closeGateLoading ? (
                <div className="text-center py-3">
                    <Spinner size="sm" animation="border" /> 檢查結案條件...
                </div>
            ) : (
                <>
                    {!closeGateData?.d6_passed && (
                        <Alert variant="warning" className="py-2 small">
                            <i className="bi bi-exclamation-triangle-fill me-2" />
                            D6 尚未勾選「驗證通過」，無法結案。
                        </Alert>
                    )}
                    {missingSteps.length > 0 && (
                        <Alert variant="warning" className="py-2 small">
                            <i className="bi bi-exclamation-triangle-fill me-2" />
                            以下步驟尚未完成，無法結案：{missingSteps.join('、')}
                        </Alert>
                    )}
                    {blockCount > 0 && (
                        <Alert variant="danger" className="py-2 small">
                            <i className="bi bi-x-circle-fill me-2" />
                            尚有 {blockCount} 個 D7 任務未完成或豁免，無法結案。
                        </Alert>
                    )}
                    {canClose && (
                        <Alert variant="success" className="py-2 small">
                            <i className="bi bi-check-circle-fill me-2" />
                            所有結案條件已滿足，可以結案。
                        </Alert>
                    )}
                </>
            )}

            <Form.Group controlId="capa-d8-confirmation" className="mb-3">
                <Form.Label className="fw-semibold">結案確認聲明 <span className="text-danger">*</span></Form.Label>
                <Form.Control
                    as="textarea"
                    rows={4}
                    value={confirmation}
                    onChange={e => setConfirmation(e.target.value)}
                    placeholder="請確認所有改善措施均已實施且有效..."
                />
            </Form.Group>

            <Form.Group controlId="capa-d8-recognition" className="mb-3">
                <Form.Label className="fw-semibold">團隊表揚與心得</Form.Label>
                <Form.Control
                    as="textarea"
                    rows={3}
                    value={recognition}
                    onChange={e => setRecognition(e.target.value)}
                    placeholder="選填：紀錄團隊貢獻與心得..."
                />
            </Form.Group>

            <div className="d-flex justify-content-end">
                <Button
                    variant={canClose ? 'danger' : 'secondary'}
                    disabled={!canClose || !confirmation.trim() || closing}
                    onClick={onClose}
                >
                    {closing ? (
                        <>
                            <Spinner size="sm" animation="border" className="me-1" />結案中...
                        </>
                    ) : (
                        <>
                            <i className="bi bi-lock-fill me-1" />確認結案（不可逆）
                        </>
                    )}
                </Button>
            </div>
        </div>
    );
};

export default D8Pane;
