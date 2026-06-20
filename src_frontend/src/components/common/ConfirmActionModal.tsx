import { Button, Modal } from 'react-bootstrap';

export interface ConfirmActionState {
  title: string;
  message: string;
  confirmLabel?: string;
  confirmVariant?: string;
  onConfirm: () => void | Promise<void>;
}

interface ConfirmActionModalProps {
  action: ConfirmActionState | null;
  onHide: () => void;
}

const ConfirmActionModal = ({ action, onHide }: ConfirmActionModalProps) => {
  const handleConfirm = async () => {
    if (!action) return;
    await action.onConfirm();
    onHide();
  };

  return (
    <Modal show={!!action} onHide={onHide} centered>
      <Modal.Header closeButton>
        <Modal.Title>{action?.title}</Modal.Title>
      </Modal.Header>
      <Modal.Body>{action?.message}</Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onHide}>取消</Button>
        <Button variant={action?.confirmVariant || 'primary'} onClick={handleConfirm}>
          {action?.confirmLabel || '確認'}
        </Button>
      </Modal.Footer>
    </Modal>
  );
};

export default ConfirmActionModal;
