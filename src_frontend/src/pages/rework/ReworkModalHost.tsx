import type {
  ReworkApplication,
  ReworkCostDetail,
  ReworkExecutionDetail,
  ReworkInspectionDetail,
} from '../../types';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import ApplyModal from '../../components/rework/ApplyModal';
import ApproveModal from '../../components/rework/ApproveModal';
import CostModal from '../../components/rework/CostModal';
import EditBasicInfoModal from '../../components/rework/EditBasicInfoModal';
import EditCostModal from '../../components/rework/EditCostModal';
import EditExecutionModal from '../../components/rework/EditExecutionModal';
import EditInspectionModal from '../../components/rework/EditInspectionModal';
import ExecutionModal from '../../components/rework/ExecutionModal';
import InspectionModal from '../../components/rework/InspectionModal';
import ReworkFollowUpModal from '../../components/rework/ReworkFollowUpModal';
import type { ReworkFollowUpState } from './reworkPageUtils';
import ReworkDetailModal from './ReworkDetailModal';
import type { ReworkDetailTab } from './useReworkDetail';

interface ReworkModalHostProps {
  showApplyModal: boolean;
  onCloseApplyModal: () => void;
  onApplySuccess: () => void;
  initialNcmrId: string;
  initialNcmrNo: string;
  showApproveModal: boolean;
  onCloseApproveModal: () => void;
  onApproveSuccess: () => void;
  selectedReworkId: number | null;
  showDetailModal: boolean;
  onHideDetailModal: () => void;
  detail: ReworkApplication | null;
  activeTab: ReworkDetailTab;
  onTabChange: (tab: ReworkDetailTab) => void;
  executions: ReworkExecutionDetail[];
  inspections: ReworkInspectionDetail[];
  costs: ReworkCostDetail[];
  onEditBasic: () => void;
  onCloseRework: (reworkId: number) => void;
  onAddExecution: () => void;
  onEditExecution: (execution: ReworkExecutionDetail) => void;
  onDeleteExecution: (executionId: number) => void;
  onAddInspection: () => void;
  onEditInspection: (inspection: ReworkInspectionDetail) => void;
  onDeleteInspection: (inspectionId: number) => void;
  onAddCost: () => void;
  onEditCost: (cost: ReworkCostDetail) => void;
  onDeleteCost: (costId: number) => void;
  showExecutionModal: boolean;
  onCloseExecutionModal: () => void;
  onExecutionSuccess: () => void;
  reworkNumber: string;
  showInspectionModal: boolean;
  onCloseInspectionModal: () => void;
  onInspectionSuccess: () => void;
  showCostModal: boolean;
  onCloseCostModal: () => void;
  onCostSuccess: () => void;
  showEditExecutionModal: boolean;
  onCloseEditExecutionModal: () => void;
  onEditExecutionSuccess: () => void;
  selectedExecution: ReworkExecutionDetail | null;
  showEditInspectionModal: boolean;
  onCloseEditInspectionModal: () => void;
  onEditInspectionSuccess: () => void;
  selectedInspection: ReworkInspectionDetail | null;
  showEditCostModal: boolean;
  onCloseEditCostModal: () => void;
  onEditCostSuccess: () => void;
  selectedCost: ReworkCostDetail | null;
  showEditBasicModal: boolean;
  onCloseEditBasicModal: () => void;
  onEditBasicSuccess: () => void;
  followUpModal: ReworkFollowUpState | null;
  onHideFollowUpModal: () => void;
  confirmAction: ConfirmActionState | null;
  onHideConfirmAction: () => void;
}

const ReworkModalHost = ({
  showApplyModal,
  onCloseApplyModal,
  onApplySuccess,
  initialNcmrId,
  initialNcmrNo,
  showApproveModal,
  onCloseApproveModal,
  onApproveSuccess,
  selectedReworkId,
  showDetailModal,
  onHideDetailModal,
  detail,
  activeTab,
  onTabChange,
  executions,
  inspections,
  costs,
  onEditBasic,
  onCloseRework,
  onAddExecution,
  onEditExecution,
  onDeleteExecution,
  onAddInspection,
  onEditInspection,
  onDeleteInspection,
  onAddCost,
  onEditCost,
  onDeleteCost,
  showExecutionModal,
  onCloseExecutionModal,
  onExecutionSuccess,
  reworkNumber,
  showInspectionModal,
  onCloseInspectionModal,
  onInspectionSuccess,
  showCostModal,
  onCloseCostModal,
  onCostSuccess,
  showEditExecutionModal,
  onCloseEditExecutionModal,
  onEditExecutionSuccess,
  selectedExecution,
  showEditInspectionModal,
  onCloseEditInspectionModal,
  onEditInspectionSuccess,
  selectedInspection,
  showEditCostModal,
  onCloseEditCostModal,
  onEditCostSuccess,
  selectedCost,
  showEditBasicModal,
  onCloseEditBasicModal,
  onEditBasicSuccess,
  followUpModal,
  onHideFollowUpModal,
  confirmAction,
  onHideConfirmAction,
}: ReworkModalHostProps) => (
  <>
    <ApplyModal
      show={showApplyModal}
      handleClose={onCloseApplyModal}
      onSuccess={onApplySuccess}
      initialNcmrId={initialNcmrId}
      initialNcmrNo={initialNcmrNo}
    />
    <ApproveModal
      show={showApproveModal}
      handleClose={onCloseApproveModal}
      onSuccess={onApproveSuccess}
      reworkId={selectedReworkId}
    />
    <ReworkDetailModal
      show={showDetailModal}
      onHide={onHideDetailModal}
      detail={detail}
      activeTab={activeTab}
      onTabChange={onTabChange}
      executions={executions}
      inspections={inspections}
      costs={costs}
      onEditBasic={onEditBasic}
      onCloseRework={onCloseRework}
      onAddExecution={onAddExecution}
      onEditExecution={onEditExecution}
      onDeleteExecution={onDeleteExecution}
      onAddInspection={onAddInspection}
      onEditInspection={onEditInspection}
      onDeleteInspection={onDeleteInspection}
      onAddCost={onAddCost}
      onEditCost={onEditCost}
      onDeleteCost={onDeleteCost}
    />
    <ExecutionModal
      show={showExecutionModal}
      handleClose={onCloseExecutionModal}
      onSuccess={onExecutionSuccess}
      reworkNumber={reworkNumber}
    />
    <InspectionModal
      show={showInspectionModal}
      handleClose={onCloseInspectionModal}
      onSuccess={onInspectionSuccess}
      reworkNumber={reworkNumber}
    />
    <CostModal
      show={showCostModal}
      handleClose={onCloseCostModal}
      onSuccess={onCostSuccess}
      reworkNumber={reworkNumber}
    />
    <EditExecutionModal
      show={showEditExecutionModal}
      handleClose={onCloseEditExecutionModal}
      onSuccess={onEditExecutionSuccess}
      execution={selectedExecution}
    />
    <EditInspectionModal
      show={showEditInspectionModal}
      handleClose={onCloseEditInspectionModal}
      onSuccess={onEditInspectionSuccess}
      inspection={selectedInspection}
    />
    <EditCostModal
      show={showEditCostModal}
      handleClose={onCloseEditCostModal}
      onSuccess={onEditCostSuccess}
      cost={selectedCost}
    />
    <EditBasicInfoModal
      show={showEditBasicModal}
      handleClose={onCloseEditBasicModal}
      onSuccess={onEditBasicSuccess}
      application={detail}
    />
    {followUpModal && (
      <ReworkFollowUpModal
        show={followUpModal.show}
        onHide={onHideFollowUpModal}
        ncmrId={followUpModal.ncmrId}
        ncmrNumber={followUpModal.ncmrNumber}
      />
    )}
    <ConfirmActionModal action={confirmAction} onHide={onHideConfirmAction} />
  </>
);

export default ReworkModalHost;
