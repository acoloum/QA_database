import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import PyrometryBasicSection from './PyrometryBasicSection';

describe('PyrometryBasicSection', () => {
  it('renders basic fields and notifies furnace/type changes', () => {
    const onFurnaceChange = vi.fn();
    const onTestTypeChange = vi.fn();

    render(
      <PyrometryBasicSection
        furnaces={[{ 識別碼: 1, 爐號: 'F-1', 名稱: '時效爐', 製程類型: '', TUS點數: 12, SAT點數: 2, TUS頻率_月: 3, SAT頻率_月: 3, TUS允許公差: '10', SAT允許誤差: '5', 有效加熱區尺寸: '', 儀器型式: '', CQI9等級: '', 啟用狀態: true, 備註: '' }]}
        inspectors={[{ id: 9, name: '檢驗員A' }]}
        furnaceId=""
        testType="TUS"
        testDate="2026-06-27"
        setpoint="180"
        tolerance="10"
        testerId=""
        testInstrument=""
        stdInstrument=""
        calDueDate=""
        note=""
        onFurnaceChange={onFurnaceChange}
        onTestTypeChange={onTestTypeChange}
        onTestDateChange={vi.fn()}
        onSetpointChange={vi.fn()}
        onToleranceChange={vi.fn()}
        onTesterIdChange={vi.fn()}
        onTestInstrumentChange={vi.fn()}
        onStdInstrumentChange={vi.fn()}
        onCalDueDateChange={vi.fn()}
        onNoteChange={vi.fn()}
      />,
    );

    expect(screen.getByText('爐子 *')).toBeInTheDocument();
    fireEvent.change(screen.getAllByRole('combobox')[0], { target: { value: '1' } });
    fireEvent.change(screen.getAllByRole('combobox')[1], { target: { value: 'SAT' } });

    expect(onFurnaceChange).toHaveBeenCalledWith('1');
    expect(onTestTypeChange).toHaveBeenCalledWith('SAT');
  });
});
