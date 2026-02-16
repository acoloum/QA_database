
import { useState, useEffect } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';
import {
    useInspectors,
    useNCMRDetail,
    useCreateNCMR,
    useUpdateNCMR
} from '../../hooks/useNCMR';

interface NCMRModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

const DEFECT_REASONS: Record<string, string[]> = {
    'M': ['M-01: 鋁錠成分不符', 'M-02: 鋁棒尺寸超差', 'M-03: 鋁材夾雜物/氣孔', 'M-04: 材質混料', 'M-05: 鋁棒表面缺陷', 'M-06: 鋁材硬度異常'],
    'E': ['E-01: 擠型溫度不當', 'E-02: 擠壓速度異常', 'E-03: 擠壓比不當', 'E-04: 表面波紋/料紋', 'E-05: 表面氣泡/砂眼/針孔', 'E-06: 表面刮傷/擦傷', 'E-07: 尺寸公差超差', 'E-08: 彎曲/扭曲/翹曲', 'E-09: 橘皮/粗晶', 'E-10: 亮帶/暗帶/色差', 'E-11: 料頭料尾不良', 'E-12: 擠型裂紋/撕裂', 'E-13: 機台參數設定錯誤'],
    'D': ['D-01: 內徑尺寸超差', 'D-02: 外徑尺寸超差', 'D-03: 壁厚不均', 'D-04: 橢圓度超差', 'D-05: 抽管表面刮傷', 'D-06: 抽管速度過快導致變形', 'D-07: 潤滑不良', 'D-08: 抽管裂紋'],
    'H': ['H-01: 硬度不足', 'H-02: 硬度過高', 'H-03: 淬火裂紋', 'H-04: 熱處理變形/彎曲', 'H-05: 淬火溫度不當', 'H-06: 時效溫度/時間不當', 'H-07: 冷卻速度不當', 'H-08: 爐溫不均', 'H-09: 硬度分布不均'],
    'T': ['T-01: 擠型模磨損/損傷', 'T-02: 擠型模設計不良', 'T-03: 擠型模溫度控制不當', 'T-04: 抽管模磨損', 'T-05: 模具清潔不良', 'T-06: 治具定位不準', 'T-07: 模具維護保養不足'],
    'P': ['P-01: 操作錯誤', 'P-02: 參數設定錯誤', 'P-03: 未依SOP作業', 'P-04: 訓練不足', 'P-05: 換線/換模錯誤', 'P-06: 標示錯誤/混料', 'P-07: 疲勞失誤'],
    'Q': ['Q-01: 量具未校驗/不準', 'Q-02: 檢驗方法錯誤', 'Q-03: 漏檢', 'Q-04: 誤判', 'Q-05: 取樣方式不當', 'Q-06: 檢驗標準理解錯誤'],
    'O': ['O-01: 包裝不良', 'O-02: 搬運碰撞/刮傷', 'O-03: 儲存環境不當', 'O-04: 圖面/規格錯誤', 'O-05: 客戶使用不當', 'O-06: 運輸損傷', 'O-07: 待分析/複合原因']
};

const NCMRModal = ({ show, handleClose, onSuccess, editId }: NCMRModalProps) => {
    // Hooks
    const { data: inspectors = [] } = useInspectors();
    const { data: detailData, isLoading: isLoadingDetail } = useNCMRDetail(editId);

    const createMutation = useCreateNCMR();
    const updateMutation = useUpdateNCMR();

    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [source, setSource] = useState('進料');
    const [vendor, setVendor] = useState('');
    const [material, setMaterial] = useState('');
    const [productInfo, setProductInfo] = useState('');
    const [productQty, setProductQty] = useState('');
    const [batch, setBatch] = useState('');
    const [defectQty, setDefectQty] = useState('');
    const [desc, setDesc] = useState('');
    const [category, setCategory] = useState('');
    const [reason, setReason] = useState('');
    const [inspector, setInspector] = useState('');
    const [result, setResult] = useState('');

    const resetForm = () => {
        setDate(new Date().toISOString().split('T')[0]);
        setSource('進料');
        setVendor('');
        setMaterial('');
        setProductInfo('');
        setProductQty('');
        setBatch('');
        setDefectQty('');
        setDesc('');
        setCategory('');
        setReason('');
        setInspector('');
        setResult('');
    };

    useEffect(() => {
        if (show) {
            if (editId && detailData) {
                const d = detailData;
                setDate(d.日期 || d.發現日期);
                setSource(d.來源);
                setVendor(d.廠商 || '');
                setMaterial(d.材質 || '');
                setProductInfo(d.產品資訊 || '');
                setProductQty(d.產品數量 || '');
                setBatch(d.批號 || '');
                setDefectQty(d.不合格數量 || '');
                setDesc(d.不良描述 || '');
                setCategory(d.不良原因大類 || '');
                setReason(d.不良原因細項 || '');
                setInspector(d.發現人員姓名 || '');
                setResult(d.判定結果 || '');
            } else if (!editId) {
                resetForm();
            }
        }
    }, [show, editId, detailData]);

    const handleSubmit = async () => {
        const payload = {
            "識別碼": editId,
            "日期": date,
            "來源": source,
            "廠商": vendor,
            "材質": material,
            "產品資訊": productInfo,
            "產品數量": productQty,
            "批號": batch,
            "不合格數量": defectQty,
            "不良描述": desc,
            "不良原因大類": category,
            "不良原因細項": reason,
            "發現人員姓名": inspector,
            "判定結果": result
        };

        try {
            if (editId) {
                await updateMutation.mutateAsync(payload);
            } else {
                await createMutation.mutateAsync(payload);
            }
            onSuccess();
            handleClose();
        } catch (error) {
            console.error(error);
        }
    };

    const isSaving = createMutation.isPending || updateMutation.isPending;

    return (
        <Modal show={show} onHide={handleClose} size="lg" backdrop="static" fullscreen="sm-down">
            <Modal.Header closeButton>
                <Modal.Title>{editId ? '編輯異常單' : '新增異常單'}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {editId && isLoadingDetail ? (
                    <div className="text-center py-5">
                        <div className="spinner-border text-primary" role="status">
                            <span className="visually-hidden">Loading...</span>
                        </div>
                    </div>
                ) : (
                    <Form>
                        <Row className="g-3">
                            <Col md={6}><Form.Label>發現日期</Form.Label><Form.Control type="date" value={date} onChange={e => setDate(e.target.value)} /></Col>
                            <Col md={6}>
                                <Form.Label>來源</Form.Label>
                                <Form.Select value={source} onChange={e => setSource(e.target.value)}>
                                    <option value="進料">進料</option>
                                    <option value="巡檢">巡檢</option>
                                    <option value="出貨檢">出貨檢</option>
                                    <option value="客訴">客訴</option>
                                    <option value="退貨">退貨</option>
                                </Form.Select>
                            </Col>
                            <Col md={4}><Form.Label>廠商</Form.Label><Form.Control value={vendor} onChange={e => setVendor(e.target.value)} /></Col>
                            <Col md={4}><Form.Label>材質</Form.Label><Form.Control value={material} onChange={e => setMaterial(e.target.value)} /></Col>
                            <Col md={4}><Form.Label>規格</Form.Label><Form.Control value={productInfo} onChange={e => setProductInfo(e.target.value)} /></Col>

                            <Col md={6}><Form.Label>產品數量</Form.Label><Form.Control type="number" value={productQty} onChange={e => setProductQty(e.target.value)} /></Col>
                            <Col md={6}><Form.Label>不合格數量</Form.Label><Form.Control type="number" value={defectQty} onChange={e => setDefectQty(e.target.value)} /></Col>

                            <Col md={12}><Form.Label>批號/訂單號</Form.Label><Form.Control value={batch} onChange={e => setBatch(e.target.value)} /></Col>
                            <Col md={12}><Form.Label>不良描述</Form.Label><Form.Control as="textarea" rows={3} value={desc} onChange={e => setDesc(e.target.value)} /></Col>

                            <Col md={6}>
                                <Form.Label>不良原因大類</Form.Label>
                                <Form.Select value={category} onChange={e => { setCategory(e.target.value); setReason(''); }}>
                                    <option value="">請選擇</option>
                                    <option value="M">M - 鋁材原料</option>
                                    <option value="E">E - 擠型製程</option>
                                    <option value="D">D - 抽管製程</option>
                                    <option value="H">H - 熱處理</option>
                                    <option value="T">T - 模具治具</option>
                                    <option value="P">P - 人員操作</option>
                                    <option value="Q">Q - 品管檢驗</option>
                                    <option value="O">O - 其他</option>
                                </Form.Select>
                            </Col>
                            <Col md={6}>
                                <Form.Label>不良原因細項</Form.Label>
                                <Form.Select value={reason} onChange={e => setReason(e.target.value)} disabled={!category}>
                                    <option value="">請選擇</option>
                                    {category && DEFECT_REASONS[category]?.map(r => (
                                        <option key={r} value={r}>{r}</option>
                                    ))}
                                </Form.Select>
                            </Col>

                            <Col md={6}>
                                <Form.Label>發現人員</Form.Label>
                                <Form.Select value={inspector} onChange={e => setInspector(e.target.value)}>
                                    <option value="">請選擇</option>
                                    {inspectors.map(i => <option key={i.name} value={i.name}>{i.name}</option>)}
                                </Form.Select>
                            </Col>
                            <Col md={6}>
                                <Form.Label>初步判定</Form.Label>
                                <Form.Select value={result} onChange={e => setResult(e.target.value)}>
                                    <option value="">請選擇</option>
                                    <option value="特採">特採</option>
                                    <option value="重工">重工</option>
                                    <option value="報廢">報廢</option>
                                    <option value="退貨">退貨</option>
                                    <option value="選別及補數">選別及補數</option>
                                </Form.Select>
                            </Col>
                        </Row>
                    </Form>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={isSaving}>
                    {isSaving ? '儲存中...' : '儲存'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default NCMRModal;
