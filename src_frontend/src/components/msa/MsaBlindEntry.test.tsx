import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MsaBlindTask } from '../../types/msa';
import MsaBlindEntry from './MsaBlindEntry';

const baseTask: MsaBlindTask = {
  requested_order: 1,
  part_blind_code: 'P-01',
  appraiser_blind_code: '甲',
  trial_no: 1,
  recorded: false,
};

const renderEntry = (task: MsaBlindTask, completed = 0) =>
  render(
    <MsaBlindEntry
      task={task}
      position={task.requested_order}
      total={5}
      completed={completed}
      unit="mm"
      categories={[]}
      isSaving={false}
      errorMessage={null}
      onSubmit={() => undefined}
    />,
  );

describe('MsaBlindEntry', () => {
  it('切換到不同任務時清空輸入並把焦點帶回輸入欄', () => {
    const { rerender } = renderEntry(baseTask);
    fireEvent.change(screen.getByLabelText('量測讀值（mm）'), { target: { value: '10.2' } });
    expect(screen.getByDisplayValue('10.2')).toBeInTheDocument();

    rerender(
      <MsaBlindEntry
        task={{ ...baseTask, requested_order: 2 }}
        position={2}
        total={5}
        completed={0}
        unit="mm"
        categories={[]}
        isSaving={false}
        errorMessage={null}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.queryByDisplayValue('10.2')).not.toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByLabelText('量測讀值（mm）'));
  });

  it('同一任務重新渲染（例如已記錄數更新）時保留輸入', () => {
    const { rerender } = renderEntry(baseTask);
    fireEvent.change(screen.getByLabelText('量測讀值（mm）'), { target: { value: '10.2' } });
    expect(screen.getByDisplayValue('10.2')).toBeInTheDocument();

    rerender(
      <MsaBlindEntry
        task={baseTask}
        position={1}
        total={5}
        completed={1}
        unit="mm"
        categories={[]}
        isSaving={false}
        errorMessage={null}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.getByDisplayValue('10.2')).toBeInTheDocument();
  });

  it('requested_order 相同但評價人不同時視為不同任務，避免殘留前一評價人的輸入', () => {
    const { rerender } = renderEntry(baseTask);
    fireEvent.change(screen.getByLabelText('量測讀值（mm）'), { target: { value: '10.2' } });
    expect(screen.getByDisplayValue('10.2')).toBeInTheDocument();

    rerender(
      <MsaBlindEntry
        task={{ ...baseTask, appraiser_blind_code: '乙' }}
        position={1}
        total={5}
        completed={0}
        unit="mm"
        categories={[]}
        isSaving={false}
        errorMessage={null}
        onSubmit={() => undefined}
      />,
    );

    expect(screen.queryByDisplayValue('10.2')).not.toBeInTheDocument();
  });
});
