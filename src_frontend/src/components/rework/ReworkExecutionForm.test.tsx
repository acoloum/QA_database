import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ReworkExecutionForm from './ReworkExecutionForm';

const noop = vi.fn();

describe('ReworkExecutionForm', () => {
  it('renders execution fields with existing values', () => {
    render(
      <ReworkExecutionForm
        inspectors={[{ id: 1, name: '王小明' }]}
        values={{
          responsiblePerson: '王小明',
          department: '製造部',
          collaborators: '李小華',
          startTime: '2026-06-01T08:00',
          expectedEndTime: '2026-06-01T12:00',
          actualEndTime: '2026-06-01T11:30',
          equipment: '機台 A',
          method: '重工方式',
          sopNo: 'SOP-001',
          consumables: '砂紙',
          completedQty: '10',
          defectQty: '1',
          status: '已完成',
          abnormalStatus: '無',
        }}
        onChange={noop}
        responsibleLabel="負責人員"
      />,
    );

    expect(screen.getByLabelText('負責人員')).toHaveValue('王小明');
    expect(screen.getByLabelText('執行部門')).toHaveValue('製造部');
    expect(screen.getByLabelText('使用設備')).toHaveValue('機台 A');
    expect(screen.getByLabelText('SOP編號')).toHaveValue('SOP-001');
    expect(screen.getByLabelText('執行狀況')).toHaveValue('已完成');
  });
});
