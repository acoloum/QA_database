import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ReworkModalHost from './ReworkModalHost';

vi.mock('../../components/rework/ApplyModal', () => ({ default: () => <div>ApplyModal</div> }));
vi.mock('../../components/rework/ApproveModal', () => ({ default: () => <div>ApproveModal</div> }));
vi.mock('../../components/rework/ExecutionModal', () => ({ default: () => <div>ExecutionModal</div> }));
vi.mock('../../components/rework/InspectionModal', () => ({ default: () => <div>InspectionModal</div> }));
vi.mock('../../components/rework/CostModal', () => ({ default: () => <div>CostModal</div> }));
vi.mock('../../components/rework/EditExecutionModal', () => ({ default: () => <div>EditExecutionModal</div> }));
vi.mock('../../components/rework/EditInspectionModal', () => ({ default: () => <div>EditInspectionModal</div> }));
vi.mock('../../components/rework/EditCostModal', () => ({ default: () => <div>EditCostModal</div> }));
vi.mock('../../components/rework/EditBasicInfoModal', () => ({ default: () => <div>EditBasicInfoModal</div> }));
vi.mock('../../components/rework/ReworkFollowUpModal', () => ({ default: () => <div>ReworkFollowUpModal</div> }));
vi.mock('./ReworkDetailModal', () => ({ default: () => <div>ReworkDetailModal</div> }));
vi.mock('../../components/common/ConfirmActionModal', () => ({ default: () => <div>ConfirmActionModal</div> }));

describe('ReworkModalHost', () => {
  it('renders all modal slots from page state', () => {
    render(
      <ReworkModalHost
        showApplyModal
        onCloseApplyModal={vi.fn()}
        onApplySuccess={vi.fn()}
        initialNcmrId=""
        initialNcmrNo=""
        showApproveModal
        onCloseApproveModal={vi.fn()}
        onApproveSuccess={vi.fn()}
        selectedReworkId={1}
        showDetailModal
        onHideDetailModal={vi.fn()}
        detail={null}
        activeTab="basic"
        onTabChange={vi.fn()}
        executions={[]}
        inspections={[]}
        costs={[]}
        onEditBasic={vi.fn()}
        onCloseRework={vi.fn()}
        onAddExecution={vi.fn()}
        onEditExecution={vi.fn()}
        onDeleteExecution={vi.fn()}
        onAddInspection={vi.fn()}
        onEditInspection={vi.fn()}
        onDeleteInspection={vi.fn()}
        onAddCost={vi.fn()}
        onEditCost={vi.fn()}
        onDeleteCost={vi.fn()}
        showExecutionModal
        onCloseExecutionModal={vi.fn()}
        onExecutionSuccess={vi.fn()}
        reworkNumber=""
        showInspectionModal
        onCloseInspectionModal={vi.fn()}
        onInspectionSuccess={vi.fn()}
        showCostModal
        onCloseCostModal={vi.fn()}
        onCostSuccess={vi.fn()}
        showEditExecutionModal
        onCloseEditExecutionModal={vi.fn()}
        onEditExecutionSuccess={vi.fn()}
        selectedExecution={null}
        showEditInspectionModal
        onCloseEditInspectionModal={vi.fn()}
        onEditInspectionSuccess={vi.fn()}
        selectedInspection={null}
        showEditCostModal
        onCloseEditCostModal={vi.fn()}
        onEditCostSuccess={vi.fn()}
        selectedCost={null}
        showEditBasicModal
        onCloseEditBasicModal={vi.fn()}
        onEditBasicSuccess={vi.fn()}
        followUpModal={{ show: true, ncmrId: 1, ncmrNumber: 'NCMR-1' }}
        onHideFollowUpModal={vi.fn()}
        confirmAction={null}
        onHideConfirmAction={vi.fn()}
      />,
    );

    expect(screen.getByText('ApplyModal')).toBeInTheDocument();
    expect(screen.getByText('ReworkDetailModal')).toBeInTheDocument();
    expect(screen.getByText('ConfirmActionModal')).toBeInTheDocument();
  });
});
