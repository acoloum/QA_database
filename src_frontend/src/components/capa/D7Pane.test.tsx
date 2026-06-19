import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D7Pane from './D7Pane';
import type { InspectorItem } from './capaInspectors';
import type { ActionTask, D7Action } from '../../types';

const inspectors: InspectorItem[] = [
  { id: 1, name: '王小明', group: '品保' },
  { id: 2, name: '李小華', group: '製造' },
];

const actions: D7Action[] = [
  { type: 'pfmea', checked: true, assignee_id: 1, due_date: '2026-06-30', description: '更新風險評估' },
  { type: 'training', checked: false },
];

const tasks: ActionTask[] = [
  {
    id: 10,
    task_no: 'TASK-001',
    source_type: 'capa',
    source_id: 42,
    category: 'pfmea',
    status: 'completed',
  },
];

describe('D7Pane', () => {
  it('渲染橫展項目、任務狀態並可更新勾選項目', () => {
    const onToggle = vi.fn();
    const onUpdateField = vi.fn();
    const onSave = vi.fn();

    render(
      <D7Pane
        actions={actions}
        tasks={tasks}
        inspectors={inspectors}
        onToggle={onToggle}
        onUpdateField={onUpdateField}
        onSave={onSave}
        saving={false}
      />,
    );

    expect(screen.getByText('PFMEA 更新')).toBeInTheDocument();
    expect(screen.getByText('教育訓練')).toBeInTheDocument();
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2026-06-30')).toBeInTheDocument();
    expect(screen.getByDisplayValue('更新風險評估')).toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue('王小明'), { target: { value: '2' } });
    expect(onUpdateField).toHaveBeenCalledWith(0, 'assignee_id', 2);

    fireEvent.click(screen.getByRole('checkbox', { name: '教育訓練' }));
    expect(onToggle).toHaveBeenCalledWith(1, true);

    fireEvent.click(screen.getByRole('button', { name: '儲存此步驟' }));
    expect(onSave).toHaveBeenCalled();
  });
});
