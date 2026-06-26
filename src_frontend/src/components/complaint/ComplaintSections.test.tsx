import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  ComplaintBasicSection,
  ComplaintDeadlineSection,
  ComplaintResponseSection,
  ComplaintWarrantySection,
} from './ComplaintSections';

describe('ComplaintSections', () => {
  const noop = vi.fn();

  it('renders basic complaint fields and extrusion tags', () => {
    render(
      <ComplaintBasicSection
        customer="客戶A"
        complaintDate="2026-06-27"
        complaintType="quality"
        material="6061"
        spec="T6"
        extrusionInput="EXT-2"
        extrusionNos={['EXT-1']}
        severity="Major"
        defectCategory="尺寸不良"
        description="外徑超差"
        complaintTypeLabels={{ quality: '品質客訴', warranty: 'Warranty', field_failure: 'Field Failure' }}
        severityOptions={['Critical', 'Major', 'Minor']}
        defectCategoryOptions={['尺寸不良']}
        onCustomerChange={noop}
        onComplaintDateChange={noop}
        onComplaintTypeChange={noop}
        onMaterialChange={noop}
        onSpecChange={noop}
        onExtrusionInputChange={noop}
        onAddExtrusionNo={noop}
        onRemoveExtrusionNo={noop}
        onSeverityChange={noop}
        onDefectCategoryChange={noop}
        onDescriptionChange={noop}
      />,
    );

    expect(screen.getByText('基本資訊')).toBeInTheDocument();
    expect(screen.getByDisplayValue('客戶A')).toBeInTheDocument();
    expect(screen.getByText('EXT-1')).toBeInTheDocument();
  });

  it('renders reply deadline fields', () => {
    render(
      <ComplaintDeadlineSection
        initialReplyDeadline="2026-06-28"
        finalReplyDeadline="2026-07-01"
        onInitialReplyDeadlineChange={noop}
        onFinalReplyDeadlineChange={noop}
      />,
    );

    expect(screen.getByText('應答時效')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2026-06-28')).toBeInTheDocument();
  });

  it('renders warranty fields when complaint type needs warranty information', () => {
    render(
      <ComplaintWarrantySection
        complaintType="warranty"
        deviceSerial="SN-1"
        usageEnv="戶外"
        failureHours="12"
        onDeviceSerialChange={vi.fn()}
        onUsageEnvChange={vi.fn()}
        onFailureHoursChange={vi.fn()}
      />,
    );

    expect(screen.getByText('Warranty 申請資訊')).toBeInTheDocument();
    expect(screen.getByDisplayValue('SN-1')).toBeInTheDocument();
  });

  it('hides warranty fields for quality complaints and labels field failure', () => {
    const { rerender } = render(
      <ComplaintWarrantySection
        complaintType="quality"
        deviceSerial=""
        usageEnv=""
        failureHours=""
        onDeviceSerialChange={vi.fn()}
        onUsageEnvChange={vi.fn()}
        onFailureHoursChange={vi.fn()}
      />,
    );

    expect(screen.queryByText('Warranty 申請資訊')).not.toBeInTheDocument();

    rerender(
      <ComplaintWarrantySection
        complaintType="field_failure"
        deviceSerial=""
        usageEnv=""
        failureHours=""
        onDeviceSerialChange={vi.fn()}
        onUsageEnvChange={vi.fn()}
        onFailureHoursChange={vi.fn()}
      />,
    );

    expect(screen.getByText('Field Failure 資訊')).toBeInTheDocument();
  });

  it('renders edit response controls', () => {
    render(
      <ComplaintResponseSection
        status="處理中"
        initialReply="初步"
        finalReply="結論"
        onStatusChange={vi.fn()}
        onInitialReplyChange={vi.fn()}
        onFinalReplyChange={vi.fn()}
      />,
    );

    expect(screen.getByText('處理回覆')).toBeInTheDocument();
    expect(screen.getByDisplayValue('初步')).toBeInTheDocument();
  });
});
