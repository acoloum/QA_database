import { useState, useEffect } from 'react';
import { Modal, Button } from 'react-bootstrap';
import toast from 'react-hot-toast';
import { useInspectors } from '../../hooks/useInspectors';
import { buildReworkExecutionPayload, type ReworkExecutionFormValues } from './reworkFormPayload';
import ReworkExecutionForm from './ReworkExecutionForm';
import { useCreateReworkExecution } from './useReworkMutations';

interface ExecutionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    reworkNumber: string;
}

const defaultExecutionForm = (): ReworkExecutionFormValues => ({
    responsiblePerson: '',
    department: '製造部',
    collaborators: '',
    startTime: '',
    expectedEndTime: '',
    actualEndTime: '',
    equipment: '',
    method: '',
    sopNo: '',
    consumables: '',
    completedQty: '',
    defectQty: '',
    status: '',
    abnormalStatus: '',
});

const ExecutionModal = ({ show, handleClose, onSuccess, reworkNumber }: ExecutionModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show });
    const createExecution = useCreateReworkExecution({
        onSuccess: () => {
            onSuccess();
            handleClose();
        }
    });

    const [form, setForm] = useState<ReworkExecutionFormValues>(defaultExecutionForm());

    const resetForm = () => {
        setForm(defaultExecutionForm());
    };

    useEffect(() => {
        let cancelled = false;
        if (show) {
            queueMicrotask(() => {
                if (!cancelled) resetForm();
            });
        }
        return () => {
            cancelled = true;
        };
    }, [show]);

    const setField = (field: keyof ReworkExecutionFormValues, value: string) => {
        setForm(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = () => {
        if (!form.responsiblePerson) {
            toast.error('請選擇負責人員');
            return;
        }

        createExecution.mutate(buildReworkExecutionPayload({
            reworkNumber,
            ...form,
        }));
    };

    return (
        <Modal show={show} onHide={handleClose} size="lg" dialogClassName="modal-rework">
            <style type="text/css">{`
                .modal-rework {
                    max-width: 800px !important;
                }
                .modal-rework .modal-body {
                    max-height: 75vh;
                    overflow-y: auto;
                }
            `}</style>
            <Modal.Header closeButton>
                <Modal.Title>新增執行記錄 - {reworkNumber}</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <ReworkExecutionForm
                    inspectors={inspectors}
                    values={form}
                    onChange={setField}
                    responsibleLabel="負責人員 *"
                />
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={createExecution.isPending}>
                    {createExecution.isPending ? '儲存中...' : '儲存'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ExecutionModal;
