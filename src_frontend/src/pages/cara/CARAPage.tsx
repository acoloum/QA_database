import { useState, useEffect } from 'react';
import { Button, Card, Table, Badge } from 'react-bootstrap';
import api from '../../services/api';
import CARAModal from '../../components/cara/CARAModal';
import type { CAR } from '../../types';
import { useNavigate } from 'react-router-dom';

const CARAPage = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<CAR[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const res = await api.get('/cara');
            const mapped = res.data.map((item: Record<string, unknown>) => ({
                id: item.識別碼,
                no: item.單號,
                ncmr_no: item.ncmr_number || item.ncmr_id,
                source: item.ncmr_source,
                vendor: item.ncmr_vendor,
                material: item.ncmr_material,
                product: item.ncmr_product,
                create_date: item.建立日期 || item.ncmr_date,
                owner: item.負責人員姓名,
                status: item.狀態
            }));
            setData(mapped);
        } catch (error) {
            console.error("Failed to load CAR data", error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!window.confirm(`確定要刪除 CAR #${id} 嗎？`)) return;
        try {
            await api.post('/cara/delete', { id });
            loadData();
        } catch (error) {
            console.error("Delete failed", error);
        }
    };

    const handleEdit = (id: number) => {
        setEditId(id);
        setShowModal(true);
    };

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2 className="text-primary fw-bold"><i className="bi bi-shield-check"></i> 矯正措施要求 (CAR)</h2>
                <Button className="btn-back-home" onClick={() => navigate('/')}>
                    <i className="bi bi-arrow-left"></i> 回首頁
                </Button>
            </div>

            <Card className="shadow-sm">
                <Card.Body>
                    <Table hover responsive className="align-middle">
                        <thead className="table-light">
                            <tr>
                                <th>單號</th>
                                <th>關聯異常單</th>
                                <th>廠商</th>
                                <th>材質</th>
                                <th>規格</th>
                                <th>建立日期</th>
                                <th>負責人</th>
                                <th>狀態</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr><td colSpan={9} className="text-center py-4">載入中...</td></tr>
                            ) : data.length === 0 ? (
                                <tr><td colSpan={9} className="text-center py-4">無資料</td></tr>
                            ) : (
                                data.map(item => (
                                    <tr key={item.id}>
                                        <td className="fw-bold">{item.no}</td>
                                        <td>#{item.ncmr_no} ({item.source})</td>
                                        <td>{item.vendor || '-'}</td>
                                        <td>{item.material || '-'}</td>
                                        <td>{item.product || '-'}</td>
                                        <td>{item.create_date?.substring(0, 10) || '-'}</td>
                                        <td>{item.owner || '-'}</td>
                                        <td>
                                            <Badge bg={item.status === '已結案' ? 'success' : 'primary'}>
                                                {item.status}
                                            </Badge>
                                        </td>
                                        <td>
                                            <Button variant="outline-primary" size="sm" className="me-2" onClick={() => handleEdit(item.id)}>處理</Button>
                                            <Button variant="outline-danger" size="sm" onClick={() => handleDelete(item.id)}>刪除</Button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            <CARAModal
                show={showModal}
                handleClose={() => setShowModal(false)}
                onSuccess={loadData}
                editId={editId}
            />
        </div>
    );
};

export default CARAPage;
