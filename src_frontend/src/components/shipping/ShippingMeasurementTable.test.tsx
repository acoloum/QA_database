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
      />,
    );

    fireEvent.change(screen.getByDisplayValue('9.8'), { target: { value: '9.9' } });
    fireEvent.click(screen.getByTitle('新增量測組'));
    fireEvent.click(screen.getByTitle('移除第 2 組'));

    expect(onMeasurementChange).toHaveBeenCalledWith('1', '外徑', 'value_min', '9.9');
    expect(onAddGroup).toHaveBeenCalledTimes(1);
    expect(onRemoveGroup).toHaveBeenCalledWith('2');
  });
});
