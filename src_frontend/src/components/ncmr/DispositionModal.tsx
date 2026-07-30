import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Modal, Button, Form, Table, Alert } from 'react-bootstrap';
import type { NCMR, NcmrDisposition, DispositionType } from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../common/ConfirmActionModal';
import {
    useDispositions, useCreateDisposition, useDeleteDisposition,
    useUpdateNCMR, useCreateCAPA, useNcmrReworks,
} from '../../hooks/useNCMR';
import {
    parseDispositionNumberInput,
    parseNullableDispositionNumberInput,
} from './dispositionFormUtils';
import { buildReworkFromNcmrUrl } from '../../pages/ncmr/ncmrPageUtils';

interface DispositionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    item: NCMR | null;
}

const DISPOSITION_TYPES: DispositionType[] = ['矯正重工', '報廢', '挑選全檢', '讓步放行'];

type DispositionFormState = Omit<NcmrDisposition, '處置數量'> & {
    處置數量: number | null;
};

const emptyForm = (): DispositionFormState => ({
    處置類型: '報廢',
    處置數量: 0,
    是否超出客戶規格: false,
});

const DispositionModal = ({ show, handleClose, onSuccess, item }: DispositionModalProps) => {
    const ncmrId = item?.id ?? null;
    const { data: dispositions = [] } = useDispositions(show ? ncmrId : null);
    const { data: reworks = [] } = useNcmrReworks(show ? ncmrId : null);
    const createDisp = useCreateDisposition();
    const deleteDisp = useDeleteDisposition();
    const updateNCMR = useUpdateNCMR();
    const createCAPA = useCreateCAPA();
    const navigate = useNavigate();

    const [form, setForm] = useState<DispositionFormState>(emptyForm());
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    // 計算不良總數、已處置數、未處置數
    const defectTotal = Number(item?.defect_qty ?? 0);
    const disposed = dispositions.reduce((s, d) => s + Number(d.處置數量 || 0), 0);
    const remaining = defectTotal - disposed;
    const canClose = defectTotal > 0 && remaining === 0 && dispositions.length > 0;

    const setField = (k: keyof DispositionFormState, v: unknown) =>
        setForm(prev => ({ ...prev, [k]: v }));

    // 新增處置明細
    const handleAdd = async () => {
        if (!ncmrId) return;
        try {
            await createDisp.mutateAsync({
                ncmrId,
                data: {
                    ...form,
                    處置數量: form.處置數量 ?? 0,
                },
            });
            setForm(emptyForm());
        } catch (e) {
            console.error(e);
        }
    };

    // 刪除處置明細
    const handleDelete = async (id?: number) => {
        if (!id) return;
        setConfirmAction({
            title: '刪除處置',
            message: '確定刪除此處置？',
            confirmLabel: '刪除',
            confirmVariant: 'danger',
            onConfirm: async () => {
              await deleteDisp.mutateAsync(id);
            },
        });
    };

    // 結案：呼叫後端結案 gate，失敗由全域 axios 錯誤攔截器顯示 toast
    const handleCloseNcmr = async () => {
        if (!item) return;
        try {
            await updateNCMR.mutateAsync({ 識別碼: item.id, 狀態: '已結案' });
            onSuccess();
            handleClose();
        } catch (e) {
            console.error(e);
        }
    };

    // 轉重工
    const convertToRework = () => {
        if (!item) return;
        setConfirmAction({
            title: '開立重工申請',
            message: '確定要針對此異常單開立重工申請嗎？',
            confirmLabel: '開立',
            confirmVariant: 'primary',
            onConfirm: () => {
              window.open(buildReworkFromNcmrUrl(item.id, item.no), '_blank');
            },
        });
    };

    // 轉開 CAPA（8D）
    const handleCreateCAPA = async () => {
        if (!item) return;
        setConfirmAction({
            title: '開立 8D 矯正措施',
            message: '確定要針對此異常單開立 8D 矯正措施嗎？',
            confirmLabel: '開立',
            confirmVariant: 'primary',
            onConfirm: async () => {
                const res = await createCAPA.mutateAsync(item.id);
                const capaId = res.id;
                handleClose();
                navigate(`/capa?editId=${capaId}`);
            },
        });
    };

    const t = form.處置類型;
    const concessionNeedsAuth = t === '讓步放行' && !!form.是否超出客戶規格 && !form.授權狀態;
    const reworkNeedsLink = t === '矯正重工' && !form.關聯重工單ID;
    const canAdd = Number(form.處置數量) > 0 && !concessionNeedsAuth && !reworkNeedsLink;

    return (
        <>
        <Modal key={item?.id} show={show} onHide={handleClose} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>異常處置 (單號: {item?.no || item?.id})</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {/* 數量摘要列 */}
                <Alert variant={remaining < 0 ? 'danger' : remaining === 0 ? 'success' : 'warning'}>
                    不良總數 {defectTotal}{' | '}已處置 {disposed}{' | '}未處置 {remaining}
                </Alert>

                {/* 處置明細列表 */}
                <Table size="sm" bordered>
                    <thead>
                        <tr><th>類型</th><th>數量</th><th>風險</th><th></th></tr>
                    </thead>
                    <tbody>
                        {dispositions.map(d => (
                            <tr key={d.識別碼}>
                                <td>{d.處置類型}</td>
                                <td>{d.處置數量}</td>
                                <td>{d.是否風險項 ? <span className="text-danger">⚠ 未授權放行</span> : ''}</td>
                                <td>
                                    <Button variant="outline-danger" size="sm"
                                        onClick={() => handleDelete(d.識別碼)}>刪除</Button>
                                </td>
                            </tr>
                        ))}
                        {dispositions.length === 0 && (
                            <tr><td colSpan={4} className="text-muted text-center">尚無處置</td></tr>
                        )}
                    </tbody>
                </Table>

                <hr />
                <h6>新增處置</h6>
                <Form>
                    <div className="row g-2">
                        <div className="col-md-6">
                            <Form.Label>處置類型</Form.Label>
                            <Form.Select value={t}
                                onChange={e => setField('處置類型', e.target.value as DispositionType)}>
                                {DISPOSITION_TYPES.map(x => <option key={x} value={x}>{x}</option>)}
                            </Form.Select>
                        </div>
                        <div className="col-md-6">
                            <Form.Label>處置數量</Form.Label>
                            <Form.Control type="number" value={form.處置數量 ?? ''}
                                onChange={e => setField('處置數量', parseDispositionNumberInput(e.target.value))} />
                        </div>
                    </div>

                    {/* 矯正重工：選擇關聯重工單 */}
                    {t === '矯正重工' && (
                        <div className="mt-2">
                            <Form.Label>關聯重工單（須已結案才能讓 NCMR 結案）</Form.Label>
                            <Form.Select value={form.關聯重工單ID ?? ''}
                                onChange={e => setField('關聯重工單ID', e.target.value ? Number(e.target.value) : null)}>
                                <option value="">請選擇重工單</option>
                                {reworks.map(rw => (
                                    <option key={rw.識別碼} value={rw.識別碼}>
                                        {rw.申請單號}（{rw.狀態}）
                                    </option>
                                ))}
                            </Form.Select>
                            {reworks.length === 0 && (
                                <small className="text-muted">尚無重工單，請先按「轉重工」開立</small>
                            )}
                        </div>
                    )}

                    {/* 挑選全檢：顯示合格數 / 不合格數欄位 */}
                    {t === '挑選全檢' && (
                        <div className="row g-2 mt-1">
                            <div className="col-md-6">
                                <Form.Label>合格數</Form.Label>
                                <Form.Control type="number" value={form.合格數 ?? ''}
                                    onChange={e => setField('合格數', parseNullableDispositionNumberInput(e.target.value))} />
                            </div>
                            <div className="col-md-6">
                                <Form.Label>不合格數</Form.Label>
                                <Form.Control type="number" value={form.不合格數 ?? ''}
                                    onChange={e => setField('不合格數', parseNullableDispositionNumberInput(e.target.value))} />
                            </div>
                        </div>
                    )}

                    {/* 讓步放行：超出客戶規格 / 授權資訊 */}
                    {t === '讓步放行' && (
                        <div className="mt-2">
                            <Form.Check type="checkbox" label="超出客戶規格"
                                checked={!!form.是否超出客戶規格}
                                onChange={e => setField('是否超出客戶規格', e.target.checked)} />
                            {form.是否超出客戶規格 && (
                                <>
                                    <Form.Label className="mt-2">授權狀態</Form.Label>
                                    <Form.Select value={form.授權狀態 ?? ''}
                                        onChange={e => setField('授權狀態', e.target.value)}>
                                        <option value="">請選擇</option>
                                        <option value="已取得">已取得客戶授權</option>
                                        <option value="未取得">未取得授權</option>
                                    </Form.Select>
                                    {/* 已取得授權：授權文號 / 有效期 / 數量上限 */}
                                    {form.授權狀態 === '已取得' && (
                                        <div className="row g-2 mt-1">
                                            <div className="col-md-4">
                                                <Form.Label>授權文號</Form.Label>
                                                <Form.Control value={form.授權文號 ?? ''}
                                                    onChange={e => setField('授權文號', e.target.value)} />
                                            </div>
                                            <div className="col-md-4">
                                                <Form.Label>有效期</Form.Label>
                                                <Form.Control type="date" value={form.授權有效期 ?? ''}
                                                    onChange={e => setField('授權有效期', e.target.value)} />
                                            </div>
                                            <div className="col-md-4">
                                                <Form.Label>數量上限</Form.Label>
                                                <Form.Control type="number" value={form.授權數量上限 ?? ''}
                                                    onChange={e => setField('授權數量上限', parseNullableDispositionNumberInput(e.target.value))} />
                                            </div>
                                        </div>
                                    )}
                                    {/* 未取得授權：標記為風險項並記錄理由 */}
                                    {form.授權狀態 === '未取得' && (
                                        <div className="mt-1">
                                            <Form.Label className="text-danger">未授權放行理由（將標記為風險項）</Form.Label>
                                            <Form.Control as="textarea" rows={2}
                                                value={form.未授權放行理由 ?? ''}
                                                onChange={e => setField('未授權放行理由', e.target.value)} />
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}

                    <Form.Label className="mt-2">備註</Form.Label>
                    <Form.Control as="textarea" rows={1} value={form.備註 ?? ''}
                        onChange={e => setField('備註', e.target.value)} />

                    <Button className="mt-2" variant="success" size="sm"
                        onClick={handleAdd} disabled={!canAdd || createDisp.isPending}>新增此處置</Button>
                </Form>
            </Modal.Body>
            <Modal.Footer>
                <div className="d-flex w-100 justify-content-between">
                    <div>
                        <Button variant="warning" size="sm" className="me-1"
                            onClick={handleCreateCAPA} disabled={createCAPA.isPending}>轉開 CAPA</Button>
                        <Button variant="info" size="sm" onClick={convertToRework}>轉重工</Button>
                    </div>
                    {/* 結案按鈕：僅在所有不良品皆已處置時可用 */}
                    <Button variant="primary" onClick={handleCloseNcmr}
                        disabled={!canClose || updateNCMR.isPending}>
                        結案（{canClose ? '可結案' : '處置未完成'}）
                    </Button>
                </div>
            </Modal.Footer>
        </Modal>
        <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </>
    );
};

export default DispositionModal;
