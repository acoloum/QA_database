import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import MechanicalTraceNumberPanel from './MechanicalTraceNumberPanel';

describe('MechanicalTraceNumberPanel', () => {
  it('顯示標題、序號，並把輸入與新增事件交給上層', () => {
    const onChange = vi.fn();
    const onAdd = vi.fn();
    render(
      <MechanicalTraceNumberPanel
        idPrefix="extrusion"
        title="擠製編號"
        addLabel="新增擠製編號"
        values={[{ 序號: 1, 編號: '' }]}
        duplicateIndexes={new Set()}
        onChange={onChange}
        onAdd={onAdd}
        onRemove={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('擠製編號 1'), {
      target: { value: 'E001' },
    });
    fireEvent.click(screen.getByRole('button', { name: '新增擠製編號' }));
    expect(onChange).toHaveBeenCalledWith(0, 'E001');
    expect(onAdd).toHaveBeenCalledOnce();
  });

  it('重複列有可存取錯誤關聯', () => {
    render(
      <MechanicalTraceNumberPanel
        idPrefix="t4-furnace"
        title="T4爐號"
        addLabel="新增T4爐號"
        values={[
          { 序號: 1, 編號: 'T4-01' },
          { 序號: 2, 編號: 'T4-01' },
        ]}
        duplicateIndexes={new Set([0, 1])}
        onChange={vi.fn()}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    const first = screen.getByLabelText('T4爐號 1');
    expect(first).toHaveAttribute('aria-invalid', 'true');
    expect(first).toHaveAttribute(
      'aria-describedby',
      'mechanical-t4-furnace-1-duplicate-error',
    );
    expect(screen.getAllByText('同一清單內的編號不可重複')).toHaveLength(2);
  });
});
