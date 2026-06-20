import { Modal, Button, Row, Col, Table } from 'react-bootstrap';
import { useToleranceDetail } from '../../hooks/useTolerance';

interface ViewToleranceModalProps {
    show: boolean;
    handleClose: () => void;
    viewId: number | null;
}

interface DetailRow {
    item: string;
    position: string;
    size_min: string | number;
    size_max: string | number;
    tol_min: string | number;
    tol_max: string | number;
    std: string | number;
    unit: string;
    remark: string;
}

const ViewToleranceModal = ({ show, handleClose, viewId }: ViewToleranceModalProps) => {
    const { data, isLoading: loading } = useToleranceDetail(viewId, show);
    const main = data?.main;
    const details: DetailRow[] = (data?.details || []).map(d => ({
        item: d.測量項目 || '',
        position: d.測量位置 || '',
        size_min: d.尺寸下限 ?? '',
        size_max: d.尺寸上限 ?? '',
        tol_min: d.公差下限 ?? '',
        tol_max: d.公差上限 ?? '',
        std: d.標準值 ?? '',
        unit: d.單位 || 'mm',
        remark: d.備註 || ''
    }));

    return (
        <Modal show={show} onHide={handleClose} size="xl" backdrop="static">
            <Modal.Header closeButton>
                <Modal.Title>查看公差資料</Modal.Title>
            </Modal.Header>
            <Modal.Body style={{ maxHeight: '80vh', overflowY: 'auto', overflowX: 'auto' }}>
                {loading ? (
                    <div className="text-center py-4">載入中...</div>
                ) : (
                    <>
                        <div className="bg-light p-3 rounded mb-3">
                            <Row className="g-3">
                                <Col md={3}>
                                    <div className="mb-2"><strong>材質：</strong>{main?.材質 || '-'}</div>
                                </Col>
                                <Col md={3}>
                                    <div className="mb-2"><strong>規格：</strong>{main?.規格 || '-'}</div>
                                </Col>
                                <Col md={3}>
                                    <div className="mb-2"><strong>廠商：</strong>{main?.廠商名稱 || '-'}</div>
                                </Col>
                                <Col md={3}>
                                    <div className="mb-2"><strong>建立日期：</strong>{main?.建立日期 || '-'}</div>
                                </Col>
                                <Col md={12}>
                                    <div><strong>備註：</strong>{main?.備註 || '-'}</div>
                                </Col>
                            </Row>
                        </div>

                        <h5 className="mb-2"><i className="bi bi-list"></i> 公差明細</h5>

                        <style type="text/css">
                            {`
                                .sticky-header th {
                                    position: sticky;
                                    top: 0;
                                    z-index: 2;
                                    background-color: var(--bs-light);
                                    box-shadow: inset 0 -1px 0 var(--bs-border-color, #dee2e6);
                                }
                            `}
                        </style>

                        <Table bordered hover size="sm">
                            <thead className="table-light text-center sticky-header">
                                <tr>
                                    <th>測量項目</th>
                                    <th>位置</th>
                                    <th>尺寸下限</th>
                                    <th>尺寸上限</th>
                                    <th>公差下限</th>
                                    <th>公差上限</th>
                                    <th>標準值</th>
                                    <th>單位</th>
                                    <th>備註</th>
                                </tr>
                            </thead>
                            <tbody>
                                {details.map((d, index) => (
                                    <tr key={index}>
                                        <td className="text-center">{d.item || '-'}</td>
                                        <td className="text-center">{d.position || '-'}</td>
                                        <td className="text-center">{d.size_min !== '' ? `${d.size_min} ${d.unit}` : '-'}</td>
                                        <td className="text-center">{d.size_max !== '' ? `${d.size_max} ${d.unit}` : '-'}</td>
                                        <td className="text-center">{d.tol_min !== '' ? `${d.tol_min} ${d.unit}` : '-'}</td>
                                        <td className="text-center">{d.tol_max !== '' ? `${d.tol_max} ${d.unit}` : '-'}</td>
                                        <td className="text-center">{d.std !== '' ? `${d.std} ${d.unit}` : '-'}</td>
                                        <td className="text-center">{d.unit}</td>
                                        <td className="text-center">{d.remark || '-'}</td>
                                    </tr>
                                ))}
                                {details.length === 0 && (
                                    <tr>
                                        <td colSpan={9} className="text-center text-muted">無明細資料</td>
                                    </tr>
                                )}
                            </tbody>
                        </Table>
                    </>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>關閉</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ViewToleranceModal;
