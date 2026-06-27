import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ToleranceDetailTable from './ToleranceDetailTable';
import { createToleranceDetailRow } from './toleranceFormUtils';

describe('ToleranceDetailTable', () => {
  it('renders tolerance rows and action controls', () => {
    const detail = {
      ...createToleranceDetailRow('row-1'),
      item: '外徑',
      position: 'A',
      size_min: '10',
      size_max: '11',
      tol_min: '-0.1',
      tol_max: '0.1',
      std: '10.5',
      unit: 'mm',
      remark: '備註',
    };

    render(
      <ToleranceDetailTable
        details={[detail]}
        fieldErrors={{}}
        onDragEnd={vi.fn()}
        onChange={vi.fn()}
        onRemove={vi.fn()}
        onAddRow={vi.fn()}
      />,
    );

    expect(screen.getByText('公差明細')).toBeInTheDocument();
    expect(screen.getByDisplayValue('外徑')).toBeInTheDocument();
    expect(screen.getByDisplayValue('10.5')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /新增明細/ })).toBeInTheDocument();
  });
});
