import type { CalibrationWorkflowStatus } from '../../types/calibration';

const steps: Array<{ status: CalibrationWorkflowStatus; label: string }> = [
  { status: 'draft', label: '草稿' },
  { status: 'in_progress', label: '登錄中' },
  { status: 'ready_for_submission', label: '待送審' },
  { status: 'submitted', label: '待核准' },
  { status: 'approved', label: '已核准' },
];

const statusLabel = (status: CalibrationWorkflowStatus) => ({
  draft: '草稿',
  in_progress: '進行中',
  ready_for_submission: '待送審',
  submitted: '待核准',
  rejected: '已退回',
  approved: '已核准',
  superseded: '已取代',
  voided: '已作廢',
}[status]);

export default function CalibrationWorkflowBar({
  status,
}: { status: CalibrationWorkflowStatus }) {
  const activeIndex = steps.findIndex((step) => step.status === status);
  return (
    <section className="cal-workflow-bar" aria-label={`校正工作流：${statusLabel(status)}`}>
      <p className="cal-kicker">受控工作流</p>
      <ol>
        {steps.map((step, index) => (
          <li
            key={step.status}
            data-state={index <= activeIndex ? 'complete' : 'pending'}
            aria-current={step.status === status ? 'step' : undefined}
          >
            <span aria-hidden="true">{index + 1}</span>
            {step.label}
          </li>
        ))}
      </ol>
      {activeIndex === -1 && <p>目前狀態：{statusLabel(status)}</p>}
    </section>
  );
}
