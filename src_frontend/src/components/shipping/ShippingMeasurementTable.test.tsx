import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ShippingMeasurementTable from './ShippingMeasurementTable';
import type { ShippingGroupMeasurements } from './shippingMeasurementUtils';

describe('ShippingMeasurementTable', () => {
  const groups: Record<string, ShippingGroupMeasurements> = {
    '1': {
      外徑: { value_min: '9.8', value_max: '10.2', is_ng: false },
      硬度: { value_single: '55', is_ng: false },
    },
  };

  const items = [
    { label: '外徑', key: '外徑', type: 'minmax' as const },
    { label: '硬度', key: '硬度', type: 'single' as const },
  ];

  it('renders min/max and single measurement inputs with violation state', () => {
    render(
      <ShippingMeasurementTable
        items={items}
        groupKeys={['1']}
        groups={groups}
        itemOffsets={[0, 2]}
        totalInputsPerGroup={3}
        fieldErrors={{}}
        violations={{ '1:外徑:value_min': true }}
        onMeasurementChange={vi.fn()}
        onAddGroup={vi.fn()}
        onRemoveGroup={vi.fn()}
        onToggleSegment={vi.fn()}
      />,
    );

    expect(screen.getByDisplayValue('9.8')).toHaveClass('is-invalid-breathing');
    expect(screen.getByDisplayValue('10.2')).toBeInTheDocument();
    expect(screen.getByDisplayValue('55')).toBeInTheDocument();
  });

  it('notifies measurement updates and group actions', () => {
    const onMeasurementChange = vi.fn();
    const onAddGroup = vi.fn();
    const onRemoveGroup = vi.fn();

    render(
      <ShippingMeasurementTable
        items={items}
        groupKeys={['1', '2']}
        groups={{ ...groups, '2': {} }}
        itemOffsets={[0, 2]}
        totalInputsPerGroup={3}
        fieldErrors={{}}
        violations={{}}
        onMeasurementChange={onMeasurementChange}
        onAddGroup={onAddGroup}
        onRemoveGroup={onRemoveGroup}
        onToggleSegment={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByDisplayValue('9.8'), { target: { value: '9.9' } });
    fireEvent.click(screen.getByTitle('新增量測組'));
    fireEvent.click(screen.getByTitle('移除第 2 組'));

    expect(onMeasurementChange).toHaveBeenCalledWith('1', '外徑', 'value_min', '9.9');
    expect(onAddGroup).toHaveBeenCalledTimes(1);
    expect(onRemoveGroup).toHaveBeenCalledWith('2');
  });

  it('可分段項目顯示切換 switch 並回報基鍵', () => {
    const onToggleSegment = vi.fn();
    render(
      <ShippingMeasurementTable
        items={[{ label: '外徑', key: '外徑', type: 'minmax' as const, segmentable: true }]}
        groupKeys={['1']}
        groups={{ '1': {} }}
        itemOffsets={[0]}
        totalInputsPerGroup={2}
        fieldErrors={{}}
        violations={{}}
        onMeasurementChange={vi.fn()}
        onAddGroup={vi.fn()}
        onRemoveGroup={vi.fn()}
        onToggleSegment={onToggleSegment}
      />,
    );

    fireEvent.click(screen.getByTitle('分段量測(前/中/後)'));
    expect(onToggleSegment).toHaveBeenCalledWith('外徑');
  });

  it('分段展開後 switch 僅出現在前段列且為勾選狀態', () => {
    const segItems = [
      { label: '外徑(前)', key: '外徑@前段', type: 'minmax' as const, segmentable: true, baseKey: '外徑', position: '前段' },
      { label: '外徑(中)', key: '外徑@中段', type: 'minmax' as const, segmentable: true, baseKey: '外徑', position: '中段' },
      { label: '外徑(後)', key: '外徑@後段', type: 'minmax' as const, segmentable: true, baseKey: '外徑', position: '後段' },
    ];
    render(
      <ShippingMeasurementTable
        items={segItems}
        groupKeys={['1']}
        groups={{ '1': {} }}
        itemOffsets={[0, 2, 4]}
        totalInputsPerGroup={6}
        fieldErrors={{}}
        violations={{}}
        onMeasurementChange={vi.fn()}
        onAddGroup={vi.fn()}
        onRemoveGroup={vi.fn()}
        onToggleSegment={vi.fn()}
      />,
    );

    const switches = screen.getAllByTitle('分段量測(前/中/後)');
    expect(switches).toHaveLength(1);
    expect(switches[0]).toBeChecked();
  });
});
