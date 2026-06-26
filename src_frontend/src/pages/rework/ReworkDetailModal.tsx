import { Button, Modal } from 'react-bootstrap';
import type {
  ReworkApplication,
  ReworkCostDetail,
  ReworkExecutionDetail,
  ReworkInspectionDetail,
} from '../../types';
import ReworkBasicTab from './ReworkBasicTab';
import ReworkCostTab from './ReworkCostTab';
import ReworkExecutionTab from './ReworkExecutionTab';
import ReworkInspectionTab from './ReworkInspectionTab';
import type { ReworkDetailTab } from './useReworkDetail';

interface ReworkDetailModalProps {
  show: boolean;
  onHide: () => void;
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
}

const tabButtons: { key: ReworkDetailTab; label: string }[] = [
  { key: 'basic', label: '基本資訊' },
  { key: 'execution', label: '執行記錄' },
  { key: 'inspection', label: '品檢記錄' },
  { key: 'cost', label: '成本分析' },
];

const ReworkDetailModal = ({
  show,
  onHide,
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
}: ReworkDetailModalProps) => (
  <Modal show={show} onHide={onHide} dialogClassName="modal-rework-detail">
    <Modal.Header closeButton>
      <Modal.Title>重工申請詳情 - {detail?.申請單號}</Modal.Title>
    </Modal.Header>
    <Modal.Body>
      {detail && (
        <>
          <ul className="nav nav-tabs" role="tablist">
            {tabButtons.map(tab => (
              <li className="nav-item" key={tab.key}>
                <button
                  className={`nav-link ${activeTab === tab.key ? 'active' : ''}`}
                  onClick={() => onTabChange(tab.key)}
                >
                  {tab.label}
                </button>
              </li>
            ))}
          </ul>
          <div className="tab-content mt-3">
            {activeTab === 'basic' && (
              <ReworkBasicTab detail={detail} onEditBasic={onEditBasic} onCloseRework={onCloseRework} />
            )}
            {activeTab === 'execution' && (
              <ReworkExecutionTab
                executions={executions}
                onAddExecution={onAddExecution}
                onEditExecution={onEditExecution}
                onDeleteExecution={onDeleteExecution}
              />
            )}
            {activeTab === 'inspection' && (
              <ReworkInspectionTab
                inspections={inspections}
                onAddInspection={onAddInspection}
                onEditInspection={onEditInspection}
                onDeleteInspection={onDeleteInspection}
              />
            )}
            {activeTab === 'cost' && (
              <ReworkCostTab
                costs={costs}
                onAddCost={onAddCost}
                onEditCost={onEditCost}
                onDeleteCost={onDeleteCost}
              />
            )}
          </div>
        </>
      )}
    </Modal.Body>
    <Modal.Footer>
      <Button variant="secondary" onClick={onHide}>關閉</Button>
    </Modal.Footer>
  </Modal>
);

export default ReworkDetailModal;
