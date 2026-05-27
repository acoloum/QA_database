import { useState, useEffect } from 'react';
import { Button, Card, Table, Badge, Col, Form } from 'react-bootstrap';
import type { NCMR } from '../../types';
import NCMRModal from '../../components/ncmr/NCMRModal';
import DispositionModal from '../../components/ncmr/DispositionModal';
import FilterBar from '../../components/common/FilterBar';
import PaginationBar from '../../components/common/PaginationBar';
import { useNavigate } from 'react-router-dom';
import { useNCMRList, useDeleteNCMR, useCreateCAPA, useNCMRDetail } from '../../hooks/useNCMR';
import type { NCMRListParams } from '../../hooks/useNCMR';

const EMPTY_FILTERS: NCMRListParams = {
    page: 1, per_page: 20,
    date_from: '', date_to: '', source: '', vendor: '', material: '', product_info: '', status: ''
};

const NCMRPage = () => {
    const navigate = useNavigate();
    const [filters, setFilters] = useState<NCMRListParams>(EMPTY_FILTERS);
    const [page, setPage] = useState(1);

    const activeParams: NCMRListParams = {
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
        page,
        per_page: 20,
    };

    const { data: result, isLoading } = useNCMRList(activeParams);
    const ncmrList = result?.data ?? [];
    const total = result?.total ?? 0;

    const deleteMutation = useDeleteNCMR();
    const createCAPAMutation = useCreateCAPA();

    const [showModal, setShowModal] = useState(false);
    const [showDisposeModal, setShowDisposeModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [disposeItem, setDisposeItem] = useState<NCMR | null>(null);
    const [printItem, setPrintItem] = useState<NCMR | null>(null);

    const { data: printDetail } = useNCMRDetail(printItem?.id || null);

    const handleFilterChange = (key: string, value: string) => {
        setFilters(prev => ({ ...prev, [key]: value }));
        setPage(1);
    };

    const handleReset = () => {
        setFilters(EMPTY_FILTERS);
        setPage(1);
    };

    useEffect(() => {
        if (printItem && printDetail) {
            const d = printDetail;
            const formatQty = (val: unknown) => val ? Math.floor(Number(val)).toString() : '';
            const ncmrNo = d.NCMR單號 || d.單號 || (d.識別碼 ? `NCMR-${d.識別碼}` : '');
            const printContent = `<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><title>不合格品異常單 - ${ncmrNo}</title>
<style>body{font-family:'Microsoft JhengHei',Arial,sans-serif;padding:20px}table{width:100%;border-collapse:collapse;margin-bottom:20px}th,td{border:1px solid #333;padding:8px;font-size:14px}th{background:#f0f0f0;text-align:center;width:150px}</style>
</head><body>
<div style="text-align:center"><h2>不合格品異常單 (NCMR)</h2></div>
<table>
<tr><th>單號</th><td>${ncmrNo}</td><th>發現日期</th><td>${d.日期 || d.發現日期 || ''}</td></tr>
<tr><th>來源</th><td>${d.來源 || ''}</td><th>廠商</th><td>${d.廠商 || ''}</td></tr>
<tr><th>材質</th><td>${d.材質 || ''}</td><th>規格</th><td>${d.產品資訊 || ''}</td></tr>
<tr><th>不合格數量</th><td colspan="3">${formatQty(d.不合格數量)}</td></tr>
<tr><th>批號/訂單號</th><td colspan="3">${d.批號 || ''}</td></tr>
<tr><th>不良描述</th><td colspan="3">${d.不良描述 || ''}</td></tr>
<tr><th>不良原因大類</th><td>${d.不良原因大類 || ''}</td><th>不良原因細項</th><td>${d.不良原因細項 || ''}</td></tr>
<tr><th>發現人員</th><td>${d.發現人員姓名 || ''}</td><th>判定結果</th><td>${d.判定結果 || ''}</td></tr>
<tr><th>狀態</th><td>${d.狀態 || ''}</td><th>建立日期</th><td>${d.建立日期 || d.日期 || ''}</td></tr>
</table>
<div style="text-align:center;margin-top:20px">
<button onclick="window.print()" style="padding:10px 20px;font-size:16px;cursor:pointer">列印</button>
<button onclick="window.close()" style="padding:10px 20px;font-size:16px;cursor:pointer;margin-left:10px">關閉</button>
</div></body></html>`;
            const pw = window.open('', '_blank', 'width=800,height=600');
            if (pw) { pw.document.write(printContent); pw.document.close(); }
            queueMicrotask(() => setPrintItem(null));
        }
    }, [printItem, printDetail]);

    const handleDelete = async (id: number) => {
        if (window.confirm(`確定要刪除異常單 #${id} 嗎？此動作無法復原。`)) {
            deleteMutation.mutate(id);
        }
    };

    const convertToRework = (id: number, no: string) => {
        if (window.confirm('確定要針對此異常單開立重工申請嗎？')) {
            window.open(`/rework?ncmr_id=${id}&ncmr_no=${no || id}`, '_blank');
        }
    };

    const convertTo8D = async (id: number) => {
        if (!window.confirm('確定要針對此異常單開立 8D 矯正措施嗎？')) return;
        try {
            const res = await createCAPAMutation.mutateAsync(id);
            if (res.id) window.location.href = `/capa?editId=${res.id}`;
        } catch { /* handled by toast */ }
    };

    const renderStatusBadge = (status: string) => {
        let bg = 'secondary';
        if (status === '已結案') bg = 'success';
        else if (status === '轉CAPA') bg = 'primary';
        else if (status === '待處理') bg = 'warning';
        return <Badge bg={bg} text={bg === 'warning' ? 'dark' : 'white'}>{status}</Badge>;
    };

    const renderProgress = (item: NCMR) => {
        const badges = [];
        if (item.car_status) badges.push(<Badge key="car" bg={item.car_status === '已結案' ? 'success' : 'info'} className="d-block mb-1">CAR: {item.car_status}</Badge>);
        if (item.capa_status) badges.push(<Badge key="capa" bg={item.capa_status === '已結案' ? 'success' : 'warning'} text="dark" className="d-block mb-1">8D: {item.capa_status}</Badge>);
        if (item.rework_count && item.rework_count > 0) {
            badges.push(<Badge key="rework" bg={item.rework_status === '已完成' ? 'success' : 'primary'} className="d-block mb-1">重工: {item.rework_status === '已完成' ? '已完成' : `執行 ${item.rework_count} 次`}</Badge>);
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
                    <Button variant="primary" onClick={() => { setEditId(null); setShowModal(true); }}>
                        <i className="bi bi-plus-lg"></i> 新增異常單
                    </Button>
                </div>
            </div>

            <FilterBar onReset={handleReset}>
                <Col md={2}><Form.Label className="small mb-1">日期（起）</Form.Label><Form.Control size="sm" type="date" value={filters.date_from ?? ''} onChange={e => handleFilterChange('date_from', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">日期（迄）</Form.Label><Form.Control size="sm" type="date" value={filters.date_to ?? ''} onChange={e => handleFilterChange('date_to', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">來源</Form.Label>
                    <Form.Select size="sm" value={filters.source ?? ''} onChange={e => handleFilterChange('source', e.target.value)}>
                        <option value="">全部</option>
                        <option value="進料">進料</option>
                        <option value="巡檢">巡檢</option>
                        <option value="出貨檢">出貨檢</option>
                        <option value="客訴">客訴</option>
                        <option value="退貨">退貨</option>
                    </Form.Select>
                </Col>
                <Col md={2}><Form.Label className="small mb-1">廠商</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.vendor ?? ''} onChange={e => handleFilterChange('vendor', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">材質</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.material ?? ''} onChange={e => handleFilterChange('material', e.target.value)} /></Col>
                <Col md={2}><Form.Label className="small mb-1">規格</Form.Label><Form.Control size="sm" placeholder="模糊搜尋" value={filters.product_info ?? ''} onChange={e => handleFilterChange('product_info', e.target.value)} /></Col>
                <Col md={1}><Form.Label className="small mb-1">狀態</Form.Label>
                    <Form.Select size="sm" value={filters.status ?? ''} onChange={e => handleFilterChange('status', e.target.value)}>
                        <option value="">全部</option>
                        <option value="待處理">待處理</option>
                        <option value="CAR處理中">CAR處理中</option>
                        <option value="CAR已完成">CAR已完成</option>
                    </Form.Select>
                </Col>
            </FilterBar>

            <Card className="shadow-sm">
                <Card.Body className="p-0">
                    <Table hover className="align-middle table-compact mb-0">
                        <thead className="table-light">
                            <tr>
                                <th>單號</th><th>日期</th><th>來源</th><th>廠商</th><th>材質</th>
                                <th>規格</th><th>不合格數量</th><th>不良描述</th><th>不良原因</th>
                                <th>判定結果</th><th>狀態</th><th>處理進度</th><th className="action-column">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={13} className="text-center py-4">載入中...</td></tr>
                            ) : ncmrList.length === 0 ? (
                                <tr><td colSpan={13} className="text-center py-4">無資料</td></tr>
                            ) : (
                                ncmrList.map((item: NCMR) => (
                                    <tr key={item.id}>
                                        <td>{item.no || item.id}</td>
                                        <td>{item.date}</td>
                                        <td><Badge bg="secondary">{item.source}</Badge></td>
                                        <td>{item.vendor || '-'}</td>
                                        <td>{item.material || '-'}</td>
                                        <td>{item.product_info || '-'}</td>
                                        <td>{item.defect_qty ?? '-'}</td>
                                        <td>{item.defect_desc || '-'}</td>
                                        <td>{item.defect_reason ? <Badge bg="info">{item.defect_reason.split(':')[0]}</Badge> : item.defect_category ? <Badge bg="secondary">{item.defect_category}</Badge> : '-'}</td>
                                        <td onClick={() => { setDisposeItem(item); setShowDisposeModal(true); }} style={{ cursor: 'pointer', textDecoration: 'underline' }} title="點擊進行處置">{item.result || '-'}</td>
                                        <td>{renderStatusBadge(item.status)}</td>
                                        <td>{renderProgress(item)}</td>
                                        <td>
                                            <div className="action-buttons">
                                                <Button variant="outline-dark" size="sm" onClick={() => setPrintItem(item)}>列印</Button>
                                                <Button variant="outline-primary" size="sm" onClick={() => { setEditId(item.id); setShowModal(true); }}>編輯</Button>
                                                <Button variant="outline-warning" size="sm" onClick={() => convertToRework(item.id, item.no || String(item.id))}>轉重工</Button>
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

            <PaginationBar page={page} perPage={20} total={total} onPageChange={setPage} />

            <NCMRModal show={showModal} handleClose={() => { setShowModal(false); setEditId(null); }} onSuccess={() => {}} editId={editId} />
            <DispositionModal show={showDisposeModal} handleClose={() => setShowDisposeModal(false)} onSuccess={() => {}} item={disposeItem} />
        </div>
    );
};

export default NCMRPage;
