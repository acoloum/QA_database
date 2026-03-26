import { Modal, Table, Badge } from 'react-bootstrap';
import { useExtrusionToleranceDetail } from '../../hooks/useExtrusionTolerance';

interface Props {
    show: boolean;
    id: number | null;
    onClose: () => void;
}

const ViewExtrusionToleranceModal = ({ show, id, onClose }: Props) => {
    const { data, isLoading } = useExtrusionToleranceDetail(id);

    return (
        <Modal show={show} onHide={onClose} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>擠壓公差詳細</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {isLoading && <p>載入中…</p>}
                {data && (
                    <>
                        <dl className="row mb-3">
                            <dt className="col-sm-2">材質</dt>
                            <dd className="col-sm-4">{data.main.材質}</dd>
                            <dt className="col-sm-2">規格</dt>
                            <dd className="col-sm-4">{data.main.規格 || '（通用）'}</dd>
                            <dt className="col-sm-2">備註</dt>
                            <dd className="col-sm-10">{data.main.備註}</dd>
                        </dl>
                        <Table bordered size="sm">
                            <thead className="table-secondary">
                                <tr>
                                    <th>測量項目</th>
                                    <th>測量位置</th>
                                    <th>公差下限</th>
                                    <th>公差上限</th>
                                    <th>標準值</th>
                                    <th>單位</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.details.map((d, i) => (
                                    <tr key={i}>
                                        <td>{d.測量項目}</td>
                                        <td>{d.測量位置}</td>
                                        <td>{d.公差下限 ?? '-'}</td>
                                        <td>{d.公差上限 ?? '-'}</td>
                                        <td>{d.標準值 ?? '-'}</td>
                                        <td><Badge bg="secondary">{d.單位}</Badge></td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    </>
                )}
            </Modal.Body>
        </Modal>
    );
};

export default ViewExtrusionToleranceModal;
