import { Modal, Button } from 'react-bootstrap';
import { useNavigate } from 'react-router';

interface ReworkFollowUpModalProps {
    show: boolean;
    onHide: () => void;
    ncmrId: number;
    ncmrNumber: string;
}

/**
 * 重工結案後的後續追蹤 Modal：
 * 若關聯 NCMR 尚未開立 CAPA，提示使用者是否要開立 CAPA。
 */
const ReworkFollowUpModal = ({ show, onHide, ncmrId, ncmrNumber }: ReworkFollowUpModalProps) => {
    const navigate = useNavigate();

    const handleOpenCapa = () => {
        onHide();
        navigate(`/ncmr?openCapaFor=${ncmrId}`);
    };

    return (
        <Modal show={show} onHide={onHide} centered>
            <Modal.Header closeButton>
                <Modal.Title>重工已完成</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <p>
                    NCMR 單號 <strong>{ncmrNumber}</strong> 的重工已結案。
                </p>
                <p className="text-muted">
                    若根因為製程或系統性問題，建議開立 CAPA 進行根本原因分析與系統性矯正。
                </p>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onHide}>
                    暫不處理
                </Button>
                <Button variant="primary" onClick={handleOpenCapa}>
                    開立 CAPA
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ReworkFollowUpModal;
