import { useState, useEffect } from 'react';
import { Button, Card, Table, Badge } from 'react-bootstrap';
import api from '../../services/api';
import type { NCMR } from '../../types';
import NCMRModal from '../../components/ncmr/NCMRModal';
import DispositionModal from '../../components/ncmr/DispositionModal';

import { useNavigate } from 'react-router-dom';

const NCMRPage = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<NCMR[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [showDisposeModal, setShowDisposeModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [disposeItem, setDisposeItem] = useState<NCMR | null>(null);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const res = await api.get('/ncmr');
            const mappedData = res.data.map((item: any) => ({
                id: item.識別碼,
                no: item.單號 || String(item.識別碼),
                date: item.日期 || item.發現日期,
                source: item.來源,
                vendor: item.廠商,
                material: item.材質,
                product_info: item.產品資訊,
                product_qty: item.產品數量,
                defect_desc: item.不良描述,
                defect_category: item.不良原因大類,
                defect_reason: item.不良原因細項,
                result: item.判定結果,
                status: item.狀態,
                car_status: item.CAR狀態 || item.car狀態,
                capa_status: item.CAPA狀態 || item.capa狀態,
                rework_status: item.重工狀態,
                rework_count: item.重工執行次數
            }));
            setData(mappedData);
        } catch (error) {
            console.error("Failed to load NCMR data", error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (window.confirm(`確定要刪除異常單 #${id} 嗎？此動作無法復原。`)) {
            try {
                await api.post('/ncmr/delete', { id });
                loadData();
            } catch (error) {
                console.error("Delete failed", error);
                alert('刪除失敗');
            }
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
        try {
            const res = await api.post('/cara/create', { ncmr_id: id });
            if (res.data.success) {
                alert(`CAR單號：${res.data.car_number} 已成功建立！`);
                // Navigate to CAR page later
            } else {
                alert('建立CAR失敗：' + res.data.error);
            }
        } catch (error: any) {
            alert('建立CAR時發生錯誤：' + error.message);
        }
    };

    const convertTo8D = async (id: number) => {
        if (!window.confirm('確定要針對此異常單開立 8D 矯正措施嗎？')) return;
        try {
            const res = await api.post('/capa/create', { ncmr_id: id });
            if (res.status === 200) {
                alert('已成功建立 CAPA 單，即將前往矯正措施頁面。');
                window.location.href = `/capa?editId=${res.data.id}`;
            } else {
                alert('建立失敗');
            }
        } catch (error: any) {
            alert('建立時發生錯誤：' + error.message);
        }
    };

    const renderStatusBadge = (status: string) => {
        let bg = 'secondary';
        if (status === '已結案') bg = 'success';
        if (status === '轉CAPA') bg = 'primary'; // Bootstrap primary is blue-ish
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
                <Card.Body className="p-0"> {/* Remove padding to gain space */}
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
                            {loading ? (
                                <tr><td colSpan={13} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={13} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map(item => (
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
                onSuccess={loadData}
                editId={editId}
            />

            <DispositionModal
                show={showDisposeModal}
                handleClose={() => setShowDisposeModal(false)}
                onSuccess={loadData}
                item={disposeItem}
            />
        </div>
    );
};

export default NCMRPage;
