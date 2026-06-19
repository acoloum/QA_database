import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ReportFieldsSection from './ReportFieldsSection';
import { emptyItemRow, type ItemRow } from './pyrometryFormUtils';

describe('ReportFieldsSection', () => {
  it('updates report metadata and item rows', async () => {
    const user = userEvent.setup();
    const setReportMeta = vi.fn();
    const setItemRows = vi.fn();
    const updateItemRow = vi.fn();
    const itemRows: ItemRow[] = [{ 工件料號: 'P-001', 生產批號: '', 內外徑尺寸: '', 支數: '' }];

    render(
      <ReportFieldsSection
        showReport
        testType="SAT"
        furnaceId="1"
        testDate="2026-06-19"
        setpoint="180"
        reportMeta={{ 測試條件: '空爐', 客戶名稱: '' }}
        itemRows={itemRows}
        onToggle={() => undefined}
        onInheritFromTus={() => undefined}
        onSetReportMeta={setReportMeta}
        onSetItemRows={setItemRows}
        onUpdateItemRow={updateItemRow}
      />,
    );

    await user.click(screen.getByLabelText('滿爐'));
    expect(setReportMeta).toHaveBeenCalledWith(expect.any(Function));
    expect(setReportMeta.mock.calls[0][0]({ 測試條件: '空爐' })).toEqual({ 測試條件: '滿爐' });

    await user.type(screen.getByLabelText('客戶名稱'), 'A');
    expect(setReportMeta).toHaveBeenLastCalledWith(expect.any(Function));

    await user.type(screen.getByDisplayValue('P-001'), '2');
    expect(updateItemRow).toHaveBeenCalledWith(0, '工件料號', expect.stringContaining('2'));

    await user.click(screen.getByRole('button', { name: '+ 新增工件' }));
    expect(setItemRows).toHaveBeenCalledWith(expect.any(Function));
    expect(setItemRows.mock.calls[0][0](itemRows)).toEqual([...itemRows, emptyItemRow()]);
  });
});
