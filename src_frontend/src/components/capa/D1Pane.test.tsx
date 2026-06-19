import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D1Pane from './D1Pane';
import type { InspectorItem } from './capaInspectors';

const inspectors: InspectorItem[] = [
  { id: 1, name: '王小明', group: '品保' },
  { id: 2, name: '李小華', group: '製造' },
];

const noop = () => undefined;

describe('D1Pane', () => {
  it('渲染團隊欄位並可切換成員', () => {
    const setMembers = vi.fn();
    const onSave = vi.fn();

    render(
      <D1Pane
        champion=""
        setChampion={noop}
        leader=""
        setLeader={noop}
        members={[1]}
        setMembers={setMembers}
        inspectors={inspectors}
        onSave={onSave}
        saving={false}
      />,
    );

    expect(screen.getByLabelText('Champion（指導者）')).toBeInTheDocument();
    expect(screen.getByLabelText('Team Leader（負責人）')).toBeInTheDocument();
    expect(screen.getByText('品保')).toBeInTheDocument();
    expect(screen.getByText('製造')).toBeInTheDocument();
    expect(screen.getByLabelText('王小明')).toBeChecked();

    fireEvent.click(screen.getByLabelText('李小華'));
    expect(setMembers).toHaveBeenCalledWith([1, 2]);

    fireEvent.click(screen.getByRole('button', { name: '儲存此步驟' }));
    expect(onSave).toHaveBeenCalled();
  });
});
