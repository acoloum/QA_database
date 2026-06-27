import { useState, useEffect, useCallback } from 'react';
import { Modal, Button } from 'react-bootstrap';
import type { ReworkExecutionDetail } from '../../types';
import { useInspectors } from '../../hooks/useInspectors';
import {
    buildReworkExecutionPayload,
    formatDateTimeLocal,
    type ReworkExecutionFormValues,
} from './reworkFormPayload';
import ReworkExecutionForm from './ReworkExecutionForm';
import { useUpdateReworkExecution } from './useReworkMutations';

// 使用 types/index.ts 的 ReworkExecutionDetail 取代本地 interface，保持型別一致
interface EditExecutionModalProps {
    show: boolean;
    handleClose: () => void;
    onSuccess: () => void;
    execution: ReworkExecutionDetail | null;
}

const emptyExecutionForm = (): ReworkExecutionFormValues => ({
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

const EditExecutionModal = ({ show, handleClose, onSuccess, execution }: EditExecutionModalProps) => {
    const { data: inspectors = [] } = useInspectors({ enabled: show && !!execution });
    const updateExecution = useUpdateReworkExecution({
        onSuccess: () => {
            onSuccess();
            handleClose();
        }
    });

    const [form, setForm] = useState<ReworkExecutionFormValues>(emptyExecutionForm());

    const loadExecutionData = useCallback(() => {
        if (!execution) return;
        setForm({
            responsiblePerson: execution.負責人員姓名 || '',
            department: execution.執行部門 || '製造部',
            collaborators: execution.協同人員 || '',
            startTime: formatDateTimeLocal(execution.開始時間 || ''),
            expectedEndTime: formatDateTimeLocal(execution.預計完成時間 || ''),
            actualEndTime: formatDateTimeLocal(execution.實際完成時間 || ''),
            equipment: execution.使用設備 || '',
            method: execution.重工方式 || '',
            sopNo: execution.SOP編號 || '',
            consumables: execution.耗材記錄 || '',
            completedQty: execution.完成數量?.toString() || '',
            defectQty: execution.不良數量?.toString() || '',
            status: execution.執行狀況 || '',
            abnormalStatus: execution.異常狀況 || '',
        });
    }, [execution]);

    // useEffect 放在 useCallback 宣告後，確保函數已初始化
    useEffect(() => {
        let cancelled = false;
        if (show && execution) {
            queueMicrotask(() => {
                if (!cancelled) loadExecutionData();
            });
        }
        return () => {
            cancelled = true;
        };
    }, [show, execution, loadExecutionData]);

    const setField = (field: keyof ReworkExecutionFormValues, value: string) => {
        setForm(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = () => {
        if (!execution) return;
        const id = execution.識別碼;
        if (!id) return;

        updateExecution.mutate({
            id,
            payload: buildReworkExecutionPayload({
                ...form,
            })
        });
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
                <Modal.Title>編輯執行記錄</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <ReworkExecutionForm
                    inspectors={inspectors}
                    values={form}
                    onChange={setField}
                    responsibleLabel="負責人員"
                />
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={updateExecution.isPending}>
                    {updateExecution.isPending ? '儲存中...' : '儲存'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default EditExecutionModal;
