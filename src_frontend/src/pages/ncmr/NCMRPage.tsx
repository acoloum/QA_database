
import { useState } from 'react';
import { Button, Card, Table, Badge } from 'react-bootstrap';
import type { NCMR } from '../../types';
import NCMRModal from '../../components/ncmr/NCMRModal';
import DispositionModal from '../../components/ncmr/DispositionModal';
import { useNavigate } from 'react-router-dom';
import { useNCMRList, useDeleteNCMR, useCreateCARA, useCreateCAPA } from '../../hooks/useNCMR';

const NCMRPage = () => {
    const navigate = useNavigate();
    const { data: ncmrList = [], isLoading } = useNCMRList();

    // Mutations
    const deleteMutation = useDeleteNCMR();
    const createCARAMutation = useCreateCARA();
    const createCAPAMutation = useCreateCAPA();

    const [showModal, setShowModal] = useState(false);
    const [showDisposeModal, setShowDisposeModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [disposeItem, setDisposeItem] = useState<NCMR | null>(null);

    const handleDelete = async (id: number) => {
        if (window.confirm(`確定要刪除異常單 #${id} 嗎？此動作無法復原。`)) {
            deleteMutation.mutate(id);
        }
    };

    const handleAdd = () => {
        setEditId(null);
        setShowModal(true);
    };

    const handleEdit = (id: number) => {
        setEditId(id);
        setShowModal(true);
    };

    const handleDispose = (item: NCMR) => {
        setDisposeItem(item);
        setShowDisposeModal(true);
    };

    const convertToRework = async (id: number, no: string) => {
        if (window.confirm('確定要針對此異常單開立重工申請嗎？')) {
            window.open(`/rework?ncmr_id=${id}&ncmr_no=${no || id}`, '_blank');
        }
    };

    const convertToCAR = async (id: number) => {
        if (!window.confirm('確定要將此異常單轉為CAR嗎？')) return;
        createCARAMutation.mutate(id);
    };

    const convertTo8D = async (id: number) => {
        if (!window.confirm('確定要針對此異常單開立 8D 矯正措施嗎？')) return;
        // 8D creation needs to redirect to CAPA page on success.
        // We can handle success in local callback or use the mutation result.
        // Since we need the ID returned, we should probably use mutateAsync or onSuccess in mutation.
        // The hook I defined doesn't return ID in onSuccess.
        // I should use mutateAsync here to get result.
        try {
            const res = await createCAPAMutation.mutateAsync(id);
            if (res.success) { // Hook returns res.data
                // Wait, hook returns res.data.
                // Backend returns {success: true, id: ...} or just {id, ...}?
                // Checking backend route: return jsonify({"success": True, **result})
                // Result from create_capa returns {id: ...} probably?
                // Let's assume it returns {id}.
                // The hook returns res.data which is JSON.
                if (res.id) {
                    window.location.href = `/capa?editId=${res.id}`;
                }
            }
        } catch (e) {
            // Error handled by global handler
        }
    };

    const renderStatusBadge = (status: string) => {
        let bg = 'secondary';
        if (status === '已結案') bg = 'success';
        if (status === '轉CAPA') bg = 'primary';
        if (status === '待處理') bg = 'warning';
        return <Badge bg={bg} text={bg === 'warning' ? 'dark' : 'white'}>{status}</Badge>;
    };

    const renderProgress = (item: NCMR) => {
        const badges = [];
        if (item.status === 'CAR處理中' || item.car_status) {
            const carStatus = item.car_status || '進行中';
            badges.push(<Badge key="car" bg={carStatus === '已結案' ? 'success' : 'info'} className="d-block mb-1">CAR: {carStatus}</Badge>);
        }
        if (item.status === '矯正中' || item.capa_status) {
            const capaStatus = item.capa_status || '進行中';
            badges.push(<Badge key="capa" bg={capaStatus === '已結案' ? 'success' : 'warning'} text="dark" className="d-block mb-1">8D: {capaStatus}</Badge>);
        }
        if (item.status === '轉重工' || (item.rework_count && item.rework_count > 0)) {
            const reworkStatus = item.rework_status === '已完成' ? '已完成' : `執行: ${item.rework_count || 0} 次`;
            badges.push(<Badge key="rework" bg={item.rework_status === '已完成' ? 'success' : 'primary'} className="d-block mb-1">重工: {reworkStatus}</Badge>);
        }
        return badges.length > 0 ? badges : '-';
    };

    return (
        <div className="p-0">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-danger fw-bold"><i className="bi bi-exclamation-octagon"></i> 不合格品管理 (NCMR)</h2>
                <div>
                    <Button className="btn-back-home me-2" onClick={() => navigate('/')}>
                        <i className="bi bi-arrow-left"></i> 回首頁
                    </Button>
                    <Button variant="primary" onClick={handleAdd}>
                        <i className="bi bi-plus-lg"></i> 新增異常單
                    </Button>
                </div>
            </div>

            <Card className="shadow-sm">
                <Card.Body className="p-0">
                    <Table hover className="align-middle table-compact mb-0">
                        <thead className="table-light">
                            <tr>
                                <th>單號</th>
                                <th>日期</th>
                                <th>來源</th>
                                <th>廠商</th>
                                <th>材質</th>
                                <th>規格</th>
                                <th>數量</th>
                                <th>不良描述</th>
                                <th>不良原因</th>
                                <th>判定結果</th>
                                <th>狀態</th>
                                <th>處理進度</th>
                                <th className="action-column">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={13} className="text-center py-4">載入中...</td></tr>
                            ) : ncmrList.length === 0 ? (
                                <tr><td colSpan={13} className="text-center py-4">無資料</td></tr>
                            ) : (
                                ncmrList.map((item: any) => (
                                    <tr key={item.id}>
                                        <td>{item.no || item.id}</td>
                                        <td>{item.date}</td>
                                        <td><Badge bg="secondary">{item.source}</Badge></td>
                                        <td>{item.vendor || '-'}</td>
                                        <td>{item.material || '-'}</td>
                                        <td>{item.product_info || '-'}</td>
                                        <td>{item.product_qty || '-'}</td>
                                        <td>{item.defect_desc || '-'}</td>
                                        <td>
                                            {item.defect_reason ? (
                                                <Badge bg="info">{item.defect_reason.split(':')[0]}</Badge>
                                            ) : item.defect_category ? (
                                                <Badge bg="secondary">{item.defect_category}</Badge>
                                            ) : '-'}
                                        </td>
                                        <td onClick={() => handleDispose(item)} style={{ cursor: 'pointer', textDecoration: 'underline' }} title="點擊進行處置">
                                            {item.result || '-'}
                                        </td>
                                        <td>{renderStatusBadge(item.status)}</td>
                                        <td>{renderProgress(item)}</td>
                                        <td>
                                            <div className="action-buttons">
                                                <Button variant="outline-primary" size="sm" onClick={() => handleEdit(item.id)}>編輯</Button>
                                                <Button variant="outline-warning" size="sm" onClick={() => convertToRework(item.id, item.no || String(item.id))}>轉重工</Button>
                                                <Button variant="outline-info" size="sm" onClick={() => convertToCAR(item.id)}>轉CAR</Button>
                                                <Button variant="outline-success" size="sm" onClick={() => convertTo8D(item.id)}>轉8D</Button>
                                                <Button variant="outline-danger" size="sm" onClick={() => handleDelete(item.id)}>刪除</Button>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            <NCMRModal
                show={showModal}
                handleClose={() => setShowModal(false)}
                onSuccess={() => { }} // React Query handles invalidation
                editId={editId}
            />

            <DispositionModal
                show={showDisposeModal}
                handleClose={() => setShowDisposeModal(false)}
                onSuccess={() => { }} // React Query handles invalidation
                item={disposeItem}
            />
        </div>
    );
};

export default NCMRPage;
