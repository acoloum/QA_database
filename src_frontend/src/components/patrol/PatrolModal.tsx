
import { useState, useEffect, useCallback, Fragment } from 'react';
import { Modal, Button, Form, Row, Col, Table } from 'react-bootstrap';
import {
    usePatrolOptions,
    usePatrolDetail,
    useCreatePatrol,
    useUpdatePatrol
} from '../../hooks/usePatrol';
import type { PatrolCreateInput, PatrolUpdateInput } from '../../types';
import { useExtrusionToleranceCheck } from '../../hooks/useExtrusionTolerance';

interface PatrolModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    editId: number | null;
}

interface PatrolDetailInput {
    group: string;
    item: string;
    pos: string;
    min: string;
    max: string;
}

const PatrolModal = ({ show, handleClose, onSuccess, editId }: PatrolModalProps) => {
    // Hooks
    const { data: optionsData } = usePatrolOptions();
    const machines = optionsData?.machines || [];
    const operators = optionsData?.operators || [];
    const inspectors = optionsData?.inspectors || [];
    const customers = optionsData?.customers || [];

    const { data: detailData, isLoading: isLoadingDetail } = usePatrolDetail(editId);

    const createMutation = useCreatePatrol();
    const updateMutation = useUpdatePatrol();

    // Form State
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [machine, setMachine] = useState('');
    const [operator, setOperator] = useState('');
    const [inspector, setInspector] = useState('');
    const [customer, setCustomer] = useState('');
    const [material, setMaterial] = useState('');
    const [batch, setBatch] = useState('');
    const [spec, setSpec] = useState('');

    // Details State
    const [groupCount, setGroupCount] = useState(1);
    const [details, setDetails] = useState<PatrolDetailInput[]>([]);
    const [showInner, setShowInner] = useState(false);

    const resetForm = useCallback(() => {
         
        console.log('resetForm called');
        setDate(new Date().toISOString().split('T')[0]);
        setMachine('');
        setOperator('');
        setInspector('');
        setCustomer('');
        setMaterial('');
        setBatch('');
        setSpec('');
        setGroupCount(1);
        setDetails([]);
        setShowInner(false);
    }, []);

    // Populate form when detailData loads or when modal opens
    useEffect(() => {
         
        console.log('useEffect triggered', { show, editId, detailData });
        if (show) {
            if (editId && detailData) {
                const d = detailData;
                // eslint-disable-next-line react-hooks/set-state-in-effect
                setDate(d.main.檢驗日期);
                 
                setMachine(d.main.機台);
                 
                setOperator(d.main.主機手);
                 
                setInspector(d.main.檢驗人員);
                 
                setCustomer(d.main.客戶名稱);
                 
                setMaterial(d.main.材質);
                 
                setBatch(d.main.原料批號);
                 
                setSpec(d.main.擠壓規格);

                // Parse details to state
                const newDetails: PatrolDetailInput[] = d.details.map((item: Record<string, unknown>) => ({
                    group: item.group,
                    item: item.item,
                    pos: item.pos,
                    min: item.min?.toString() || '',
                    max: item.max?.toString() || ''
                }));
                 
                setDetails(newDetails);

                // Determine group count
                const groups = new Set(newDetails.map(d => d.group));
                 
                setGroupCount(groups.size || 1);
            } else if (!editId) {
                 
                console.log('Calling resetForm from useEffect');
                resetForm();
            }
        }
    }, [show, editId, detailData, resetForm]);

    const handleDetailChange = (group: string, pos: string, item: string, type: 'min' | 'max', value: string) => {
        // console.log(`Change: ${group} ${pos} ${item} ${type} = ${value}`);
        setDetails(prev => {
            const existingIndex = prev.findIndex(d => d.group === group && d.pos === pos && d.item === item);
            if (existingIndex >= 0) {
                const newDetails = [...prev];
                newDetails[existingIndex] = { ...newDetails[existingIndex], [type]: value };
                return newDetails;
            } else {
                return [...prev, {
                    group, item, pos, min: type === 'min' ? value : '', max: type === 'max' ? value : ''
                }];
            }
        });
    };

    const getDetailValue = (group: string, pos: string, item: string, type: 'min' | 'max') => {
        const detail = details.find(d => d.group === group && d.pos === pos && d.item === item);
        return detail ? detail[type] : '';
    };

    const handleSubmit = async () => {
        console.log('Current details state:', details);

        // Client-side required field validation
        const missingFields: string[] = [];
        if (!date) missingFields.push('日期');
        if (!machine) missingFields.push('機台');
        if (!operator) missingFields.push('主機手');
        if (!inspector) missingFields.push('檢驗員');

        if (missingFields.length > 0) {
            alert(`請填寫以下必填欄位：\n${missingFields.join('、')}`);
            return;
        }

        // Collect valid details
        const validDetails = details.filter(d => d.min !== '' || d.max !== '').map(d => ({
            group: d.group,
            item: d.item,
            pos: d.pos,
            min: d.min === '' ? null : parseFloat(d.min),
            max: d.max === '' ? null : parseFloat(d.max)
        }));

        console.log('Valid details:', validDetails);

        if (validDetails.length === 0) {
            alert('請至少輸入一組測量數值');
            return;
        }

        const payload = {
            id: editId,
            "檢驗日期": date,
            "機台": machine,
            "主機手": operator,
            "客戶名稱": customer,
            "材質": material,
            "原料批號": batch,
            "擠壓規格": spec,
            "檢驗人員": inspector,
            "details": validDetails
        };

        try {
            if (editId) {
                // PatrolModal 使用舊欄位格式（機台/主機手），後端仍可接受
                // 需透過 unknown 才能轉型，因為兩種型別沒有足夠的重疊
                await updateMutation.mutateAsync({ id: editId, data: payload as unknown as PatrolUpdateInput });
            } else {
                await createMutation.mutateAsync(payload as PatrolCreateInput);
            }
            onSuccess();
            handleClose();
        } catch (error) {
            console.error(error);
        }
    };

    // 取得擠壓公差（有 material 就查，spec 空字串表示通用）
    const { data: toleranceResult } = useExtrusionToleranceCheck(material, spec);
    const tolerances = toleranceResult?.found ? (toleranceResult.tolerances ?? []) : [];

    // 判斷單一儲存格是否 NG（雙側比對：同時檢查上下限）
    const isCellNG = (pos: string, item: string, type: 'min' | 'max', gName: string): boolean => {
        const tol = tolerances.find((t) => t.項目 === item);
        if (!tol) return false;
        const valStr = getDetailValue(gName, pos, item, type);
        if (valStr === '') return false;
        const val = parseFloat(valStr);
        if (tol.公差下限 != null && val < tol.公差下限) return true;
        if (tol.公差上限 != null && val > tol.公差上限) return true;
        return false;
    };

    // 判斷同心度是否 NG（同心度 = 最大厚度 - 最小厚度）
    const isConcentricityNG = (pos: string, gName: string): boolean => {
        const tol = tolerances.find((t) => t.項目 === '同心度');
        if (!tol) return false;
        const minStr = getDetailValue(gName, pos, '厚度', 'min');
        const maxStr = getDetailValue(gName, pos, '厚度', 'max');
        if (minStr === '' || maxStr === '') return false;
        const concentricity = parseFloat(maxStr) - parseFloat(minStr);
        if (tol.公差下限 != null && concentricity < tol.公差下限) return true;
        if (tol.公差上限 != null && concentricity > tol.公差上限) return true;
        return false;
    };

    // Render helper
    const renderTableRows = () => {
        const rows = [];
        const positions = ['前段', '中段', '後段'];
        const items = ['外徑', '內徑', '厚度'];

        for (let i = 1; i <= groupCount; i++) {
            const gName = `第${i}組`;
            rows.push(
                <tr key={i}>
                    <td className="fw-bold bg-light">{gName}</td>
                    {positions.map(pos =>
                        items.map(item => {
                            if (item === '內徑' && !showInner) return null;
                            return (
                                <Fragment key={`${pos}-${item}`}>
                                    <td style={{ padding: '2px', backgroundColor: (isCellNG(pos, item, 'min', gName) || (item === '厚度' && isConcentricityNG(pos, gName))) ? '#ffcccc' : undefined }}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            step="0.01"
                                            value={getDetailValue(gName, pos, item, 'min')}
                                            onChange={e => handleDetailChange(gName, pos, item, 'min', e.target.value)}
                                            className="patrol-input"
                                            style={{ backgroundColor: (isCellNG(pos, item, 'min', gName) || (item === '厚度' && isConcentricityNG(pos, gName))) ? '#ffcccc' : undefined }}
                                        />
                                    </td>
                                    <td style={{ padding: '2px', backgroundColor: (isCellNG(pos, item, 'max', gName) || (item === '厚度' && isConcentricityNG(pos, gName))) ? '#ffcccc' : undefined }}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            step="0.01"
                                            value={getDetailValue(gName, pos, item, 'max')}
                                            onChange={e => handleDetailChange(gName, pos, item, 'max', e.target.value)}
                                            className="patrol-input"
                                            style={{ backgroundColor: (isCellNG(pos, item, 'max', gName) || (item === '厚度' && isConcentricityNG(pos, gName))) ? '#ffcccc' : undefined }}
                                        />
                                    </td>
                                </Fragment>
                            );
                        })
                    )}
                </tr>
            );
        }
        return rows;
    };

    const isSaving = createMutation.isPending || updateMutation.isPending;

    return (
        <Modal show={show} onHide={handleClose} dialogClassName="modal-patrol-wide" backdrop="static">
            <div className="modal-dialog" style={{ maxWidth: '1600px', width: '99%', overflowX: 'auto' }}>
                <div className="modal-content" style={{ overflowX: 'auto' }}>
                    <Modal.Header closeButton>
                        <Modal.Title>{editId ? '編輯巡檢紀錄' : '新增巡檢紀錄'}</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        {editId && isLoadingDetail ? (
                            <div className="text-center py-5">
                                <div className="spinner-border text-primary" role="status">
                                    <span className="visually-hidden">Loading...</span>
                                </div>
                            </div>
                        ) : (
                            <div>
                                <Form>
                                    <Row className="g-3 mb-4">
                                        <Col md={3}><Form.Label>日期</Form.Label><Form.Control type="date" value={date} onChange={e => setDate(e.target.value)} /></Col>
                                        <Col md={3}>
                                            <Form.Label>機台</Form.Label>
                                            <Form.Select value={machine} onChange={e => setMachine(e.target.value)}>
                                                <option value="">請選擇</option>
                                                {machines.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={3}>
                                            <Form.Label>主機手</Form.Label>
                                            <Form.Select value={operator} onChange={e => setOperator(e.target.value)}>
                                                <option value="">請選擇</option>
                                                {operators.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={3}>
                                            <Form.Label>檢驗員</Form.Label>
                                            <Form.Select value={inspector} onChange={e => setInspector(e.target.value)}>
                                                <option value="">請選擇</option>
                                                {inspectors.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={4}>
                                            <Form.Label>客戶名稱</Form.Label>
                                            <Form.Select value={customer} onChange={e => setCustomer(e.target.value)} style={{ minWidth: '100%' }}>
                                                <option value="">請選擇</option>
                                                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                                            </Form.Select>
                                        </Col>
                                        <Col md={4}><Form.Label>材質</Form.Label><Form.Control value={material} onChange={e => setMaterial(e.target.value)} style={{ width: '100%' }} /></Col>
                                        <Col md={4}><Form.Label>原料批號</Form.Label><Form.Control value={batch} onChange={e => setBatch(e.target.value)} style={{ width: '100%' }} /></Col>
                                        <Col md={12}><Form.Label>擠壓規格</Form.Label><Form.Control value={spec} onChange={e => setSpec(e.target.value)} style={{ width: '100%' }} /></Col>
                                    </Row>

                                    <div className="table-responsive" style={{ overflow: 'auto', maxHeight: '50vh', display: 'block' }}>
                                        <Table bordered size="sm" className="text-center align-middle" style={{ minWidth: showInner ? '1550px' : '1050px', tableLayout: 'fixed' }}>
                                            <thead className="table-light">
                                                <tr>
                                                    <th rowSpan={3} style={{ width: '50px' }}>組別</th>
                                                    <th colSpan={showInner ? 6 : 4}>前段</th>
                                                    <th colSpan={showInner ? 6 : 4}>中段</th>
                                                    <th colSpan={showInner ? 6 : 4}>後段</th>
                                                </tr>
                                                <tr>
                                                    {['前段', '中段', '後段'].map(sec =>
                                                        ['外徑', '內徑', '厚度'].map(item => {
                                                            if (item === '內徑' && !showInner) return null;
                                                            return <th key={`${sec}-${item}`} colSpan={2}>{item}</th>;
                                                        })
                                                    )}
                                                </tr>
                                                <tr>
                                                    {['前段', '中段', '後段'].map(sec =>
                                                        ['外徑', '內徑', '厚度'].map(item => {
                                                            if (item === '內徑' && !showInner) return null;
                                                            return <Fragment key={`${sec}-${item}-hd`}><th>MIN</th><th>MAX</th></Fragment>;
                                                        })
                                                    )}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {renderTableRows()}
                                            </tbody>
                                        </Table>
                                    </div>

                                    <div className="d-flex gap-2 mt-3">
                                        <Button variant="outline-primary" onClick={() => setGroupCount(c => c + 1)}>
                                            <i className="bi bi-plus-lg"></i> 新增組別
                                        </Button>
                                        <Button variant="outline-danger" onClick={() => setGroupCount(c => Math.max(1, c - 1))}>
                                            <i className="bi bi-dash-lg"></i> 刪除組別
                                        </Button>
                                        <Button variant={showInner ? "info" : "outline-info"} onClick={() => setShowInner(!showInner)}>
                                            <i className={`bi bi-arrows-${showInner ? 'collapse' : 'expand'}`}></i> {showInner ? '隱藏內徑' : '展開內徑'}
                                        </Button>
                                    </div>

                                </Form>
                            </div>
                        )}
                    </Modal.Body>
                    <Modal.Footer>
                        <Button variant="secondary" onClick={handleClose}>取消</Button>
                        <Button variant="success" onClick={handleSubmit} disabled={isSaving} type="button">
                            {isSaving ? '儲存中...' : '儲存'}
                        </Button>
                    </Modal.Footer>
                </div>
            </div>
        </Modal>
    );
};

export default PatrolModal;
