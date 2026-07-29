import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { CalibrationRecord } from '../../types/calibration';
import CalibrationEvidenceReview from './CalibrationEvidenceReview';

const point = (pointCode: string) => ({
  id: pointCode === 'P01' ? 31 : 32,
  point_code: pointCode,
  measurement_mode: '外徑',
  unit: 'mm',
  required_repetitions: 2,
  completed_reading_count: 2,
  result: 'pass',
  mean_error: '0.0015',
  mean_correction: '-0.0015',
  error_range: '0.0010',
  sample_stddev: '0.0007',
});

const baseRecord = {
  id: 41,
  row_version: 5,
  result: 'pass',
  status: 'ready_for_submission',
  calibration_type: 'internal',
  reference_standard_equipment_id: 9,
  certificate_attachment_id: null,
  environment_conditions: {},
  calculation_summary: { completed_points: 2 },
  points: [point('P01'), point('P02')],
} as unknown as CalibrationRecord;

const renderReview = (
  record: CalibrationRecord,
  blockers: string[] = [],
) => render(
  <CalibrationEvidenceReview
    record={record}
    validation={{
      row_version: record.row_version,
      result: blockers.length > 0 ? 'pending' : 'pass',
      blockers,
      passed_scope_codes: [],
      failed_scope_codes: [],
    }}
    reason=""
    onReasonChange={vi.fn()}
    onValidate={vi.fn()}
    onSubmit={vi.fn()}
    onNavigateBlocker={vi.fn()}
    validating={false}
    submitting={false}
    dirty={false}
    readOnly={false}
  />,
);

describe('校正證據檢閱', () => {
  it('顯示後端實際保存的計算證據欄位', () => {
    renderReview({
      ...baseRecord,
      points: [point('P01')],
    } as unknown as CalibrationRecord);

    expect(screen.getByText('平均器差 0.0015 mm')).toBeInTheDocument();
    expect(screen.getByText('平均補正值 -0.0015 mm')).toBeInTheDocument();
    expect(screen.getByText('器差範圍 0.0010 mm')).toBeInTheDocument();
    expect(screen.getByText('樣本標準差 0.0007 mm')).toBeInTheDocument();
  });

  it('相同 blocker 涵蓋多個校正點時逐點列出返回入口', () => {
    renderReview({
      ...baseRecord,
      calculation_summary: {
        completed_points: 0,
        points: [
          { point_code: 'P01', blockers: ['CALIBRATION_READING_MISSING'] },
          { point_code: 'P02', blockers: ['CALIBRATION_READING_MISSING'] },
        ],
      },
    } as unknown as CalibrationRecord, ['CALIBRATION_READING_MISSING']);

    expect(screen.getByRole('button', { name: '返回 P01 讀值' }))
      .toBeInTheDocument();
    expect(screen.getByRole('button', { name: '返回 P02 讀值' }))
      .toBeInTheDocument();
  });
});
